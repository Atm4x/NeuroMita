import os
import json
import shutil
from typing import List, Dict, Any
import logging
try:
    from main_logger import logger
except ImportError:
    logger = logging.getLogger(__name__)
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.INFO)
    logger.warning("main_logger не найден, используется стандартный логгер.")
from managers.database_manager import DatabaseManager


def find_character_directories(histories_dir: str = "Histories") -> List[str]:
    """Находит директории персонажей в Histories/."""
    if not os.path.exists(histories_dir):
        logger.warning(f"Директория {histories_dir} не найдена.")
        return []
    characters = []
    for item in os.listdir(histories_dir):
        item_path = os.path.join(histories_dir, item)
        if os.path.isdir(item_path):
            characters.append(item)
    logger.info(f"Найдено {len(characters)} директорий персонажей: {characters}")
    return characters


def is_already_migrated(character_name: str, histories_dir: str = "Histories") -> bool:
    """Проверяет, мигрированы ли данные персонажа (существует .bak или данные в БД)."""
    history_file = os.path.join(histories_dir, character_name, f"{character_name}_history.json")
    memory_file = os.path.join(histories_dir, character_name, f"{character_name}_memories.json")
    history_bak = history_file + ".bak"
    memory_bak = memory_file + ".bak"
    
    # Проверяем наличие .bak файлов
    if os.path.exists(history_bak) or os.path.exists(memory_bak):
        logger.info(f"Данные персонажа {character_name} уже мигрированы (.bak файлы существуют).")
        return True
    
    # Проверяем наличие данных в БД (требует db_manager)
    # Но для автономной проверки, можно опустить или передать db_manager
    return False


def migrate_character(character_name: str, db_manager: DatabaseManager, histories_dir: str = "Histories") -> Dict[str, int]:
    """Мигрирует историю и память одного персонажа."""
    char_dir = os.path.join(histories_dir, character_name)
    if not os.path.exists(char_dir):
        logger.warning(f"Директория персонажа {char_dir} не найдена.")
        return {"history": 0, "memory": 0}
    
    history_file = os.path.join(char_dir, f"{character_name}_history.json")
    memory_file = os.path.join(char_dir, f"{character_name}_memories.json")
    
    # Проверяем на .bak
    history_bak = history_file + ".bak"
    memory_bak = memory_file + ".bak"
    if os.path.exists(history_bak) or os.path.exists(memory_file + ".bak"):
        logger.info(f"Персонаж {character_name} уже мигрирован.")
        return {"history": 0, "memory": 0}
    
    inserted = {"history": 0, "memory": 0}
    
    # Мигрируем историю
    if os.path.exists(history_file):
        inserted["history"] = db_manager.migrate_history_from_json(history_file, character_name)
        if inserted["history"] > 0:
            # Переименовываем в .bak
            shutil.move(history_file, history_bak)
            logger.info(f"Мигрировано {inserted['history']} сообщений истории для {character_name}. Файл переименован в .bak.")
        else:
            logger.warning(f"Не удалось мигрировать историю для {character_name}.")
    
    # Мигрируем память
    if os.path.exists(memory_file):
        inserted["memory"] = db_manager.migrate_memory_from_json(memory_file, character_name)
        if inserted["memory"] > 0:
            shutil.move(memory_file, memory_bak)
            logger.info(f"Мигрировано {inserted['memory']} воспоминаний для {character_name}. Файл переименован в .bak.")
        else:
            logger.warning(f"Не удалось мигрировать память для {character_name}.")
    
    return inserted


def perform_full_migration(db_manager: DatabaseManager, histories_dir: str = "Histories") -> Dict[str, Any]:
    """Выполняет полную миграцию всех персонажей."""
    characters = find_character_directories(histories_dir)
    if not characters:
        logger.info("Нет директорий персонажей для миграции.")
        return {"total_history": 0, "total_memory": 0, "migrated_characters": []}
    
    total_inserted = {"history": 0, "memory": 0}
    migrated_characters = []
    
    for char in characters:
        if is_already_migrated(char, histories_dir):
            continue
        inserted = migrate_character(char, db_manager, histories_dir)
        total_inserted["history"] += inserted["history"]
        total_inserted["memory"] += inserted["memory"]
        if inserted["history"] > 0 or inserted["memory"] > 0:
            migrated_characters.append(char)
            logger.info(f"Миграция для {char} завершена: {inserted}")
    
    logger.info(f"Полная миграция завершена. Мигрировано персонажей: {len(migrated_characters)}, всего истории: {total_inserted['history']}, памяти: {total_inserted['memory']}")
    return {
        "total_history": total_inserted["history"],
        "total_memory": total_inserted["memory"],
        "migrated_characters": migrated_characters
    }


if __name__ == "__main__":
    # Пример использования
    db = DatabaseManager()
    result = perform_full_migration(db)
    print(result)