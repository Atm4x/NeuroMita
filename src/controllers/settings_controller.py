import os
import base64
import json
from typing import Dict, Any

from managers.settings_manager import SettingsManager
from main_logger import logger
from utils import SH, _
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtCore import QTimer
from core.events import get_event_bus, Events, Event
from utils.migration import find_character_directories, perform_full_migration, is_already_migrated
from managers.database_manager import DatabaseManager
from PyQt6.QtWidgets import QMessageBox


class SettingsController:
    def __init__(self, config_path):
        self.config_path = config_path
        self.event_bus = get_event_bus()
        self._subscribe_to_events()
        self.settings = SettingsManager(self.config_path)
        

    def _subscribe_to_events(self):
        self.event_bus.subscribe(Events.Settings.GET_SETTINGS, self._on_get_settings, weak=False)
        self.event_bus.subscribe(Events.Settings.GET_SETTING, self._on_get_setting, weak=False)
        self.event_bus.subscribe(Events.Settings.SAVE_SETTING, self._on_save_setting, weak=False)
        self.event_bus.subscribe(Events.Settings.GET_APP_VARS, self._on_get_app_vars, weak=False)
        
    def load_api_settings(self, update_model):
        # Проверка на миграцию при запуске
        self._check_and_prompt_migration()
        
        logger.info("Начинаю загрузку настроек API")
        
        preset_id = self.settings.get("LAST_API_PRESET_ID", 0)
        
        if preset_id:
            preset_data = self.event_bus.emit_and_wait(Events.ApiPresets.GET_PRESET_FULL,
                                                        {'id': preset_id}, timeout=1.0)
            if preset_data and preset_data[0]:
                preset = preset_data[0]
                
                api_key = self.settings.get("NM_API_KEY", "")
                api_url = self.settings.get("NM_API_URL", "")
                api_model = self.settings.get("NM_API_MODEL", "")
                
                if update_model:
                    model_settings = {
                        'api_key': api_key,
                        'api_key_res': self.settings.get("NM_API_KEY_RES", ""),
                        'api_url': api_url,
                        'api_model': api_model,
                        'makeRequest': preset.get('use_request', False)
                    }
                    self.event_bus.emit("model_settings_loaded", model_settings)
        
        telegram_settings = {
            "api_id": self.settings.get("NM_TELEGRAM_API_ID", ""),
            "api_hash": self.settings.get("NM_TELEGRAM_API_HASH", ""),
            "phone": self.settings.get("NM_TELEGRAM_PHONE", ""),
            "settings": self.settings
        }
        self.event_bus.emit("telegram_settings_loaded", telegram_settings)
        
        capture_settings = {"settings": self.settings}
        self.event_bus.emit("capture_settings_loaded", capture_settings)
        
        speech_settings = {"settings": self.settings}
        self.event_bus.emit("speech_settings_loaded", speech_settings)
        
        logger.info("Настройки API применены")

    def _check_and_prompt_migration(self):
        """Проверяет наличие старых JSON-файлов и предлагает миграцию."""
        characters = find_character_directories()
        needs_migration = any(not is_already_migrated(char) for char in characters)
        
        if needs_migration:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Icon.Question)
            msg.setWindowTitle(_("Миграция данных", "Data Migration"))
            msg.setText(_("Обнаружены старые файлы истории и памяти (JSON). Хотите импортировать их в новую базу данных SQLite?", "Old history and memory files (JSON) detected. Do you want to import them to the new SQLite database?"))
            msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg.button(QMessageBox.StandardButton.Yes).setText(_("Да, импортировать", "Yes, import"))
            msg.button(QMessageBox.StandardButton.No).setText(_("Нет, позже", "No, later"))
            
            reply = msg.exec()
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    db_manager = DatabaseManager()
                    result = perform_full_migration(db_manager)
                    if result["total_history"] > 0 or result["total_memory"] > 0:
                        QMessageBox.information(self, _("Миграция завершена", "Migration completed"),
                                              f"Импортировано: {result['total_history']} сообщений истории, {result['total_memory']} воспоминаний для {len(result['migrated_characters'])} персонажей.")
                        logger.info(f"Миграция завершена: {result}")
                    else:
                        QMessageBox.information(self, _("Нет данных для миграции", "No data to migrate"),
                                              _("Нет данных для импорта или миграция уже выполнена.", "No data to import or migration already done."))
                except Exception as e:
                    QMessageBox.critical(self, _("Ошибка миграции", "Migration error"), f"Ошибка при миграции: {str(e)}")
                    logger.error(f"Ошибка миграции при запуске: {e}")
            else:
                logger.info("Пользователь отказался от миграции при запуске.")

    def _on_get_settings(self, event: Event):
        return self.settings
    
    def _on_save_setting(self, event: Event):
        key = event.data.get('key')
        value = event.data.get('value')
        
        if key:
            self.settings.set(key, value)
            self.settings.save_settings()
            self.update_setting(key, value)
    
    def _on_get_setting(self, event: Event):
        key = event.data.get('key')
        default = event.data.get('default', None)
        
        return self.settings.get(key, default)
    
    def update_setting(self, key, value):
        self.settings.set(key, value)
        self.settings.save_settings()
        
        self.event_bus.emit(Events.Core.SETTING_CHANGED, {"key": key, "value": value})
        
        logger.debug(f"Настройка '{key}' успешно применена со значением: {value}")

    def _on_get_app_vars(self, event: Event):
        bool_keys = [
            "ENABLE_CAMERA_CAPTURE",
            "ENABLE_SCREEN_ANALYSIS",
            "MIC_ACTIVE",
        ]

        custom_vars: Dict[str, Any] = {
            "app_version": "1.0.0",
        }

        flag_vars: Dict[str, Any] = {
            key: bool(SettingsManager.get(key, False))
            for key in bool_keys
        }

        return {**flag_vars, **custom_vars}
        