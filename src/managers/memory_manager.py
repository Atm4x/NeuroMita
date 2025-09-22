import logging
from managers.database_manager import DatabaseManager
from datetime import datetime


class MemoryManager:
    def __init__(self, character_name):
        self.character_name = character_name
        self.db_manager = DatabaseManager()
        logging.info(f"MemoryManager инициализирован для персонажа: {character_name}")

    def add_memory(self, content: str, key: str = None, priority: str = "Normal", memory_type: str = "fact"):
        """Добавляет факт в память для текущего персонажа."""
        # Если ключ не предоставлен, используем часть контента или генерируем уникальный
        if key is None:
            key = f"{memory_type}_{datetime.now().isoformat()}" # Пример генерации ключа
        
        self.db_manager.add_memory_fact(self.character_name, key, content, datetime.now().isoformat())
        logging.debug(f"Факт добавлен в память для {self.character_name}: {key} - {content[:50]}...")

    def update_memory(self, key: str, content: str, priority: str = None):
        """Обновляет существующий факт в памяти или добавляет новый."""
        self.db_manager.update_memory_fact(self.character_name, key, content, datetime.now().isoformat())
        logging.debug(f"Факт обновлен/добавлен в память для {self.character_name}: {key} - {content[:50]}...")
        return True # Всегда возвращаем True, так как update_memory_fact либо обновляет, либо добавляет

    def delete_memory(self, key: str, save_as_missing: bool = False):
        """Удаляет факт из памяти для персонажа."""
        # save_as_missing не поддерживается напрямую в БД, так как это логика JSON-файлов
        self.db_manager.delete_memory_fact(self.character_name, key)
        logging.info(f"Факт {key} удален из памяти для {self.character_name}.")
        return True

    def clear_memories(self):
        """Очищает всю память для текущего персонажа."""
        self.db_manager.clear_memory(self.character_name)
        logging.info(f"Память для персонажа {self.character_name} очищена.")

    def get_memories_formatted(self):
        """Получает и форматирует все факты из памяти для текущего персонажа."""
        memories_dict = self.db_manager.get_memory_facts(self.character_name)
        
        formatted_memories = []
        total_characters = 0
        for key, value in memories_dict.items():
            # В текущей схеме БД нет полей 'N', 'date', 'priority', 'memory_type' для каждого факта
            # Поэтому форматируем, используя доступные данные
            formatted_memories.append(f"Key: {key}, Content: {value}")
            total_characters += len(value)

        memory_stats = f"\nMemory status: {len(memories_dict)} facts, {total_characters} characters"

        # Правила для управления памятью
        management_tips = []
        if total_characters > 10000:
            management_tips.append("CRITICAL: Memory limit exceeded! Delete old or useless memories immediately!")
        elif total_characters > 5000:
            management_tips.append("WARNING: Memory size is large. Consider optimization or summarization")

        if len(memories_dict) > 75:
            management_tips.append("Too many memories! Delete unimportant ones using <-memory>N</memory> syntax")
        elif len(memories_dict) > 40:
            management_tips.append("Many memories stored. Review lower priority entries")

        # Примеры команд (нужно будет адаптировать под работу с ключами вместо N)
        examples = [
            "Example of memory commands:",
            "<-memory>key_to_delete</memory> - delete memory by key",
            "<+memory>new_key|new content</memory> - add memory with a new key",
            "<#memory>existing_key|updated content</memory> - change memory by key"
        ]

        full_message = (
                "LongMemory< " +
                "\n".join(formatted_memories) +
                " >EndLongMemory\n" +
                memory_stats + "\n" +
                "\n".join(management_tips) + "\n" +
                "\n".join(examples)
        )

        return full_message

    # Методы, которые больше не нужны или будут перенесены
    # def load_memories(self): ... (удалено)
    # def _calculate_total_characters(self): ... (удалено)
    # def save_memories(self): ... (удалено)
    # def save_missed_memory(self, missed_memory: dict): ... (удалено)