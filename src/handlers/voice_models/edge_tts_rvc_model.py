import os
import sys
import traceback
import tempfile
import asyncio
import re
from xml.sax.saxutils import escape
from typing import Optional, Any, List, Dict

import soundfile as sf

from .base_model import IVoiceModel
from main_logger import logger
from utils.translation_manager import t
from utils import get_character_voice_paths

from core.events import get_event_bus, Events
from core.install_types import InstallPlan, InstallAction
from core.install_requirements import InstallRequirement, check_requirements

from handlers.voice_models.install_plan_helpers import torch_install_action, pip_uninstall_action


class EdgeTTSRVCInstallSpec:
    @classmethod
    def supported_model_ids(cls) -> list[str]:
        return ["low", "low+"]

    @classmethod
    def title(cls, model_id: str) -> str:
        return t("handlers.voice_models.edge_tts_rvc.title") + str(model_id)

    @classmethod
    def requirements(cls, model_id: str, ctx: dict) -> list[InstallRequirement]:
        mid = str(model_id)
        gpu = str((ctx or {}).get("gpu_vendor") or "CPU")

        req: list[InstallRequirement] = [
            InstallRequirement(id="omegaconf", kind="python_dist", spec="omegaconf", required=True),
        ]

        if mid == "low+":
            req.append(InstallRequirement(id="silero", kind="python_dist", spec="silero", required=True))
            req.append(InstallRequirement(id="silero_module", kind="python_module", module="silero", required=True))

        # AMD uses onnx+dml package; NVIDIA/others use torch variant.
        if gpu == "AMD":
            req.append(InstallRequirement(id="tts_rvc_pkg", kind="python_dist", spec="tts-with-rvc-onnx[dml]", required=True))
        else:
            req.append(InstallRequirement(id="tts_rvc_pkg", kind="python_dist", spec="tts-with-rvc", required=True))

        # Runtime import path in this project
        req.append(InstallRequirement(id="tts_with_rvc_module", kind="python_module", module="tts_with_rvc", required=True))
        return req

    @classmethod
    def is_installed(cls, model_id: str, ctx: dict) -> bool:
        st = check_requirements(cls.requirements(model_id, ctx), ctx=ctx)
        return bool(st.get("ok"))

    @classmethod
    def _patch_fairseq_configs_call(cls):
        def _fn(*, pip_installer=None, callbacks=None, ctx=None, **_kwargs) -> bool:
            cb = callbacks
            libs_path_abs = getattr(pip_installer, "libs_path_abs", None) if pip_installer else None
            libs_path_abs = str(libs_path_abs or os.path.abspath("Lib"))

            def log(m: str):
                try:
                    if cb:
                        cb.log(str(m))
                except Exception:
                    pass

            config_path = os.path.join(libs_path_abs, "fairseq", "dataclass", "configs.py")
            if not os.path.exists(config_path):
                log(t("handlers.voice_models.edge_tts_rvc.fairseq_not_found"))
                return True

            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    source = f.read()

                patched = re.sub(r"metadata=\{(.*?)help:", r'metadata={\1"help":', source)

                if patched != source:
                    with open(config_path, "w", encoding="utf-8") as f:
                        f.write(patched)
                    log(t("handlers.voice_models.edge_tts_rvc.patch_applied"))
                else:
                    log(t("handlers.voice_models.edge_tts_rvc.patch_already_applied"))
                return True
            except Exception as e:
                log(t("handlers.voice_models.edge_tts_rvc.patch_error", e=e))
                log(traceback.format_exc())
                return False

        return _fn

    @classmethod
    def build_install_plan(cls, model_id: str, ctx: dict) -> InstallPlan:
        mid = str(model_id)
        if cls.is_installed(mid, ctx):
            return InstallPlan(actions=[], already_installed=True, already_installed_status=t("handlers.voice_models.edge_tts_rvc.already_installed"))

        gpu = str((ctx or {}).get("gpu_vendor") or "CPU")
        actions: list[InstallAction] = []

        # Historical behavior: torch only for NVIDIA branch
        if gpu == "NVIDIA":
            actions.append(torch_install_action(ctx, progress=10))

        actions.append(
            InstallAction(
                type="pip",
                description=t("handlers.voice_models.edge_tts_rvc.installing_deps"),
                progress=35,
                packages=["omegaconf"],
            )
        )

        if mid == "low+":
            actions.append(
                InstallAction(
                    type="pip",
                    description=t("handlers.voice_models.edge_tts_rvc.installing_silero"),
                    progress=45,
                    packages=["silero"],
                )
            )

        if gpu == "AMD":
            actions.append(
                InstallAction(
                    type="pip",
                    description=t("handlers.voice_models.edge_tts_rvc.installing_rvc_amd"),
                    progress=70,
                    packages=["tts-with-rvc-onnx[dml]"],
                )
            )
        else:
            actions.append(
                InstallAction(
                    type="pip",
                    description=t("handlers.voice_models.edge_tts_rvc.installing_rvc_nvidia"),
                    progress=70,
                    packages=["tts-with-rvc"],
                )
            )

        actions.append(
            InstallAction(
                type="call",
                description=t("handlers.voice_models.edge_tts_rvc.final_check"),
                progress=90,
                fn=cls._patch_fairseq_configs_call(),
            )
        )

        actions.append(
            InstallAction(
                type="call",
                description=t("handlers.voice_models.edge_tts_rvc.final_check"),
                progress=99,
                fn=lambda **_k: cls.is_installed(mid, ctx),
            )
        )

        return InstallPlan(actions=actions, ok_status=t("handlers.voice_models.edge_tts_rvc.done"))

    @classmethod
    def build_uninstall_plan(cls, model_id: str, ctx: dict) -> InstallPlan:
        gpu = str((ctx or {}).get("gpu_vendor") or "CPU")
        if gpu == "AMD":
            return InstallPlan(
                actions=[
                    pip_uninstall_action(
                        ["tts-with-rvc-onnx"],
                        description=t("handlers.voice_models.edge_tts_rvc.final_check"),
                        progress=20,
                    )
                ],
                ok_status=t("handlers.voice_models.edge_tts_rvc.uninstalled"),
            )

        return InstallPlan(
            actions=[
                pip_uninstall_action(
                    ["tts-with-rvc"],
                    description=t("handlers.voice_models.edge_tts_rvc.final_check"),
                    progress=20,
                )
            ],
            ok_status=t("handlers.voice_models.edge_tts_rvc.uninstalled"),
        )


class EdgeTTS_RVC_Model(IVoiceModel):
    def __init__(self, parent: 'LocalVoice', model_id: str):
        super().__init__(parent, model_id)
        self.tts_rvc_module = None
        self.current_tts_rvc = None
        self.current_silero_model = None
        self.current_silero_sample_rate = 48000

        self._silero_available = False
        self.events = get_event_bus()

    MODEL_CONFIGS = [
        {
            "id": "low",
            "name": "Edge-TTS + RVC",
            "min_vram": 3,
            "rec_vram": 4,
            "gpu_vendor": ["NVIDIA", "AMD"],
            "size_gb": 3,
            "languages": ["Russian", "English"],
            "intents": [t("handlers.voice_models.edge_tts_rvc.models.low.low_intent_fast"), t("handlers.voice_models.edge_tts_rvc.models.low.low_intent_low_reqs")],
            "description": t("handlers.voice_models.edge_tts_rvc.models.low.low_description"),
            "settings": [
                {
                    "key": "device", "label": t("handlers.voice_models.edge_tts_rvc.models.low.device_label"), "type": "combobox",
                    "options": {
                        "values_nvidia": ["dml", "cuda:0", "cpu"],
                        "default_nvidia": "cuda:0",
                        "values_amd": ["dml", "cpu"],
                        "default_amd": "dml",
                        "values_other": ["cpu", "mps:0"],
                        "default_other": "cpu"
                    },
                    "help": t("handlers.voice_models.edge_tts_rvc.models.low.device_help")
                },
                {
                    "key": "is_half", "label": t("handlers.voice_models.edge_tts_rvc.models.low.is_half_label"),
                    "type": "combobox",
                    "options": {"values": ["True", "False"], "default_nvidia": "True", "default_amd": "False", "default_other": "False"},
                    "help": t("handlers.voice_models.edge_tts_rvc.models.low.is_half_help")
                },
                {
                    "key": "f0method", "label": t("handlers.voice_models.edge_tts_rvc.models.low.f0method_label"),
                    "type": "combobox",
                    "options": {
                        "values_nvidia": ["pm", "rmvpe", "crepe", "harvest", "fcpe", "dio"],
                        "default_nvidia": "rmvpe",
                        "values_amd": ["rmvpe", "harvest", "pm", "dio"],
                        "default_amd": "pm",
                        "values_other": ["pm", "rmvpe", "crepe", "harvest", "fcpe", "dio"],
                        "default_other": "pm"
                    },
                    "help": t("handlers.voice_models.edge_tts_rvc.models.low.f0method_help")
                },
                {"key": "pitch", "label": t("handlers.voice_models.edge_tts_rvc.models.low.pitch_label"),
                 "type": "entry", "options": {"default": "6"},
                 "help": t("handlers.voice_models.edge_tts_rvc.models.low.pitch_help")},
                {"key": "use_index_file", "label": t("handlers.voice_models.edge_tts_rvc.models.low.use_index_file_label"),
                 "type": "checkbutton", "options": {"default": True},
                 "help": t("handlers.voice_models.edge_tts_rvc.models.low.use_index_file_help")},
                {"key": "index_rate", "label": t("handlers.voice_models.edge_tts_rvc.models.low.index_rate_label"),
                 "type": "entry", "options": {"default": "0.75"},
                 "help": t("handlers.voice_models.edge_tts_rvc.models.low.index_rate_help")},
                {"key": "protect", "label": t("handlers.voice_models.edge_tts_rvc.models.low.protect_label"),
                 "type": "entry", "options": {"default": "0.33"},
                 "help": t("handlers.voice_models.edge_tts_rvc.models.low.protect_help")},
                {"key": "tts_rate", "label": t("handlers.voice_models.edge_tts_rvc.models.low.tts_rate_label"),
                 "type": "entry", "options": {"default": "0"},
                 "help": t("handlers.voice_models.edge_tts_rvc.models.low.tts_rate_help")},
                {"key": "filter_radius", "label": t("handlers.voice_models.edge_tts_rvc.models.low.filter_radius_label"),
                 "type": "entry", "options": {"default": "3"},
                 "help": t("handlers.voice_models.edge_tts_rvc.models.low.filter_radius_help")},
                {"key": "rms_mix_rate", "label": t("handlers.voice_models.edge_tts_rvc.models.low.rms_mix_rate_label"),
                 "type": "entry", "options": {"default": "0.5"},
                 "help": t("handlers.voice_models.edge_tts_rvc.models.low.rms_mix_rate_help")},
                {"key": "volume", "label": t("handlers.voice_models.edge_tts_rvc.models.low.volume_label"),
                 "type": "entry", "options": {"default": "1.0"},
                 "help": t("handlers.voice_models.edge_tts_rvc.models.low.volume_help")}
            ]
        },
        {
            "id": "low+",
            "name": "Silero + RVC",
            "min_vram": 3,
            "rec_vram": 4,
            "gpu_vendor": ["NVIDIA", "AMD"],
            "size_gb": 3,
            "languages": ["Russian", "English"],
            "intents": [t("handlers.voice_models.edge_tts_rvc.models.low_plus.low_plus_intent_fast"), t("handlers.voice_models.edge_tts_rvc.models.low_plus.low_plus_intent_offline")],
            "description": t("handlers.voice_models.edge_tts_rvc.models.low_plus.low_plus_description"),
            "settings": [
                {"key": "silero_rvc_device", "label": t("handlers.voice_models.edge_tts_rvc.models.low_plus.silero_rvc_device_label"), "type": "combobox",
                 "options": {
                     "values_nvidia": ["dml", "cuda:0", "cpu"],
                     "default_nvidia": "cuda:0",
                     "values_amd": ["dml", "cpu"],
                     "default_amd": "dml",
                     "values_other": ["cpu", "dml"],
                     "default_other": "cpu"
                 },
                 "help": t("handlers.voice_models.edge_tts_rvc.models.low_plus.silero_rvc_device_help")},
                {"key": "silero_device", "label": t("handlers.voice_models.edge_tts_rvc.models.low_plus.silero_device_label"), "type": "combobox",
                 "options": {"values_nvidia": ["cuda", "cpu"], "default_nvidia": "cuda", "values_amd": ["cpu"], "default_amd": "cpu", "values_other": ["cpu"], "default_other": "cpu"},
                 "help": t("handlers.voice_models.edge_tts_rvc.models.low_plus.silero_device_help")},
                {"key": "silero_rvc_is_half", "label": t("handlers.voice_models.edge_tts_rvc.models.low_plus.silero_rvc_is_half_label"), "type": "combobox",
                 "options": {"values": ["True", "False"], "default_nvidia": "True", "default_amd": "False", "default_other": "False"},
                 "help": t("handlers.voice_models.edge_tts_rvc.models.low_plus.silero_rvc_is_half_help")},
                {"key": "silero_rvc_f0method", "label": t("handlers.voice_models.edge_tts_rvc.models.low_plus.silero_rvc_f0method_label"), "type": "combobox",
                 "options": {"values_nvidia": ["pm", "rmvpe", "crepe", "harvest", "fcpe", "dio"], "default_nvidia": "rmvpe",
                             "values_amd": ["rmvpe", "harvest", "pm", "dio"], "default_amd": "pm",
                             "values_other": ["pm", "rmvpe", "harvest", "dio"], "default_other": "pm"},
                 "help": t("handlers.voice_models.edge_tts_rvc.models.low_plus.silero_rvc_f0method_help")},
                {"key": "silero_rvc_pitch", "label": t("handlers.voice_models.edge_tts_rvc.models.low_plus.silero_rvc_pitch_label"), "type": "entry", "options": {"default": "6"},
                 "help": t("handlers.voice_models.edge_tts_rvc.models.low_plus.silero_rvc_pitch_help")},
                {"key": "silero_rvc_use_index_file", "label": t("handlers.voice_models.edge_tts_rvc.models.low_plus.silero_rvc_use_index_file_label"), "type": "checkbutton", "options": {"default": True},
                 "help": t("handlers.voice_models.edge_tts_rvc.models.low_plus.silero_rvc_use_index_file_help")},
                {"key": "silero_rvc_index_rate", "label": t("handlers.voice_models.edge_tts_rvc.models.low_plus.silero_rvc_index_rate_label"), "type": "entry", "options": {"default": "0.75"},
                 "help": t("handlers.voice_models.edge_tts_rvc.models.low_plus.silero_rvc_index_rate_help")},
                {"key": "silero_rvc_protect", "label": t("handlers.voice_models.edge_tts_rvc.models.low_plus.silero_rvc_protect_label"), "type": "entry", "options": {"default": "0.33"},
                 "help": t("handlers.voice_models.edge_tts_rvc.models.low_plus.silero_rvc_protect_help")},
                {"key": "silero_rvc_filter_radius", "label": t("handlers.voice_models.edge_tts_rvc.models.low_plus.silero_rvc_filter_radius_label"), "type": "entry", "options": {"default": "3"},
                 "help": t("handlers.voice_models.edge_tts_rvc.models.low_plus.silero_rvc_filter_radius_help")},
                {"key": "silero_rvc_rms_mix_rate", "label": t("handlers.voice_models.edge_tts_rvc.models.low_plus.silero_rvc_rms_mix_rate_label"), "type": "entry", "options": {"default": "0.5"},
                 "help": t("handlers.voice_models.edge_tts_rvc.models.low_plus.silero_rvc_rms_mix_rate_help")},
                {"key": "silero_sample_rate", "label": t("handlers.voice_models.edge_tts_rvc.models.low_plus.silero_sample_rate_label"), "type": "combobox",
                 "options": {"values": ["48000", "24000", "16000"], "default": "48000"},
                 "help": t("handlers.voice_models.edge_tts_rvc.models.low_plus.silero_sample_rate_help")},
                {"key": "silero_put_accent", "label": t("handlers.voice_models.edge_tts_rvc.models.low_plus.silero_put_accent_label"), "type": "checkbutton", "options": {"default": True},
                 "help": t("handlers.voice_models.edge_tts_rvc.models.low_plus.silero_put_accent_help")},
                {"key": "silero_put_yo", "label": t("handlers.voice_models.edge_tts_rvc.models.low_plus.silero_put_yo_label"), "type": "checkbutton", "options": {"default": True},
                 "help": t("handlers.voice_models.edge_tts_rvc.models.low_plus.silero_put_yo_help")},
                {"key": "volume", "label": t("handlers.voice_models.edge_tts_rvc.models.low_plus.volume_label"), "type": "entry", "options": {"default": "1.0"},
                 "help": t("handlers.voice_models.edge_tts_rvc.models.low_plus.volume_help")}
            ]
        }
    ]

    def get_model_configs(self) -> List[Dict[str, Any]]:
        return self.MODEL_CONFIGS

    def _load_module(self):
        if self.tts_rvc_module is not None:
            return

        if getattr(self, "_import_attempted", False):
            return

        self._import_attempted = True
        self._silero_available = False

        libs_path_abs = os.path.abspath("Lib")
        if libs_path_abs not in sys.path:
            sys.path.insert(0, libs_path_abs)

        # Try primary import
        try:
            from tts_with_rvc import TTS_RVC
            self.tts_rvc_module = TTS_RVC
        except Exception:
            # Fallback for some AMD builds (best-effort)
            try:
                from tts_with_rvc_onnx import TTS_RVC  # type: ignore
                self.tts_rvc_module = TTS_RVC
            except Exception:
                self.tts_rvc_module = None
                return

        try:
            from silero import silero_tts  # noqa: F401
            self._silero_available = True
        except Exception:
            self._silero_available = False

    def get_display_name(self) -> str:
        return "EdgeTTS+RVC / Silero+RVC"

    def cleanup_state(self):
        super().cleanup_state()
        self.current_tts_rvc = None
        self.current_silero_model = None
        self.tts_rvc_module = None
        self._silero_available = False
        self._import_attempted = False
        logger.info("Состояние для обработчика EdgeTTS/Silero+RVC сброшено.")

    def initialize(self, init: bool = False) -> bool:
        current_mode = self.parent.current_model_id
        if self.initialized and self.initialized_for == current_mode:
            return True

        logger.info(f"Запрос на инициализацию обработчика в режиме: '{current_mode}'")

        if self.tts_rvc_module is None:
            self._load_module()

        if self.current_tts_rvc is None:
            logger.info("Инициализация базового компонента RVC...")
            if self.tts_rvc_module is None:
                logger.error("Модуль tts_with_rvc не установлен.")
                self.initialized = False
                self.initialized_for = None
                return False

            settings = self.parent.load_model_settings(current_mode)

            if current_mode == "low+":
                device = settings.get("silero_rvc_device", "cuda:0" if self.parent.provider == "NVIDIA" else "dml")
                f0_method = settings.get("silero_rvc_f0method", "rmvpe" if self.parent.provider == "NVIDIA" else "pm")
            else:
                device = settings.get("device", "cuda:0" if self.parent.provider == "NVIDIA" else "dml")
                f0_method = settings.get("f0method", "rmvpe" if self.parent.provider == "NVIDIA" else "pm")

            is_nvidia = self.parent.provider in ["NVIDIA"]
            model_ext = "pth" if is_nvidia else "onnx"
            default_model_path = os.path.join("Models", f"Mila.{model_ext}")

            model_path_to_use = (
                self.parent.pth_path
                if getattr(self.parent, "pth_path", None) and os.path.exists(self.parent.pth_path)
                else default_model_path
            )
            if not os.path.exists(model_path_to_use):
                logger.error(f"Не найден файл RVC модели: {model_path_to_use}")
                self.initialized = False
                self.initialized_for = None
                return False

            self.current_tts_rvc = self.tts_rvc_module(model_path=model_path_to_use, device=device, f0_method=f0_method)
            self._adjust_sampling_rate_for_amd()
            logger.info(f"Базовый компонент RVC инициализирован с device={device}, f0_method={f0_method}")

        if self.parent.voice_language == "ru":
            self.current_tts_rvc.set_voice("ru-RU-SvetlanaNeural")
        else:
            self.current_tts_rvc.set_voice("en-US-MichelleNeural")

        if current_mode == "low+":
            if self.current_silero_model is None:
                logger.info("Требуется режим 'low+', инициализация компонента Silero...")
                try:
                    settings = self.parent.load_model_settings(current_mode)
                    silero_device = settings.get("silero_device", "cuda" if self.parent.provider == "NVIDIA" else "cpu")
                    self.current_silero_sample_rate = int(settings.get("silero_sample_rate", 48000))
                    language = "en" if self.parent.voice_language == "en" else "ru"
                    model_id_silero = "v3_en" if language == "en" else "v5_ru"

                    from silero import silero_tts
                    model, _ = silero_tts(language=language, speaker=model_id_silero)
                    model.to(silero_device)
                    self.current_silero_model = model
                    logger.info("Компонент Silero для 'low+' успешно инициализирован.")
                except Exception as e:
                    logger.error(f"Ошибка инициализации компонента Silero: {e}", exc_info=True)
                    self.initialized = False
                    self.initialized_for = None
                    return False
        else:
            if self.current_silero_model is not None:
                logger.info("Переключение в режим без Silero. Выгрузка компонента Silero...")
                self.current_silero_model = None
                import gc
                gc.collect()

        is_ready = self.current_tts_rvc is not None
        if current_mode == "low+":
            is_ready = is_ready and self.current_silero_model is not None

        if not is_ready:
            logger.error(f"Не все компоненты для модели '{current_mode}' удалось инициализировать.")
            self.initialized = False
            self.initialized_for = None
            return False

        self.initialized = True
        self.initialized_for = current_mode

        if init:
            init_text = f"Инициализация модели {current_mode}" if self.parent.voice_language == "ru" else f"{current_mode} Model Initialization"
            logger.info(f"Выполнение тестового прогона для {current_mode}...")
            try:
                results = self.events.emit_and_wait(Events.Core.GET_EVENT_LOOP, timeout=1.0)
                main_loop = results[0] if results else None
                if not main_loop or not main_loop.is_running():
                    raise RuntimeError("Главный цикл событий asyncio недоступен.")

                future = asyncio.run_coroutine_threadsafe(self.voiceover(init_text), main_loop)
                result_path = future.result(timeout=3600)

                if not result_path or not os.path.exists(result_path) or os.path.getsize(result_path) == 0:
                    logger.error("Тестовый прогон не создал аудиофайл — инициализация неуспешна.")
                    self.initialized = False
                    self.initialized_for = None
                    return False

                logger.info(f"Тестовый прогон для {current_mode} успешно завершен.")
            except Exception as e:
                logger.error(f"Ошибка во время тестового прогона модели {current_mode}: {e}", exc_info=True)
                self.initialized = False
                self.initialized_for = None
                return False

        return self.initialized
    
    def _maybe_move_to_output(self, produced_path: Optional[str], output_file: Optional[str]) -> Optional[str]:
        if not produced_path or not os.path.exists(produced_path):
            return produced_path
        if not output_file:
            return produced_path

        out = os.path.abspath(str(output_file))
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)

        try:
            if os.path.abspath(produced_path) == out:
                return produced_path
            if os.path.exists(out):
                try:
                    os.remove(out)
                except Exception:
                    pass
            os.replace(produced_path, out)
            return out
        except Exception:
            return produced_path

    def _update_parent_paths(self, character=None):
        voice_paths = get_character_voice_paths(character, self.parent.provider)
        self.parent.pth_path = voice_paths['pth_path']
        self.parent.index_path = voice_paths['index_path']
        self.parent.clone_voice_filename = voice_paths['clone_voice_filename']
        self.parent.clone_voice_text = voice_paths['clone_voice_text']
        self.parent.current_character_name = voice_paths['character_name']
        logger.info(f"Обновлены пути в parent для персонажа: {voice_paths['character_name']}")

    async def voiceover(self, text: str, character: Optional[Any] = None, **kwargs) -> Optional[str]:
        current_mode = self.parent.current_model_id
        if not self.initialized or self.initialized_for != current_mode:
            raise Exception(f"Обработчик не инициализирован для режима '{current_mode}'.")

        self._update_parent_paths(character)

        if current_mode == "low":
            return await self._voiceover_edge_tts_rvc(
                text,
                character,
                output_file=kwargs.get("output_file"),
                settings_model_id=kwargs.get("settings_model_id"),
                TEST_WITH_DONE_AUDIO=kwargs.get("TEST_WITH_DONE_AUDIO"),
            )
        if current_mode == "low+":
            return await self._voiceover_silero_rvc(text, character, output_file=kwargs.get("output_file"))

        raise ValueError(f"Обработчик вызван с неизвестным режимом: {current_mode}")

    async def apply_rvc_to_file(
        self,
        filepath: str,
        character: Optional[Any] = None,
        pitch: float = 0,
        index_rate: float = 0.75,
        protect: float = 0.33,
        filter_radius: int = 3,
        rms_mix_rate: float = 0.5,
        is_half: bool = True,
        f0method: Optional[str] = None,
        use_index_file: bool = True,
        volume: str = "1.0",
        original_model_id: Optional[str] = None
    ) -> Optional[str]:
        if not self.initialized:
            logger.info("Инициализация RVC компонента на лету...")
            if not self.initialize(init=False):
                logger.error("Не удалось инициализировать RVC компонент.")
                return None

        logger.info(f"Вызов RVC для файла: {filepath}")

        try:
            self._update_parent_paths(character)

            voice_paths = get_character_voice_paths(character, self.parent.provider)
            model_path = voice_paths['pth_path']
            index_path = voice_paths['index_path']

            inference_params = {
                "pitch": pitch,
                "index_rate": index_rate,
                "protect": protect,
                "filter_radius": filter_radius,
                "rms_mix_rate": rms_mix_rate
            }

            if self.parent.provider == "NVIDIA":
                inference_params["is_half"] = is_half

            if f0method:
                inference_params["f0method"] = f0method

            if use_index_file and index_path and os.path.exists(index_path):
                self.current_tts_rvc.set_index_path(index_path)
            else:
                self.current_tts_rvc.set_index_path("")

            self._adjust_sampling_rate_for_amd()

            if os.path.abspath(model_path) != os.path.abspath(self.current_tts_rvc.current_model):
                if self.parent.provider in ["AMD"] and hasattr(self.current_tts_rvc, 'set_model'):
                    self.current_tts_rvc.set_model(model_path)
                    logger.info(f'RVC модель изменена на: {model_path}')
                else:
                    self.current_tts_rvc.current_model = model_path
                    logger.info(f'RVC модель изменена на: {model_path}')

            output_file_rvc = self.current_tts_rvc.voiceover_file(input_path=filepath, **inference_params)
            if not output_file_rvc or not os.path.exists(output_file_rvc) or os.path.getsize(output_file_rvc) == 0:
                return None

            stereo_output_file = output_file_rvc.replace(".wav", "_stereo.wav")
            converted_file = self.parent.convert_wav_to_stereo(
                output_file_rvc,
                stereo_output_file,
                atempo=1.0,
                volume=volume,
            )

            if converted_file and os.path.exists(converted_file):
                final_output_path = stereo_output_file
                try:
                    os.remove(output_file_rvc)
                except OSError:
                    pass
            else:
                final_output_path = output_file_rvc

            return final_output_path

        except Exception as error:
            traceback.print_exc()
            logger.info(f"Ошибка при применении RVC к файлу: {error}")
            return None

    async def _voiceover_edge_tts_rvc(
        self,
        text,
        character=None,
        TEST_WITH_DONE_AUDIO: str = None,
        settings_model_id: Optional[str] = None,
        output_file: Optional[str] = None,
    ):
        if self.current_tts_rvc is None:
            raise Exception("Компонент RVC не инициализирован.")
        try:
            config_id = settings_model_id if settings_model_id else self.parent.current_model_id
            settings = self.parent.load_model_settings(config_id)
            logger.info(f"RVC использует конфигурацию от модели: '{config_id}'")

            voice_paths = get_character_voice_paths(character, self.parent.provider)
            model_path = voice_paths["pth_path"]
            index_path = voice_paths["index_path"]
            character_name = voice_paths["character_name"]

            pitch = float(settings.get("pitch", 0))
            if character_name == "Player" and config_id != "medium+low":
                pitch = -12

            index_rate = float(settings.get("index_rate", 0.75))
            protect = float(settings.get("protect", 0.33))
            filter_radius = int(settings.get("filter_radius", 3))
            rms_mix_rate = float(settings.get("rms_mix_rate", 0.5))
            is_half = str(settings.get("is_half", "True")).lower() == "true"
            use_index_file = settings.get("use_index_file", True)
            f0method_override = settings.get("f0method", None)
            tts_rate = int(settings.get("tts_rate", 0)) if config_id != "medium+low" else 0
            vol = str(settings.get("volume", "1.0"))

            if use_index_file and index_path and os.path.exists(index_path):
                self.current_tts_rvc.set_index_path(index_path)
            else:
                self.current_tts_rvc.set_index_path("")

            if self.parent.provider in ["NVIDIA"]:
                inference_params = {
                    "pitch": pitch,
                    "index_rate": index_rate,
                    "protect": protect,
                    "filter_radius": filter_radius,
                    "rms_mix_rate": rms_mix_rate,
                    "is_half": is_half,
                }
            else:
                inference_params = {
                    "pitch": pitch,
                    "index_rate": index_rate,
                    "protect": protect,
                    "filter_radius": filter_radius,
                    "rms_mix_rate": rms_mix_rate,
                }

            if f0method_override:
                inference_params["f0method"] = f0method_override

            current_model_abs = os.path.abspath(self.current_tts_rvc.current_model)
            model_path_abs = os.path.abspath(model_path)

            if current_model_abs != model_path_abs:
                if self.parent.provider in ["AMD"] and hasattr(self.current_tts_rvc, "set_model"):
                    self.current_tts_rvc.set_model(model_path)
                else:
                    self.current_tts_rvc.current_model = model_path
                logger.info(f"RVC модель изменена на: {model_path}")

            self._adjust_sampling_rate_for_amd()

            if not TEST_WITH_DONE_AUDIO:
                inference_params["tts_rate"] = tts_rate
                output_file_rvc = self.current_tts_rvc(text=text, **inference_params)
            else:
                output_file_rvc = self.current_tts_rvc.voiceover_file(input_path=TEST_WITH_DONE_AUDIO, **inference_params)

            if not output_file_rvc or not os.path.exists(output_file_rvc) or os.path.getsize(output_file_rvc) == 0:
                return None

            stereo_output_file = output_file_rvc.replace(".wav", "_stereo.wav")
            converted_file = self.parent.convert_wav_to_stereo(
                output_file_rvc,
                stereo_output_file,
                atempo=1.0,
                volume=vol,
            )

            if converted_file and os.path.exists(converted_file):
                final_output_path = stereo_output_file
                try:
                    os.remove(output_file_rvc)
                except OSError:
                    pass
            else:
                final_output_path = output_file_rvc

            final_output_path = self._maybe_move_to_output(final_output_path, output_file)

            try:
                res_conn = self.events.emit_and_wait(Events.Server.GET_GAME_CONNECTION)
                connected_to_game = bool(res_conn and res_conn[0])
            except Exception:
                connected_to_game = False

            if connected_to_game and TEST_WITH_DONE_AUDIO is None and final_output_path:
                self.events.emit(Events.Server.SET_PATCH_TO_SOUND_FILE, final_output_path)

            return final_output_path

        except Exception as error:
            traceback.print_exc()
            logger.info(f"Ошибка при создании озвучки с Edge-TTS + RVC: {error}")
            return None

    def _preprocess_text_to_ssml(self, text: str, character_name: str):
        lang = self.parent.voice_language
        defaults = {'en': {'pitch': 6, 'speaker': "en_88"}, 'ru': {'pitch': 2, 'speaker': "kseniya"}}
        lang_defaults = defaults.get(lang, defaults['en'])
        char_params = {
            'en': {"CappieMita": (6, "en_26"), "CrazyMita": (6, "en_60"), "GhostMita": (6, "en_33"), "Mila": (6, "en_88"), "MitaKind": (3, "en_33"), "ShorthairMita": (6, "en_60"), "SleepyMita": (6, "en_33"), "TinyMita": (2, "en_60"), "Player": (0, "en_27")},
            'ru': {"CappieMita": (6, "kseniya"), "MitaKind": (1, "kseniya"), "ShorthairMita": (2, "kseniya"), "CrazyMita": (2, "kseniya"), "Mila": (2, "kseniya"), "TinyMita": (-3, "baya"), "SleepyMita": (2, "baya"), "GhostMita": (1, "baya"), "Player": (0, "aidar")}
        }
        character_rvc_pitch, character_speaker = lang_defaults['pitch'], lang_defaults['speaker']
        character_short_name = character_name
        current_lang_params = char_params.get(lang, char_params['en'])
        if specific_params := current_lang_params.get(character_short_name):
            character_rvc_pitch, character_speaker = specific_params

        text = escape(re.sub(r'<[^>]*>', '', text))

        pattern = re.compile(
            r'\b([MmМм])([IiИи])([A-Za-zА-Яа-я]{2,3})\b',
            re.IGNORECASE
        )

        def put_plus(match: re.Match) -> str:
            return f'{match.group(1)}+{match.group(2)}{match.group(3)}'

        text = pattern.sub(put_plus, text)

        parts = re.split(r'([.!?]+[^A-Za-zА-Яа-я0-9_]*)(\s+)', text.strip())
        processed_text = ""
        i = 0
        while i < len(parts):
            if text_part := parts[i]:
                processed_text += text_part
            if i + 2 < len(parts):
                if punctuation_part := parts[i + 1]:
                    processed_text += punctuation_part
                if (whitespace_part := parts[i + 2]) and i + 3 < len(parts) and parts[i + 3]:
                    processed_text += ' <break time="300ms"/> '
                elif whitespace_part:
                    processed_text += whitespace_part
            i += 3

        ssml_content = processed_text.strip()
        ssml_output = f'<speak><p>{ssml_content}</p></speak>' if ssml_content else '<speak></speak>'
        return ssml_output, character_rvc_pitch, character_speaker

    def _adjust_sampling_rate_for_amd(self):
        if self.parent.provider != "AMD":
            return

        char = getattr(self.parent, "current_character_name", "Mila")
        sr, hop = (48000, 512) if char == "ShorthairMita" else (40000, 512)

        if hasattr(self.current_tts_rvc, "set_sampling_params"):
            self.current_tts_rvc.set_sampling_params(sr, hop)
            self.current_tts_rvc.sampling_rate = sr
            logger.info(f"[AMD] SR patched for '{char}': {sr}/{hop}")
        else:
            logger.warning("set_sampling_params() not found in TTS_RVC – SR patch skipped.")

    async def _voiceover_silero_rvc(self, text, character=None, output_file: Optional[str] = None):
        if self.current_silero_model is None or self.current_tts_rvc is None:
            raise Exception("Компоненты Silero или RVC не инициализированы для режима low+.")

        self.parent.current_character = character if character is not None else getattr(self.parent, "current_character", None)
        temp_wav = None
        try:
            voice_paths = get_character_voice_paths(character, self.parent.provider)
            character_name = voice_paths["character_name"]

            ssml_text, character_base_rvc_pitch, character_speaker = self._preprocess_text_to_ssml(text, character_name)
            settings = self.parent.load_model_settings("low+")

            audio_tensor = self.current_silero_model.apply_tts(
                ssml_text=ssml_text,
                speaker=character_speaker,
                sample_rate=self.current_silero_sample_rate,
                put_accent=settings.get("silero_put_accent", True),
                put_yo=settings.get("silero_put_yo", True),
                put_stress_homo=settings.get("silero_put_accent", True),
                put_yo_homo=settings.get("silero_put_yo", True),
            )

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_wav_file:
                temp_wav = temp_wav_file.name
            sf.write(temp_wav, audio_tensor.cpu().numpy(), self.current_silero_sample_rate)

            if not os.path.exists(temp_wav) or os.path.getsize(temp_wav) == 0:
                return None

            base_rvc_pitch_from_settings = float(settings.get("silero_rvc_pitch", 6))
            final_rvc_pitch = base_rvc_pitch_from_settings - (6 - character_base_rvc_pitch)
            vol = str(settings.get("volume", "1.0"))

            final_output_path = await self.apply_rvc_to_file(
                filepath=temp_wav,
                character=character,
                pitch=final_rvc_pitch,
                index_rate=float(settings.get("silero_rvc_index_rate", 0.75)),
                protect=float(settings.get("silero_rvc_protect", 0.33)),
                filter_radius=int(settings.get("silero_rvc_filter_radius", 3)),
                rms_mix_rate=float(settings.get("silero_rvc_rms_mix_rate", 0.5)),
                is_half=str(settings.get("silero_rvc_is_half", "True")).lower() == "true" if self.parent.provider == "NVIDIA" else True,
                f0method=settings.get("silero_rvc_f0method", None),
                use_index_file=settings.get("silero_rvc_use_index_file", True),
                volume=vol,
            )

            final_output_path = self._maybe_move_to_output(final_output_path, output_file)

            try:
                res_conn = self.events.emit_and_wait(Events.Server.GET_GAME_CONNECTION)
                connected_to_game = bool(res_conn and res_conn[0])
            except Exception:
                connected_to_game = False

            if connected_to_game and final_output_path:
                self.events.emit(Events.Server.SET_PATCH_TO_SOUND_FILE, final_output_path)

            return final_output_path

        except Exception as error:
            traceback.print_exc()
            logger.info(f"Ошибка при создании озвучки с Silero + RVC: {error}")
            return None
        finally:
            if temp_wav and os.path.exists(temp_wav):
                try:
                    os.remove(temp_wav)
                except OSError:
                    pass