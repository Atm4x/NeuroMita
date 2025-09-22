import os
import json
import shutil
from datetime import datetime

from managers.database_manager import DatabaseManager
from main_logger import logger

class MigrationManager:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.base_history_dir = "Histories" # Базовая директория для старых файлов

    def _find_old_character_dirs(self) -> list[str]:
        """Находит все директории персонажей, содержащие старые JSON-файлы."""
        character_dirs = []
        if not os.path.exists(self.base_history_dir):
            return []

        for char_name in os.listdir(self.base_history_dir):
            char_path = os.path.join(self.base_history_dir, char_name)
            if os.path.isdir(char_path):
                history_file = os.path.join(char_path, f"{char_name}_history.json")
                memory_file = os.path.join(char_path, f"{char_name}_memories.json")
                if os.path.exists(history_file) or os.path.exists(memory_file):
                    character_dirs.append(char_name)
        return character_dirs

    def _migrate_history_for_character(self, character_name: str):
        """Мигрирует историю сообщений для одного персонажа."""
        history_file_path = os.path.join(self.base_history_dir, character_name, f"{character_name}_history.json")
        if not os.path.exists(history_file_path):
            logger.info(f"Файл истории для {character_name} не найден: {history_file_path}")
            return

        try:
            with open(history_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            messages = data.get('messages', [])
            for msg in messages:
                role = msg.get('role')
                content = msg.get('content')
                if isinstance(content, list):
                    content = "\n".join(content) # Объединяем список строк в одну строку
                elif not isinstance(content, str):
                    content = str(content) # Преобразуем в строку, если это не список и не строка
                
                # В старой истории нет timestamp, используем текущее время или заглушку
                timestamp = datetime.now().isoformat()
                if role and content:
                    self.db_manager.add_history_message(character_name, role, content, timestamp)
            
            # Переименовываем файл после успешной миграции
            shutil.move(history_file_path, history_file_path + ".bak")
            logger.info(f"История для персонажа {character_name} успешно мигрирована и файл переименован в .bak")

        except json.JSONDecodeError as e:
            logger.error(f"Ошибка декодирования JSON в файле истории {history_file_path}: {e}")
        except Exception as e:
            logger.error(f"Неизвестная ошибка при миграции истории для {character_name}: {e}", exc_info=True)

    def _migrate_memory_for_character(self, character_name: str):
        """Мигрирует память (факты) для одного персонажа."""
        memory_file_path = os.path.join(self.base_history_dir, character_name, f"{character_name}_memories.json")
        if not os.path.exists(memory_file_path):
            logger.info(f"Файл памяти для {character_name} не найден: {memory_file_path}")
            return

        try:
            with open(memory_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Старая память - это список словарей с полями 'N', 'date', 'priority', 'content', 'memory_type'
            # В новой БД - это key-value пары
            for fact in data:
                content = fact.get('content')
                # Генерируем ключ из N или content, если N нет
                key = f"fact_{fact.get('N', datetime.now().timestamp())}" 
                if content:
                    self.db_manager.add_memory_fact(character_name, key, content, datetime.now().isoformat())
            
            # Переименовываем файл после успешной миграции
            shutil.move(memory_file_path, memory_file_path + ".bak")
            logger.info(f"Память для персонажа {character_name} успешно мигрирована и файл переименован в .bak")

        except json.JSONDecodeError as e:
            logger.error(f"Ошибка декодирования JSON в файле памяти {memory_file_path}: {e}")
        except Exception as e:
            logger.error(f"Неизвестная ошибка при миграции памяти для {character_name}: {e}", exc_info=True)

    def run_migration(self):
        """Запускает процесс миграции для всех найденных персонажей."""
        logger.info("Запуск процесса миграции старых JSON-файлов в SQLite...")
        character_names = self._find_old_character_dirs()
        
        if not character_names:
            logger.info("Старые JSON-файлы истории/памяти не найдены. Миграция не требуется.")
            return False # Миграция не проводилась

        for char_name in character_names:
            logger.info(f"Миграция данных для персонажа: {char_name}")
            self._migrate_history_for_character(char_name)
            self._migrate_memory_for_character(char_name)
        
        logger.info("Процесс миграции завершен.")
        return True # Миграция проводилась

    def check_for_old_files(self) -> bool:
        """Проверяет наличие старых JSON-файлов, требующих миграции."""
        character_names = self._find_old_character_dirs()
        return bool(character_names)
