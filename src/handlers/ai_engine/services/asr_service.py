from __future__ import annotations

import asyncio
import gc
from typing import Any, Callable, Optional


class ASRService:
    """
    ASR service, живёт в отдельном процессе.
    Поддерживает live recognition и отдаёт события в GUI через emit_event():
      - event="text": {"text": "..."}
      - event="status": {"running": bool}
    """

    def __init__(self, *, emit_event: Callable[[str, Any], None]):
        self.emit_event = emit_event

        self._recognizer = None
        self._engine_id: str = "google"
        self._engine_settings: dict = {}

        self._active: bool = False
        self._task: Optional[asyncio.Task] = None

        self._vad_model = None

        self._pip_installer = None
        self._logger = None

        # Верификация спикера (засчитывать только голос пользователя).
        self._speaker = None                 # SpeakerVerifier | None
        self._speaker_enabled: bool = False
        self._enroll_next: bool = False      # следующий сегмент — образец голоса

    async def shutdown(self):
        await self._stop_live_internal()

    async def handle(self, method: str, payload: dict):
        m = str(method or "").strip().lower()

        if m == "ping":
            return True

        if m == "get_status":
            return {"running": bool(self._active)}

        if m == "enroll_next":
            # Следующий распознанный сегмент будет использован как образец
            # голоса пользователя (см. _handle_text). Требует активного ASR.
            self._enroll_next = True
            return True

        if m == "speaker_reset":
            try:
                from handlers.asr_models.speaker_verifier import SpeakerVerifier
                ok = SpeakerVerifier().reset()
            except Exception:
                ok = False
            if self._speaker is not None:
                try:
                    self._speaker.reset()
                except Exception:
                    pass
            return bool(ok)

        if m == "get_speaker_status":
            try:
                from handlers.asr_models.speaker_verifier import SpeakerVerifier, profile_exists
                return {
                    "available": bool(SpeakerVerifier.is_available()),
                    "enrolled": bool(profile_exists()),
                }
            except Exception:
                return {"available": False, "enrolled": False}

        if m == "start_live":
            engine_id = str(payload.get("engine_id") or "google").strip()
            mic_index = int(payload.get("microphone_index", 0) or 0)
            engine_settings = payload.get("engine_settings") if isinstance(payload.get("engine_settings"), dict) else {}

            vad_cfg = payload.get("vad") if isinstance(payload.get("vad"), dict) else {}
            sample_rate = int(vad_cfg.get("sample_rate", 16000) or 16000)
            chunk_size = int(vad_cfg.get("chunk_size", 512) or 512)
            vad_threshold = float(vad_cfg.get("vad_threshold", 0.5) or 0.5)
            silence_timeout = float(vad_cfg.get("silence_timeout", 0.15) or 0.15)
            pre_buffer_duration = float(vad_cfg.get("pre_buffer_duration", 0.3) or 0.3)
            max_speech_duration = float(vad_cfg.get("max_speech_duration", 30.0) or 30.0)

            spk_cfg = payload.get("speaker") if isinstance(payload.get("speaker"), dict) else {}
            self._setup_speaker(spk_cfg)

            await self._stop_live_internal()

            ok = await self._start_live_internal(
                engine_id=engine_id,
                mic_index=mic_index,
                engine_settings=engine_settings,
                sample_rate=sample_rate,
                chunk_size=chunk_size,
                vad_threshold=vad_threshold,
                silence_timeout=silence_timeout,
                pre_buffer_duration=pre_buffer_duration,
                max_speech_duration=max_speech_duration,
            )
            return bool(ok)

        if m == "stop_live":
            await self._stop_live_internal()
            return True

        raise RuntimeError(f"Unknown asr method: {method}")

    async def _start_live_internal(
        self,
        *,
        engine_id: str,
        mic_index: int,
        engine_settings: dict,
        sample_rate: int,
        chunk_size: int,
        vad_threshold: float,
        silence_timeout: float,
        pre_buffer_duration: float,
        max_speech_duration: float,
    ) -> bool:
        self._engine_id = engine_id
        self._engine_settings = engine_settings or {}

        rec = self._get_recognizer(engine_id)
        if rec is None:
            return False

        try:
            if hasattr(rec, "apply_settings"):
                rec.apply_settings(self._engine_settings)
        except Exception:
            pass

        if hasattr(rec, "is_installed"):
            try:
                if not rec.is_installed():
                    return False
            except Exception:
                pass

        ok = await rec.init()
        if not ok:
            return False

        vad_model = None
        if engine_id != "google":
            vad_model = await self._get_vad_model()

        self._active = True
        self.emit_event("status", {"running": True})

        async def _handle_text(text, audio=None, sample_rate=16000):
            t = (text or "").strip()

            # Энроллмент: текущий сегмент — образец голоса пользователя.
            if self._enroll_next and audio is not None and self._speaker is not None:
                self._enroll_next = False
                ok = False
                try:
                    ok = bool(self._speaker.enroll(audio, sample_rate))
                except Exception:
                    ok = False
                self.emit_event("enrolled", {"ok": ok})
                # Образец в чат не отправляем.
                return

            # Гейт: засчитываем только голос пользователя. На неопределённости
            # (accept() вернул None — нет профиля / коротко / нет модели) —
            # пропускаем, чтобы не съесть речь.
            if self._speaker_enabled and self._speaker is not None and audio is not None:
                try:
                    decision = self._speaker.accept(audio, sample_rate)
                except Exception:
                    decision = None
                if decision is False:
                    return

            if t:
                self.emit_event("text", {"text": t})

        def _active_flag():
            return bool(self._active)

        async def _runner():
            try:
                await rec.live_recognition(
                    mic_index,
                    _handle_text,
                    vad_model,
                    _active_flag,
                    sample_rate=sample_rate,
                    chunk_size=chunk_size,
                    vad_threshold=vad_threshold,
                    silence_timeout=silence_timeout,
                    pre_buffer_duration=pre_buffer_duration,
                    max_speech_duration=max_speech_duration,
                )
            finally:
                self._active = False
                self.emit_event("status", {"running": False})

        self._task = asyncio.create_task(_runner())
        return True

    async def _stop_live_internal(self):
        self._active = False

        if self._task is not None:
            try:
                self._task.cancel()
                await asyncio.wait_for(self._task, timeout=5.0)
            except asyncio.CancelledError:
                pass
            except asyncio.TimeoutError:
                pass
            except Exception:
                pass
            finally:
                self._task = None

        if self._recognizer is not None:
            try:
                self._recognizer.cleanup()
            except Exception:
                pass
            finally:
                self._recognizer = None

        self._unload_vad_model()
        self.emit_event("status", {"running": False})

    def _setup_speaker(self, cfg: dict):
        """Подготовить верификатор спикера по конфигу из start_live payload."""
        self._speaker_enabled = bool(cfg.get("enabled"))
        try:
            threshold = float(cfg.get("threshold") or 0.0)
        except Exception:
            threshold = 0.0

        # Энроллмент нужен даже при выключенном гейте, поэтому создаём
        # верификатор, если модель в принципе доступна.
        try:
            from handlers.asr_models.speaker_verifier import SpeakerVerifier
            if not SpeakerVerifier.is_available():
                self._speaker = None
                if self._logger is None:
                    from main_logger import logger as _logger
                    self._logger = _logger
                if self._speaker_enabled:
                    self._logger.warning(
                        "Speaker verification включена, но resemblyzer не установлен — "
                        "поставьте компонент «Распознавание спикера» в AI Hub (раздел ASR)."
                    )
                return
            if self._logger is None:
                from main_logger import logger as _logger
                self._logger = _logger
            kwargs = {"logger": self._logger}
            if threshold > 0:
                kwargs["threshold"] = threshold
            self._speaker = SpeakerVerifier(**kwargs)
        except Exception as e:
            self._speaker = None
            try:
                from main_logger import logger as _logger
                _logger.error(f"Speaker verifier setup failed: {e}")
            except Exception:
                pass

    async def _get_vad_model(self):
        if self._vad_model is not None:
            return self._vad_model

        try:
            from handlers.embedding_handler import _ensure_torch_and_transformers
            _ensure_torch_and_transformers()
            import torch
        except Exception as e:
            raise RuntimeError(f"torch not available for VAD: {e}") from None

        try:
            from silero_vad import load_silero_vad
        except Exception as e:
            raise RuntimeError(f"silero_vad not available: {e}") from None

        self._vad_model = load_silero_vad()
        return self._vad_model

    def _unload_vad_model(self):
        self._vad_model = None
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

    def _get_recognizer(self, engine_id: str):
        if self._recognizer is not None and self._engine_id == engine_id:
            return self._recognizer

        # Ленивая загрузка классов
        from handlers.asr_models.google_recognizer import GoogleRecognizer
        from handlers.asr_models.gigaam_recognizer import GigaAMRecognizer
        from handlers.asr_models.gigaam_onnx_recognizer import GigaAMOnnxRecognizer
        from handlers.asr_models.whisper_recognizer import WhisperRecognizer
        from handlers.asr_models.whisper_onnx_recognizer import WhisperOnnxRecognizer

        reg = {
            "google": GoogleRecognizer,
            "gigaam": GigaAMRecognizer,
            "gigaam_onnx": GigaAMOnnxRecognizer,
            "whisper": WhisperRecognizer,
            "whisper_onnx": WhisperOnnxRecognizer,
        }

        cls = reg.get(str(engine_id or "").strip())
        if not cls:
            return None

        if self._logger is None:
            from main_logger import logger as _logger
            self._logger = _logger

        if self._pip_installer is None:
            try:
                from utils.pip_installer import PipInstaller
                self._pip_installer = PipInstaller(
                    update_log=self._logger.info,
                )
            except Exception:
                self._pip_installer = None

        self._recognizer = cls(self._pip_installer, self._logger)
        return self._recognizer
