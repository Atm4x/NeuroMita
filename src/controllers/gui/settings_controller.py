from main_logger import logger
from core.events import Events, Event
from utils import getTranslationVariant as _
from .base_controller import BaseController

class SettingsController(BaseController):
    def subscribe_to_events(self):
        self.event_bus.subscribe(Events.GUI.SWITCH_VOICEOVER_SETTINGS, self._on_switch_voiceover_settings, weak=False)
        self.event_bus.subscribe(Events.GUI.UPDATE_CHAT_FONT_SIZE, self._on_update_chat_font_size, weak=False)
        self.event_bus.subscribe(Events.GUI.RELOAD_CHAT_HISTORY, self._on_reload_chat_history, weak=False)
        self.event_bus.subscribe(Events.Core.SETTING_CHANGED, self._on_setting_changed, weak=False)
        
    def _on_switch_voiceover_settings(self, event: Event):
        if self.view and hasattr(self.view, 'switch_voiceover_settings_signal') and self.view.switch_voiceover_settings_signal:
            self.view.switch_voiceover_settings_signal.emit()
        elif self.view and hasattr(self.view, 'switch_voiceover_settings'):
            self.view.switch_voiceover_settings()

    def _on_update_chat_font_size(self, event: Event):
        font_size = event.data.get('font_size', 12)
        if self.view and hasattr(self.view, 'update_chat_font_size_signal') and self.view.update_chat_font_size_signal:
            self.view.update_chat_font_size_signal.emit(font_size)
        elif self.view and hasattr(self.view, 'update_chat_font_size'):
            self.view.update_chat_font_size(font_size)

    def _on_reload_chat_history(self, event: Event):
        if self.view and hasattr(self.view, 'load_chat_history_signal') and self.view.load_chat_history_signal:
            self.view.load_chat_history_signal.emit()
        elif self.view and hasattr(self.view, 'load_chat_history'):
            self.view.load_chat_history()

    def _on_setting_changed(self, event: Event):
        key = event.data.get('key')
        value = event.data.get('value')

        if key in ["USE_VOICEOVER", "VOICEOVER_METHOD", "AUDIO_BOT", "NM_CURRENT_VOICEOVER", "VOICE_LANGUAGE", "LOCAL_VOICE_LOAD_LAST"]:
            self.event_bus.emit(Events.GUI.VOICEOVER_REFRESH)

        if key == "AUDIO_BOT":
            if isinstance(value, str) and value.startswith("@CrazyMitaAIbot"):
                self.event_bus.emit(Events.GUI.SHOW_INFO_MESSAGE, {
                    "title": _("Информация", "Information"),
                    "message": _("VinerX: наши товарищи из CrazyMitaAIbot предоставляет озвучку бесплатно буквально со своих пк, будет время - загляните к ним в тг, скажите спасибо)", "VinerX: Our friends from CrazyMitaAIbot provide free voice acting directly from their PCs. If you have time, check them out on Telegram and say thanks!)")
                })

        elif key == "CHAT_FONT_SIZE":
            try:
                font_size = int(value)
                self.event_bus.emit(Events.GUI.UPDATE_CHAT_FONT_SIZE, {"font_size": font_size})
                self.event_bus.emit(Events.GUI.RELOAD_CHAT_HISTORY)
                logger.info(_("Размер шрифта чата изменен на: {font_size}", "Chat font size changed to: {font_size}").format(font_size=font_size))
            except ValueError:
                logger.warning(_("Неверное значение для размера шрифта: {value}", "Invalid value for font size: {value}").format(value=value))
            except Exception as e:
                logger.error(_("Ошибка при изменении размера шрифта: {e}", "Error changing chat font size: {e}").format(e=e))

        elif key in ["SHOW_CHAT_TIMESTAMPS", "MAX_CHAT_HISTORY_DISPLAY", "HIDE_CHAT_TAGS"]:
            self.event_bus.emit(Events.GUI.RELOAD_CHAT_HISTORY)
            logger.info(_("Настройка '{key}' изменена на: {value}. История чата перезагружена.", "Setting '{key}' changed to: {value}. Chat history reloaded.").format(key=key, value=value))

        elif key == "SHOW_TOKEN_INFO":
            self.event_bus.emit(Events.GUI.UPDATE_TOKEN_COUNT)