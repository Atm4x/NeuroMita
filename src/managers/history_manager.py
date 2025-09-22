import os
from main_logger import logger
from managers.database_manager import DatabaseManager
from datetime import datetime


class HistoryManager:
    """Управляет историей сообщений персонажа, используя базу данных."""

    def __init__(self, character_name="Common"):
        self.character_name = character_name
        self.db_manager = DatabaseManager()
        logger.info(f"HistoryManager инициализирован для персонажа: {character_name}")

    def add_message(self, role: str, content: str, timestamp: str = None):
        """Добавляет сообщение в историю для текущего персонажа."""
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        self.db_manager.add_history_message(self.character_name, role, content, timestamp)
        logger.debug(f"Сообщение добавлено в историю для {self.character_name}: {role} - {content[:50]}...")

    def get_history(self, limit: int = None) -> list[dict]:
        """Получает историю сообщений для текущего персонажа."""
        messages = self.db_manager.get_history_messages(self.character_name, limit)
        # Преобразуем формат из БД в ожидаемый формат {role: ..., content: ...}
        formatted_messages = [{'role': msg['role'], 'content': msg['content']} for msg in messages]
        logger.debug(f"Получено {len(formatted_messages)} сообщений из истории для {self.character_name}.")
        return formatted_messages

    def clear_history(self):
        """Очищает историю сообщений для текущего персонажа."""
        self.db_manager.clear_history(self.character_name)
        logger.info(f"История для персонажа {self.character_name} очищена.")

    def get_messages_for_compression(self, num_messages: int) -> list[dict]:
        """
        Возвращает `num_messages` самых старых сообщений и удаляет их из истории.
        """
        messages_to_compress_db_format = self.db_manager.get_history_messages(self.character_name, num_messages)
        
        # Удаляем извлеченные сообщения из БД
        ids_to_delete = [msg['id'] for msg in messages_to_compress_db_format]
        self.db_manager.delete_history_messages_by_ids(ids_to_delete)
        
        messages_to_compress = [{'role': msg['role'], 'content': msg['content']} for msg in messages_to_compress_db_format]
        logger.info(f"Извлечено {len(messages_to_compress)} сообщений для сжатия и удалено из истории для {self.character_name}.")
        return messages_to_compress

    def add_summarized_history_to_messages(self, summary_message: dict):
        """Добавляет сжатую сводку обратно в список сообщений истории."""
        # Добавляем сводку как обычное сообщение в историю
        self.add_message(summary_message['role'], summary_message['content'])
        logger.debug(f"Сжатая сводка добавлена в историю для {self.character_name}.")

    # Методы, которые больше не нужны или будут перенесены
    # def load_history(self): ... (удалено)
    # def history_format_correct(self, data): ... (удалено)
    # def save_history(self, data): ... (удалено)
    # def save_history_separate(self): ... (удалено)
    # def save_missed_history(self, missed_messages: list): ... (удалено)
    # def _default_history(self): ... (удалено, так как история теперь в БД)
