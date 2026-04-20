import os
import traceback
import tempfile
import re
from xml.sax.saxutils import escape
from typing import Optional, Any, List, Dict

import soundfile as sf

from .base_model import IVoiceModel
from main_logger import logger
from managers.backend_manager import Backend, BackendManager
from utils import getTranslationVariant as _, get_character_voice_paths

from core.install_types import InstallPlan, InstallAction
from core.install_requirements import InstallRequirement, check_requirements


class EdgeTTSRVCOnnxInstallSpec:
    @classmethod
    def supported_model_ids(cls) -> list[str]:
        return ["low", "low+"]

    @classmethod
    def title(cls, model_id: str) -> str:
        return _("Установка локальной модели (ONNX): ", "Installing local model (ONNX): ") + str(model_id)

    @classmethod
    def requirements(cls, model_id: str, ctx: dict) -> list[InstallRequirement]:
        mid = str(model_id)
        req: list[InstallRequirement] = [
            InstallRequirement(id="omegaconf", kind="python_dist", spec="omegaconf", required=True),
            InstallRequirement(id="tts_rvc_pkg", kind="python_dist", spec="tts-with-rvc-onnx[dml]", required=True),
        ]
        if mid == "low+":
            req.append(InstallRequirement(id="silero", kind="python_dist", spec="silero", required=True))
        return req

    @classmethod
    def is_installed(cls, model_id: str, ctx: dict) -> bool:
        st = check_requirements(cls.requirements(model_id, ctx), ctx=ctx)
        return bool(st.get("ok"))

    @classmethod
    def _extra_for(cls, model_id: str, ctx: dict) -> str:
        return {"low": "tts-edge-rvc-amd", "low+": "tts-silero-rvc-amd"}[str(model_id)]

    @classmethod
    def build_install_plan(cls, model_id: str, ctx: dict) -> InstallPlan:
        mid = str(model_id)
        if cls.is_installed(mid, ctx):
            return InstallPlan(
                actions=[],
                already_installed=True,
                already_installed_status=_("Уже установлено", "Already installed"),
            )
        extra = cls._extra_for(mid, ctx)
        removed_extra = {"low": "tts-edge-rvc", "low+": "tts-silero-rvc"}[mid]
        return InstallPlan(
            required_extras=[extra],
            removed_extras=[removed_extra],
            actions=[
                InstallAction(
                    type="call",
                    description=_("Проверка установки...", "Final check..."),
                    progress=99,
                    fn=lambda **_k: cls.is_installed(mid, ctx),
                )
            ],
            ok_status=_("Готово", "Done"),
        )

    @classmethod
    def build_uninstall_plan(cls, model_id: str, ctx: dict) -> InstallPlan:
        return InstallPlan(
            actions=[],
            removed_extras=[cls._extra_for(str(model_id), ctx)],
            ok_status=_("Удалено", "Uninstalled"),
        )


class EdgeTTS_RVC_Onnx_Model(IVoiceModel):
    """ONNX/DirectML вариант EdgeTTS+RVC — для AMD и прочих GPU без CUDA."""

    REQUIRED_BACKEND = Backend.ONNX

    def __init__(self, parent: "LocalVoice", model_id: str):
        super().__init__(parent, model_id)
        self.tts_rvc_module = None
        self.current_tts_rvc = None
        self.current_silero_model = None
        self.current_silero_sample_rate = 48000
        self._silero_available = False

    MODEL_CONFIGS = [
        {
            "id": "low",
            "name": "Edge-TTS + RVC (ONNX)",
            "min_vram": 3,
            "rec_vram": 4,
            "gpu_vendor": ["AMD"],
            "size_gb": 3,
            "languages": ["Russian", "English"],
            "intents": [_("Быстро", "Fast"), _("Низкие требования", "Low reqs")],
            "description": _(
                "Быстрая модель: Edge-TTS + RVC через DirectML (ONNX). Для AMD и Intel GPU.",
                "Fast pipeline: Edge-TTS + RVC via DirectML (ONNX). For AMD and Intel GPU.",
            ),
            "settings": [
                {
                    "key": "device", "label": _("Устройство RVC", "RVC Device"), "type": "combobox",
                    "options": {"values": ["dml", "cpu"], "default": "dml"},
                    "help": _(
                        "Устройство для RVC: 'dml' — DirectML (AMD/Intel); 'cpu' — процессор.",
                        "Compute device for RVC: 'dml' — DirectML (AMD/Intel); 'cpu' — CPU.",
                    ),
                },
                {
                    "key": "f0method", "label": _("Метод F0 (RVC)", "F0 Method (RVC)"), "type": "combobox",
                    "options": {"values": ["rmvpe", "harvest", "pm", "dio"], "default": "rmvpe"},
                    "help": _("Алгоритм извлечения F0.", "F0 extraction algorithm."),
                },
                {"key": "pitch", "label": _("Высота голоса RVC (пт)", "RVC Pitch (semitones)"),
                 "type": "entry", "options": {"default": "6"},
                 "help": _("Смещение высоты в полутонах.", "Pitch shift in semitones.")},
                {"key": "use_index_file", "label": _("Исп. .index файл (RVC)", "Use .index file (RVC)"),
                 "type": "checkbutton", "options": {"default": True},
                 "help": _("Использовать .index для лучшего совпадения тембра.", "Use .index to better match voice timbre.")},
                {"key": "index_rate", "label": _("Соотношение индекса RVC", "RVC Index Rate"),
                 "type": "entry", "options": {"default": "0.75"}},
                {"key": "protect", "label": _("Защита согласных (RVC)", "Consonant Protection (RVC)"),
                 "type": "entry", "options": {"default": "0.33"}},
                {"key": "tts_rate", "label": _("Скорость TTS (%)", "TTS Speed (%)"),
                 "type": "entry", "options": {"default": "0"}},
                {"key": "filter_radius", "label": _("Радиус фильтра F0 (RVC)", "F0 Filter Radius (RVC)"),
                 "type": "entry", "options": {"default": "3"}},
                {"key": "rms_mix_rate", "label": _("Смешивание RMS (RVC)", "RMS Mixing (RVC)"),
                 "type": "entry", "options": {"default": "0.5"}},
                {"key": "volume", "label": _("Громкость (volume)", "Volume"),
                 "type": "entry", "options": {"default": "1.0"}},
            ],
        },
        {
            "id": "low+",
            "name": "Silero + RVC (ONNX)",
            "min_vram": 3,
            "rec_vram": 4,
            "gpu_vendor": ["AMD"],
            "size_gb": 3,
            "languages": ["Russian", "English"],
            "intents": [_("Быстро", "Fast"), _("Локальный синтез", "Offline synth")],
            "description": _(
                "Silero + RVC через DirectML (ONNX). Для AMD и Intel GPU.",
                "Silero + RVC via DirectML (ONNX). For AMD and Intel GPU.",
            ),
            "settings": [
                {"key": "silero_rvc_device", "label": _("Устройство RVC", "RVC Device"), "type": "combobox",
                 "options": {"values": ["dml", "cpu"], "default": "dml"}},
                {"key": "silero_device", "label": _("Устройство Silero", "Silero Device"), "type": "combobox",
                 "options": {"values": ["cpu"], "default": "cpu"}},
                {"key": "silero_rvc_is_half", "label": _("Half-precision RVC", "Half-precision RVC"), "type": "combobox",
                 "options": {"values": ["True", "False"], "default": "False"}},
                {"key": "silero_rvc_f0method", "label": _("Метод F0 (RVC)", "F0 Method (RVC)"), "type": "combobox",
                 "options": {"values": ["rmvpe", "harvest", "pm", "dio"], "default": "rmvpe"}},
                {"key": "silero_rvc_pitch", "label": _("Высота голоса RVC (пт)", "RVC Pitch (semitones)"),
                 "type": "entry", "options": {"default": "6"}},
                {"key": "silero_rvc_use_index_file", "label": _("Исп. .index файл (RVC)", "Use .index file (RVC)"),
                 "type": "checkbutton", "options": {"default": True}},
                {"key": "silero_rvc_index_rate", "label": _("Соотношение индекса RVC", "RVC Index Rate"),
                 "type": "entry", "options": {"default": "0.75"}},
                {"key": "silero_rvc_protect", "label": _("Защита согласных (RVC)", "Consonant Protection (RVC)"),
                 "type": "entry", "options": {"default": "0.33"}},
                {"key": "silero_rvc_filter_radius", "label": _("Радиус фильтра F0 (RVC)", "F0 Filter Radius (RVC)"),
                 "type": "entry", "options": {"default": "3"}},
                {"key": "silero_rvc_rms_mix_rate", "label": _("Смешивание RMS (RVC)", "RMS Mixing (RVC)"),
                 "type": "entry", "options": {"default": "0.5"}},
                {"key": "silero_sample_rate", "label": _("Частота Silero", "Silero Sample Rate"), "type": "combobox",
                 "options": {"values": ["48000", "24000", "16000"], "default": "48000"}},
                {"key": "silero_put_accent", "label": _("Акценты Silero", "Silero Accents"),
                 "type": "checkbutton", "options": {"default": True}},
                {"key": "silero_put_yo", "label": _("Буква Ё Silero", "Silero Letter Yo"),
                 "type": "checkbutton", "options": {"default": True}},
                {"key": "volume", "label": _("Громкость (volume)", "Volume"),
                 "type": "entry", "options": {"default": "1.0"}},
            ],
        },
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
        try:
            from tts_with_rvc_onnx import TTS_RVC
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
        return "EdgeTTS+RVC (ONNX) / Silero+RVC (ONNX)"

    def cleanup_state(self):
        super().cleanup_state()
        self.current_tts_rvc = None
        self.current_silero_model = None
        self.tts_rvc_module = None
        self._silero_available = False
        self._import_attempted = False

    def _adjust_sampling_rate(self):
        char = getattr(self.parent, "current_character_name", "Mila")
        sr, hop = (48000, 512) if char == "ShorthairMita" else (40000, 512)
        if hasattr(self.current_tts_rvc, "set_sampling_params"):
            self.current_tts_rvc.set_sampling_params(sr, hop)
            self.current_tts_rvc.sampling_rate = sr
            logger.info(f"[ONNX] SR patched for '{char}': {sr}/{hop}")

    def initialize(self, init: bool = False) -> bool:
        current_mode = self.parent.current_model_id
        if self.initialized and self.initialized_for == current_mode:
            return True

        if self.tts_rvc_module is None:
            self._load_module()

        if self.current_tts_rvc is None:
            if self.tts_rvc_module is None:
                logger.error("Модуль tts_with_rvc_onnx не установлен.")
                return False

            settings = self.parent.load_model_settings(current_mode)

            if current_mode == "low+":
                device = settings.get("silero_rvc_device", "dml")
                f0_method = settings.get("silero_rvc_f0method", "rmvpe")
            else:
                device = settings.get("device", "dml")
                f0_method = settings.get("f0method", "rmvpe")

            default_model_path = os.path.join("Models", "Mila.onnx")
            model_path_to_use = (
                self.parent.pth_path
                if getattr(self.parent, "pth_path", None) and os.path.exists(self.parent.pth_path)
                else default_model_path
            )
            if not os.path.exists(model_path_to_use):
                logger.error(f"Не найден файл RVC модели: {model_path_to_use}")
                return False

            self.current_tts_rvc = self.tts_rvc_module(model_path=model_path_to_use, device=device, f0_method=f0_method)
            self._adjust_sampling_rate()
            logger.info(f"RVC (ONNX) инициализирован с device={device}, f0_method={f0_method}")

        if self.parent.voice_language == "ru":
            self.current_tts_rvc.set_voice("ru-RU-SvetlanaNeural")
        else:
            self.current_tts_rvc.set_voice("en-US-MichelleNeural")

        if current_mode == "low+":
            if self.current_silero_model is None:
                try:
                    settings = self.parent.load_model_settings(current_mode)
                    silero_device = settings.get("silero_device", "cpu")
                    self.current_silero_sample_rate = int(settings.get("silero_sample_rate", 48000))
                    language = "en" if self.parent.voice_language == "en" else "ru"
                    model_id_silero = "v3_en" if language == "en" else "v5_ru"
                    from silero import silero_tts
                    model, _ = silero_tts(language=language, speaker=model_id_silero)
                    model.to(silero_device)
                    self.current_silero_model = model
                except Exception as e:
                    logger.error(f"Ошибка инициализации Silero: {e}", exc_info=True)
                    self.initialized = False
                    return False
        else:
            if self.current_silero_model is not None:
                self.current_silero_model = None

        is_ready = self.current_tts_rvc is not None
        if current_mode == "low+":
            is_ready = is_ready and self.current_silero_model is not None

        self.initialized = is_ready
        self.initialized_for = current_mode if is_ready else None
        return is_ready

    async def voiceover(self, text: str, character: Optional[Any] = None, **kwargs) -> Optional[str]:
        current_mode = self.parent.current_model_id
        if not self.initialized or self.initialized_for != current_mode:
            raise Exception(f"Обработчик не инициализирован для режима '{current_mode}'.")

        voice_paths = get_character_voice_paths(character, self.parent.provider)
        self.parent.pth_path = voice_paths["pth_path"]
        self.parent.index_path = voice_paths["index_path"]
        self.parent.clone_voice_filename = voice_paths["clone_voice_filename"]
        self.parent.clone_voice_text = voice_paths["clone_voice_text"]
        self.parent.current_character_name = voice_paths["character_name"]

        if current_mode == "low":
            return await self._voiceover_edge_tts_rvc(
                text, character,
                output_file=kwargs.get("output_file"),
                settings_model_id=kwargs.get("settings_model_id"),
                TEST_WITH_DONE_AUDIO=kwargs.get("TEST_WITH_DONE_AUDIO"),
            )
        if current_mode == "low+":
            return await self._voiceover_silero_rvc(text, character, output_file=kwargs.get("output_file"))
        raise ValueError(f"Неизвестный режим: {current_mode}")

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
                os.remove(out)
            os.replace(produced_path, out)
            return out
        except Exception:
            return produced_path

    async def _voiceover_edge_tts_rvc(self, text, character=None, TEST_WITH_DONE_AUDIO=None,
                                       settings_model_id=None, output_file=None):
        if self.current_tts_rvc is None:
            raise Exception("Компонент RVC не инициализирован.")
        try:
            config_id = settings_model_id or self.parent.current_model_id
            settings = self.parent.load_model_settings(config_id)
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
            use_index_file = settings.get("use_index_file", True)
            f0method_override = settings.get("f0method", None)
            tts_rate = int(settings.get("tts_rate", 0)) if config_id != "medium+low" else 0
            vol = str(settings.get("volume", "1.0"))

            if use_index_file and index_path and os.path.exists(index_path):
                self.current_tts_rvc.set_index_path(index_path)
            else:
                self.current_tts_rvc.set_index_path("")

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
            if current_model_abs != os.path.abspath(model_path):
                if hasattr(self.current_tts_rvc, "set_model"):
                    self.current_tts_rvc.set_model(model_path)
                else:
                    self.current_tts_rvc.current_model = model_path

            self._adjust_sampling_rate()

            if not TEST_WITH_DONE_AUDIO:
                inference_params["tts_rate"] = tts_rate
                output_file_rvc = self.current_tts_rvc(text=text, **inference_params)
            else:
                output_file_rvc = self.current_tts_rvc.voiceover_file(input_path=TEST_WITH_DONE_AUDIO, **inference_params)

            if not output_file_rvc or not os.path.exists(output_file_rvc) or os.path.getsize(output_file_rvc) == 0:
                return None

            stereo = output_file_rvc.replace(".wav", "_stereo.wav")
            converted = self.parent.convert_wav_to_stereo(output_file_rvc, stereo, atempo=1.0, volume=vol)
            if converted and os.path.exists(converted):
                try:
                    os.remove(output_file_rvc)
                except OSError:
                    pass
                final = stereo
            else:
                final = output_file_rvc

            return self._maybe_move_to_output(final, output_file)
        except Exception as error:
            traceback.print_exc()
            logger.info(f"Ошибка Edge-TTS+RVC (ONNX): {error}")
            return None

    async def _voiceover_silero_rvc(self, text, character=None, output_file=None):
        if self.current_silero_model is None or self.current_tts_rvc is None:
            raise Exception("Компоненты Silero или RVC не инициализированы.")
        temp_wav = None
        try:
            voice_paths = get_character_voice_paths(character, self.parent.provider)
            character_name = voice_paths["character_name"]
            settings = self.parent.load_model_settings("low+")

            # reuse SSML preprocessing from the CUDA model via import
            from .edge_tts_rvc_model import EdgeTTS_RVC_Model as _CudaModel
            ssml_text, character_base_rvc_pitch, character_speaker = _CudaModel._preprocess_text_to_ssml(
                self, text, character_name
            )

            audio_tensor = self.current_silero_model.apply_tts(
                ssml_text=ssml_text,
                speaker=character_speaker,
                sample_rate=self.current_silero_sample_rate,
                put_accent=settings.get("silero_put_accent", True),
                put_yo=settings.get("silero_put_yo", True),
            )
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                temp_wav = f.name
            sf.write(temp_wav, audio_tensor.cpu().numpy(), self.current_silero_sample_rate)

            if not os.path.exists(temp_wav) or os.path.getsize(temp_wav) == 0:
                return None

            base_pitch = float(settings.get("silero_rvc_pitch", 6))
            final_pitch = base_pitch - (6 - character_base_rvc_pitch)
            vol = str(settings.get("volume", "1.0"))
            index_path = voice_paths["index_path"]
            use_index = settings.get("silero_rvc_use_index_file", True)

            if use_index and index_path and os.path.exists(index_path):
                self.current_tts_rvc.set_index_path(index_path)
            else:
                self.current_tts_rvc.set_index_path("")

            self._adjust_sampling_rate()

            inference_params = {
                "pitch": final_pitch,
                "index_rate": float(settings.get("silero_rvc_index_rate", 0.75)),
                "protect": float(settings.get("silero_rvc_protect", 0.33)),
                "filter_radius": int(settings.get("silero_rvc_filter_radius", 3)),
                "rms_mix_rate": float(settings.get("silero_rvc_rms_mix_rate", 0.5)),
            }
            f0m = settings.get("silero_rvc_f0method")
            if f0m:
                inference_params["f0method"] = f0m

            output_file_rvc = self.current_tts_rvc.voiceover_file(input_path=temp_wav, **inference_params)
            if not output_file_rvc or not os.path.exists(output_file_rvc) or os.path.getsize(output_file_rvc) == 0:
                return None

            stereo = output_file_rvc.replace(".wav", "_stereo.wav")
            converted = self.parent.convert_wav_to_stereo(output_file_rvc, stereo, atempo=1.0, volume=vol)
            if converted and os.path.exists(converted):
                try:
                    os.remove(output_file_rvc)
                except OSError:
                    pass
                final = stereo
            else:
                final = output_file_rvc

            return self._maybe_move_to_output(final, output_file)
        except Exception as error:
            traceback.print_exc()
            logger.info(f"Ошибка Silero+RVC (ONNX): {error}")
            return None
        finally:
            if temp_wav and os.path.exists(temp_wav):
                try:
                    os.remove(temp_wav)
                except OSError:
                    pass
