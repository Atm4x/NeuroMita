import json
import os
import datetime
import shutil
from typing import Optional

from main_logger import logger
from managers.database_manager import DatabaseManager


class HistoryManager:
    """Менеджер истории чатов, фасад над DatabaseManager для совместимости с JSON-API."""

    def __init__(self, character_name="Common", history_file_name=""):
        self.character_name = character_name
        self.db_manager = DatabaseManager()
        # Для совместимости с backup, сохраняем путь, но не используем для хранения
        self.history_dir = f"Histories\\{character_name}"
        self.history_file_path = os.path.join(self.history_dir, f"{character_name}_history.json") if history_file_name else ""
        os.makedirs(self.history_dir, exist_ok=True)
        if self.history_file_path:
            # Если указан файл, возможно, для миграции, но load_history теперь из DB
            pass

    def load_history(self):
        """Загружаем историю из БД, возвращаем структуру как в JSON."""
        try:
            metadata = self.db_manager.get_history_metadata(self.character_name)
            messages = self.db_manager.get_history(self.character_name, order='ASC')
            data = {
                'fixed_parts': metadata['fixed_parts'],
                'messages': messages,
                'temp_context': metadata['temp_context'],
                'variables': metadata['variables']
            }
            if self.history_format_correct(data):
                return data
            else:
                logger.info("Ошибка загрузки истории из БД, сброс к умолчанию")
                self.clear_history()
                return self._default_history()
        except Exception as e:
            logger.error(f"Ошибка загрузки истории: {e}")
            return self._default_history()

    def history_format_correct(self, data):
        """Проверяем формат данных (как в JSON)."""
        checks = [
            (isinstance(data.get('fixed_parts'), list), "fixed_parts должен быть списком"),
            (isinstance(data.get('messages'), list), "messages должен быть списком"),
            (isinstance(data.get('temp_context'), list), "temp_context должен быть списком"),
            (isinstance(data.get('variables'), dict), "variables должен быть словарем")
        ]
        if all(check[0] for check in checks):
            return True
        else:
            for condition, error_message in checks:
                if not condition:
                    logger.info(f"Ошибка: {error_message}")
            return False

    def save_history(self, data):
        """Сохраняем историю в БД."""
        # Извлекаем метаданные и сообщения
        metadata = {
            'fixed_parts': data.get('fixed_parts', []),
            'temp_context': data.get('temp_context', []),
            'variables': data.get('variables', {})
        }
        messages = data.get('messages', [])
        self.db_manager.update_history_metadata(self.character_name, metadata)
        self.db_manager.replace_history_messages(self.character_name, messages)

    def save_history_separate(self):
        """Бэкап истории в JSON-файл в папке Saved."""
        logger.info("Сохранение бэкапа истории")
        target_folder = f"Histories\\{self.character_name}\\Saved"
        os.makedirs(target_folder, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%d.%m.%Y_%H.%M")
        target_file = f"chat_history_{timestamp}.json"
        target_path = os.path.join(target_folder, target_file)
        # Экспорт из БД
        self.db_manager.export_history_to_json(self.character_name, target_path)
        logger.info(f"Бэкап сохранён как {target_path}")

    def save_missed_history(self, missed_messages: list):
        """
        Сохраняет "потерянные" сообщения. Для совместимости добавляем в историю как special messages.
        """
        for msg in missed_messages:
            self.add_message(role=msg.get('role', 'user'), content=msg.get('content', ''), timestamp=msg.get('timestamp'))
        logger.info(f"Добавлено {len(missed_messages)} пропущенных сообщений в историю")

    def add_message(self, role: str, content: str, timestamp: Optional[str] = None):
        """Добавляет сообщение в историю (новый метод для полноты API)."""
        if timestamp is None:
            timestamp = datetime.datetime.now().isoformat()
        self.db_manager.insert_history_message(self.character_name, role, content, timestamp)

    def clear_history(self):
        """Очищает историю в БД."""
        logger.info("Сброс истории")
        self.db_manager.clear_history(self.character_name)

    def _default_history(self):
        """Структура по умолчанию."""
        logger.info("Создание пустой истории")
        return {
            'fixed_parts': [],
            'messages': [],
            'temp_context': [],
            'variables': {}
        }

    def get_messages_for_compression(self, num_messages: int) -> list[dict]:
        """
        Получает num_messages самых старых сообщений для сжатия и удаляет их из БД.
        """
        messages_to_compress = self.db_manager.get_history_messages_for_compression(self.character_name, num_messages)
        logger.info(f"Извлечено {len(messages_to_compress)} сообщений для сжатия.")
        return messages_to_compress

    def add_summarized_history_to_messages(self, summary_message: dict):
        """Добавляет сжатую сводку в начало истории (как system message)."""
        role = summary_message.get('role', 'system')
        content = summary_message.get('content', '')
        self.add_message(role=role, content=content)
        # Поскольку вставка в начало, но DB по timestamp, для симуляции вставки в начало используем timestamp в прошлом
        # Но для простоты, новая запись будет последней; если нужно в начало, скорректировать timestamp
        logger.info("Добавлена сводка истории в начало")
