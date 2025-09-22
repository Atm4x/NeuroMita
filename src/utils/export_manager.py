import os
from datetime import datetime
from managers.database_manager import DatabaseManager
from main_logger import logger

class ExportManager:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def export_character_data_to_text(self, character_name: str, output_dir: str = "Exports"):
        """
        Экспортирует историю и память для указанного персонажа в текстовый файл.
        """
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = os.path.join(output_dir, f"{character_name}_data_export_{timestamp}.txt")

        try:
            with open(output_filename, 'w', encoding='utf-8') as f:
                f.write(f"--- Экспорт данных для персонажа: {character_name} ---\n\n")
                f.write(f"Дата экспорта: {datetime.now().isoformat()}\n\n")

                # Экспорт истории
                f.write("--- ИСТОРИЯ СООБЩЕНИЙ ---\n\n")
                history_messages = self.db_manager.get_all_history_messages(character_name)
                if history_messages:
                    for msg in history_messages:
                        f.write(f"[{msg['timestamp']}] {msg['role'].upper()}: {msg['content']}\n")
                else:
                    f.write("История сообщений отсутствует.\n")
                f.write("\n")

                # Экспорт памяти
                f.write("--- ПАМЯТЬ (ФАКТЫ) ---\n\n")
                memory_facts = self.db_manager.get_all_memory_facts_list(character_name)
                if memory_facts:
                    for fact in memory_facts:
                        f.write(f"[{fact['timestamp']}] KEY: {fact['key']}, VALUE: {fact['value']}\n")
                else:
                    f.write("Память (факты) отсутствует.\n")
                f.write("\n")

                f.write("--- Конец экспорта ---\n")
            
            logger.success(f"Данные для персонажа {character_name} успешно экспортированы в {output_filename}")
            return output_filename
        except Exception as e:
            logger.error(f"Ошибка при экспорте данных для персонажа {character_name}: {e}", exc_info=True)
            return None
