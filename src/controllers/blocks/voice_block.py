from __future__ import annotations

from main_logger import logger

from .block_base import ControllerBlock
from .block_context import BlockContext


class VoiceBlock(ControllerBlock):
    name = "voice"
    enabled_setting = "BLOCK_VOICE_ENABLED"
    default_enabled = False
    dependencies = ("ai_engine",)

    def initialize(self, ctx: BlockContext) -> None:
        from controllers.audio_controller import AudioController
        from controllers.local_voice_controller import LocalVoiceController
        from controllers.voice_model_controller import VoiceModelController
        from controllers.speech_controller import SpeechController

        local_voice = LocalVoiceController()
        self.controllers["local_voice_controller"] = local_voice
        logger.notify("LocalVoiceController успешно инициализирован.")

        audio = AudioController(ctx.settings, ctx.event_bus)
        self.controllers["audio_controller"] = audio
        logger.notify("AudioController успешно инициализирован.")

        voice_model = VoiceModelController(config_dir="Settings")
        self.controllers["voice_model_controller"] = voice_model
        logger.notify("VoiceModelController (backend) успешно инициализирован.")

        speech = SpeechController()
        self.controllers["speech_controller"] = speech
        logger.notify("SpeechController успешно инициализирован.")

        # Очистка остатков sound-файлов от прошлой сессии.
        try:
            audio.delete_all_sound_files()
        except Exception as e:
            logger.error(f"[VoiceBlock] delete_all_sound_files: {e}")

    def shutdown(self) -> None:
        audio = self.controllers.get("audio_controller")
        if audio:
            try:
                audio.delete_all_sound_files()
            except Exception as e:
                logger.error(f"[VoiceBlock] delete_all_sound_files: {e}")
