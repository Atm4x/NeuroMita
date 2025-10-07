import json
import logging
import os
import datetime

from main_logger import logger
from managers.database_manager import DatabaseManager


class MemoryManager:
    """Менеджер памяти персонажа, фасад над DatabaseManager для совместимости с JSON-API."""

    def __init__(self, character_name):
        self.character_name = character_name
        self.history_dir = f"Histories\\{character_name}"
        os.makedirs(self.history_dir, exist_ok=True)
        self.filename = os.path.join(self.history_dir, f"{character_name}_memories.json")
        self.db_manager = DatabaseManager()
        self.memories = []
        self.total_characters = 0
        self.last_memory_number = 1
        self.load_memories()

    def load_memories(self):
        """Загружает воспоминания из БД в self.memories."""
        try:
            db_memories = self.db_manager.get_memories(self.character_name, order='ASC')
            self.memories = []
            max_n = 0
            for mem in db_memories:
                n = int(mem['key']) if mem['key'].isdigit() else self.last_memory_number
                memory = {
                    "N": n,
                    "date": mem['timestamp'],
                    "priority": mem['priority'],
                    "content": mem['value'],
                    "memory_type": mem['memory_type']
                }
                self.memories.append(memory)
                if n > max_n:
                    max_n = n
                self.total_characters += len(mem['value'])
            self.last_memory_number = max_n + 1
            if not os.path.exists(self.filename):
                self.save_memories_to_json()  # Создаем пустой JSON для совместимости
                logger.info(f"Created new memories file: {self.filename}")
        except Exception as e:
            logger.error(f"Ошибка загрузки воспоминаний: {e}")
            self.memories = []
            self.total_characters = 0
            self.last_memory_number = 1
            self.save_memories_to_json()

    def save_memories(self):
        """Сохраняет self.memories в БД."""
        for memory in self.memories:
            key = str(memory['N'])
            value = memory['content']
            priority = memory['priority']
            memory_type = memory['memory_type']
            timestamp = memory['date']
            self.db_manager.insert_memory(
                self.character_name, key, value, priority, memory_type, timestamp
            )

    def save_memories_to_json(self):
        """Сохраняет в JSON для бэкапа или совместимости."""
        with open(self.filename, 'w', encoding='utf-8') as file:
            json.dump(self.memories, file, ensure_ascii=False, indent=4)

    def add_memory(self, content, date=None, priority="Normal", memory_type="fact"):
        """Добавляет новое воспоминание в self.memories и БД."""
        if date is None:
            date = datetime.datetime.now().isoformat() # Используем ISO формат для БД
        
        if isinstance(content, list):
            # Если content - это список, преобразуем его в строку
            content = " ".join([str(item) for item in content])

        new_id = self.last_memory_number
        memory = {
            "N": new_id,
            "date": date,
            "priority": priority,
            "content": content,
            "memory_type": memory_type
        }
        self.memories.append(memory)
        self.total_characters += len(content)
        self.last_memory_number += 1
        # Сохраняем в БД
        self.db_manager.insert_memory(
            self.character_name, str(new_id), content, priority, memory_type, date
        )
        self.save_memories_to_json()  # Опционально для бэкапа

    def update_memory(self, number, content, priority=None):
        """Обновляет воспоминание по N."""
        for memory in self.memories:
            if memory["N"] == number:
                self.total_characters -= len(memory["content"])
                
                if isinstance(content, list):
                    content = " ".join([str(item) for item in content])

                self.total_characters += len(content)
                memory["date"] = datetime.datetime.now().isoformat() # Используем ISO формат для БД
                memory["content"] = content
                if priority:
                    memory["priority"] = priority
                # Обновляем в БД
                self.db_manager.update_memory(number, value=content, priority=priority, timestamp=memory["date"])
                self.save_memories()
                self.save_memories_to_json()
                return True
        return False

    def delete_memory(self, number, save_as_missing=False):
        """Удаляет воспоминание по N."""
        for i, memory in enumerate(self.memories):
            if memory["N"] == number:
                if save_as_missing:
                    self.save_missed_memory(memory)
                self.total_characters -= len(memory["content"])
                del self.memories[i]
                # Удаляем из БД
                self.db_manager.delete_memory(number)
                self.save_memories()
                self.save_memories_to_json()
                logger.info(f"Memory {number} deleted")
                return True
        logger.warning(f"Memory {number} not found for deletion.")
        return False

    def save_missed_memory(self, missed_memory: dict):
        """Сохраняет удалённое воспоминание в missed_memories.json (как раньше)."""
        missed_dir = self.history_dir
        os.makedirs(missed_dir, exist_ok=True)
        missed_file_path = os.path.join(missed_dir, f"{self.character_name}_missed_memories.json")

        existing_missed_memories = []
        if os.path.exists(missed_file_path):
            try:
                with open(missed_file_path, 'r', encoding='utf-8') as f:
                    existing_missed_memories = json.load(f)
                    if not isinstance(existing_missed_memories, list):
                        logger.warning(f"Файл пропущенных воспоминаний поврежден. Создаю новый.")
                        existing_missed_memories = []
            except (json.JSONDecodeError, FileNotFoundError):
                logger.warning(f"Не удалось загрузить missed_memories. Создаю новый файл.")
                existing_missed_memories = []

        existing_missed_memories.append(missed_memory)

        try:
            with open(missed_file_path, 'w', encoding='utf-8') as f:
                json.dump(existing_missed_memories, f, ensure_ascii=False, indent=4)
            logger.info(f"Пропущенное воспоминание сохранено в {missed_file_path}")
        except Exception as e:
            logger.error(f"Ошибка при сохранении missed_memory: {e}", exc_info=True)

    def clear_memories(self):
        """Очищает воспоминания в БД и self.memories."""
        self.memories = []
        self.total_characters = 0
        self.last_memory_number = 1
        self.db_manager.clear_memory(self.character_name)
        self.save_memories_to_json()

    def get_memories_formatted(self):
        """Форматирует воспоминания как раньше."""
        formatted_memories = []
        for memory in self.memories:
            # Форматируем дату для отображения
            formatted_date = datetime.datetime.fromisoformat(memory['date']).strftime("%d.%m.%Y %H:%M")
            if memory.get('memory_type', "") == "summary":
                formatted_memories.append(
                    f"N:{memory['N']}, Date {formatted_date}, Type: Summary: {memory['content']}"
                )
            else:
                formatted_memories.append(
                    f"N:{memory['N']}, Date {formatted_date}, Priority: {memory['priority']}: {memory['content']}"
                )

        memory_stats = f"\nMemory status: {len(self.memories)} facts, {self.total_characters} characters"

        # Правила для управления памятью
        management_tips = []
        if self.total_characters > 10000:
            management_tips.append("CRITICAL: Memory limit exceeded! Delete old or useless memories immediately!")
        elif self.total_characters > 5000:
            management_tips.append("WARNING: Memory size is large. Consider optimization or summarization")

        if len(self.memories) > 75:
            management_tips.append("Too many memories! Delete unimportant ones using <-memory>N</memory> syntax")
        elif len(self.memories) > 40:
            management_tips.append("Many memories stored. Review lower priority entries")

        # Примеры команд
        examples = [
            "Example of memory commands:",
            "<-memory>2</memory> - delete memory 2",
            "<+memory>high|new content</memory> - add memory with priority high",
            "<#memory>4|low|content</memory> - change memory 4 to content with priority low"
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