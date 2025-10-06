import sqlite3
import os
import json
from contextlib import contextmanager
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

class DatabaseManager:
    """
    Централизованный менеджер для работы с SQLite базой данных neuromita.db.
    Хранит историю чатов и память персонажей.
    """
    _instance = None
    _lock = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, db_path: str = "neuromita.db"):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True
        self.db_path = db_path
        self._ensure_db_directory()
        if self._lock is None:
            import threading
            self._lock = threading.Lock()
        self.create_tables()

    def _ensure_db_directory(self):
        """Обеспечивает существование директории для БД."""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)

    @contextmanager
    def get_connection(self):
        """Контекстный менеджер для соединения с БД."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Для доступа по именам колонок
            conn.execute("PRAGMA foreign_keys=ON")  # Включаем foreign keys если нужно
            conn.execute("PRAGMA busy_timeout=5000")  # Таймаут для busy locks
            try:
                yield conn
                conn.commit()
            except Exception as e:
                logger.error(f"Database error: {e}")
                conn.rollback()
                raise
            finally:
                conn.close()

    def create_tables(self):
        """Создает таблицы history, memory и history_metadata, если они не существуют."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Включаем WAL mode для лучшей concurrency
            cursor.execute("PRAGMA journal_mode=WAL")

            # Таблица history
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    character_name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    faiss_vector BLOB
                )
            """)

            # Таблица history_metadata для fixed_parts, temp_context, variables
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS history_metadata (
                    character_name TEXT PRIMARY KEY,
                    fixed_parts TEXT DEFAULT '[]',
                    temp_context TEXT DEFAULT '[]',
                    variables TEXT DEFAULT '{}'
                )
            """)

            # Таблица memory
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    character_name TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    priority TEXT DEFAULT 'medium',
                    memory_type TEXT DEFAULT 'fact',
                    timestamp TEXT NOT NULL,
                    faiss_vector BLOB
                )
            """)

    # Методы для таблицы history

    def insert_history_message(self, character_name: str, role: str, content: str,
                               timestamp: Optional[str] = None,
                               faiss_vector: Optional[bytes] = None) -> int:
        """Вставляет новое сообщение в историю."""
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO history (character_name, role, content, timestamp, faiss_vector)
                VALUES (?, ?, ?, ?, ?)
            """, (character_name, role, content, timestamp, faiss_vector))
            return cursor.lastrowid

    def get_history(self, character_name: str, limit: Optional[int] = None,
                    order: str = 'ASC', include_id: bool = False) -> List[Dict[str, Any]]:
        """Получает историю сообщений для персонажа."""
        if include_id:
            select_fields = "*"
            return_format = lambda rows: [dict(row) for row in rows]
        else:
            select_fields = "role, content, timestamp"
            return_format = lambda rows: [{'role': row['role'], 'content': row['content'], 'timestamp': row['timestamp']} for row in rows]
        order_by = 'ASC' if order == 'ASC' else 'DESC'
        query = f"""
            SELECT {select_fields} FROM history
            WHERE character_name = ?
            ORDER BY timestamp {order_by}
        """
        params = [character_name]
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return return_format(rows)

    def get_history_metadata(self, character_name: str) -> Dict[str, Any]:
        """Получает метаданные истории (fixed_parts, temp_context, variables)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT fixed_parts, temp_context, variables FROM history_metadata
                WHERE character_name = ?
            """, (character_name,))
            row = cursor.fetchone()
            if row:
                import json
                return {
                    'fixed_parts': json.loads(row['fixed_parts']),
                    'temp_context': json.loads(row['temp_context']),
                    'variables': json.loads(row['variables'])
                }
            return {'fixed_parts': [], 'temp_context': [], 'variables': {}}

    def update_history_metadata(self, character_name: str, metadata: Dict[str, Any]):
        """Обновляет метаданные истории."""
        import json
        fixed_parts_json = json.dumps(metadata.get('fixed_parts', []), ensure_ascii=False)
        temp_context_json = json.dumps(metadata.get('temp_context', []), ensure_ascii=False)
        variables_json = json.dumps(metadata.get('variables', {}), ensure_ascii=False)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO history_metadata (character_name, fixed_parts, temp_context, variables)
                VALUES (?, ?, ?, ?)
            """, (character_name, fixed_parts_json, temp_context_json, variables_json))

    def get_history_messages_for_compression(self, character_name: str,
                                             num_messages: int) -> List[Dict[str, Any]]:
        """Получает oldest num_messages сообщений для сжатия (ORDER ASC)."""
        full_history = self.get_history(character_name, limit=num_messages, order='ASC', include_id=True)
        # Фильтруем только user/assistant
        filtered = [msg for msg in full_history if msg['role'] in ['user', 'assistant']]
        messages_to_compress = filtered[:num_messages]
        # Extract ids for deletion
        ids_to_delete = [msg['id'] for msg in messages_to_compress]
        self.delete_history_messages_by_ids(ids_to_delete)
        # Return without id
        return [{'role': msg['role'], 'content': msg['content'], 'timestamp': msg['timestamp']} for msg in messages_to_compress]

    def clear_history(self, character_name: str):
        """Очищает историю для персонажа."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM history WHERE character_name = ?", (character_name,))
        # Also clear metadata
        cursor.execute("DELETE FROM history_metadata WHERE character_name = ?", (character_name,))

    def delete_history_messages_by_ids(self, ids: List[int]):
        """Удаляет сообщения по IDs."""
        if not ids:
            return
        placeholders = ','.join('?' * len(ids))
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM history WHERE id IN ({placeholders})", ids)

    def replace_history_messages(self, character_name: str, messages: List[Dict[str, Any]]):
        """Заменяет все сообщения истории новыми (для сохранения совместимости)."""
        self.clear_history(character_name)
        for msg in messages:
            self.insert_history_message(
                character_name,
                msg['role'],
                msg['content'],
                msg.get('timestamp', datetime.now().isoformat()),
                msg.get('faiss_vector')
            )

    def update_history_vector(self, message_id: int, faiss_vector: bytes):
        """Обновляет вектор для сообщения в истории."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE history SET faiss_vector = ? WHERE id = ?
            """, (faiss_vector, message_id))

    # Методы для таблицы memory

    def insert_memory(self, character_name: str, key: str, value: str,
                      priority: str = 'medium', memory_type: str = 'fact',
                      timestamp: Optional[str] = None,
                      faiss_vector: Optional[bytes] = None) -> int:
        """Вставляет новую запись в память."""
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO memory (character_name, key, value, priority, memory_type, timestamp, faiss_vector)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (character_name, key, value, priority, memory_type, timestamp, faiss_vector))
            return cursor.lastrowid

    def get_memories(self, character_name: str, limit: Optional[int] = None,
                     order: str = 'DESC') -> List[Dict[str, Any]]:
        """Получает воспоминания для персонажа."""
        query = """
            SELECT * FROM memory
            WHERE character_name = ?
            ORDER BY timestamp {}
        """.format('DESC' if order == 'DESC' else 'ASC')
        params = [character_name]
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def update_memory(self, memory_id: int, **kwargs):
        """Обновляет запись в памяти."""
        if not kwargs:
            return
        set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values()) + [memory_id]
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                UPDATE memory SET {set_clause} WHERE id = ?
            """, values)

    def delete_memory(self, memory_id: int):
        """Удаляет воспоминание по ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM memory WHERE id = ?", (memory_id,))

    def clear_memory(self, character_name: str):
        """Очищает память для персонажа."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM memory WHERE character_name = ?", (character_name,))

    def update_memory_vector(self, memory_id: int, faiss_vector: bytes):
        """Обновляет вектор для воспоминания."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE memory SET faiss_vector = ? WHERE id = ?
            """, (faiss_vector, memory_id))

    # Placeholder методы для FAISS

    def get_vectors_for_search(self, table: str, character_name: str) -> List[Tuple[int, bytes]]:
        """Получает ID и векторы для поиска (placeholder для FAISS)."""
        if table not in ['history', 'memory']:
            raise ValueError("Invalid table")
        query = f"SELECT id, faiss_vector FROM {table} WHERE character_name = ? AND faiss_vector IS NOT NULL"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (character_name,))
            return [(row['id'], row['faiss_vector']) for row in cursor.fetchall()]

    # Методы для миграции

    def migrate_history_from_json(self, json_path: str, character_name: str) -> int:
        """Мигрирует историю из JSON-файла в БД, включая метаданные."""
        if not os.path.exists(json_path):
            return 0
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            messages = data.get('messages', [])
            inserted = 0
            for msg in messages:
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')
                timestamp = msg.get('timestamp', datetime.now().isoformat())
                self.insert_history_message(character_name, role, content, timestamp)
                inserted += 1
            # Migrate metadata
            metadata = {
                'fixed_parts': data.get('fixed_parts', []),
                'temp_context': data.get('temp_context', []),
                'variables': data.get('variables', {})
            }
            self.update_history_metadata(character_name, metadata)
            return inserted
        except Exception as e:
            print(f"Ошибка миграции истории из {json_path}: {e}")
            return 0

    def export_history_to_json(self, character_name: str, output_path: str):
        """Экспортирует историю и метаданные в JSON для бэкапа."""
        metadata = self.get_history_metadata(character_name)
        messages = self.get_history(character_name, order='ASC')
        export_data = {
            'fixed_parts': metadata['fixed_parts'],
            'messages': messages,
            'temp_context': metadata['temp_context'],
            'variables': metadata['variables']
        }
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=4, default=str)

    def export_memory_to_txt(self, character_name: str, output_path: str):
        """Экспортирует память в читаемый TXT файл."""
        memories = self.get_memories(character_name, order='ASC')
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"Память персонажа: {character_name}\n")
            f.write("=" * 50 + "\n\n")
            for mem in memories:
                f.write(f"ID: {mem['id']}\n")
                f.write(f"Ключ: {mem['key']}\n")
                f.write(f"Значение: {mem['value']}\n")
                f.write(f"Приоритет: {mem['priority']}\n")
                f.write(f"Тип: {mem['memory_type']}\n")
                f.write(f"Время: {mem['timestamp']}\n")
                f.write("-" * 30 + "\n\n")

    def export_history_to_txt(self, character_name: str, output_path: str):
        """Экспортирует историю в читаемый TXT файл."""
        metadata = self.get_history_metadata(character_name)
        messages = self.get_history(character_name, order='ASC')
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"История персонажа: {character_name}\n")
            f.write("=" * 50 + "\n\n")
            if metadata['fixed_parts']:
                f.write("Фиксированные части:\n")
                for part in metadata['fixed_parts']:
                    f.write(f"- {part}\n")
                f.write("\n")
            f.write("Сообщения:\n")
            for msg in messages:
                f.write(f"Роль: {msg['role']}\n")
                f.write(f"Содержимое: {msg['content']}\n")
                f.write(f"Время: {msg['timestamp']}\n")
                f.write("-" * 30 + "\n\n")

    def export_character_data(self, character_name: str, output_dir: str, format_type: str = 'json'):
        """Экспортирует историю и память персонажа в файлы (JSON или TXT)."""
        os.makedirs(output_dir, exist_ok=True)
        if format_type == 'txt':
            history_path = os.path.join(output_dir, f"{character_name}_history.txt")
            memory_path = os.path.join(output_dir, f"{character_name}_memory.txt")
            self.export_history_to_txt(character_name, history_path)
            self.export_memory_to_txt(character_name, memory_path)
            logger.info(f"Экспорт в TXT для {character_name}: {history_path}, {memory_path}")
        else:  # json
            history_path = os.path.join(output_dir, f"{character_name}_history.json")
            memory_path = os.path.join(output_dir, f"{character_name}_memory.json")
            self.export_history_to_json(character_name, history_path)
            memories = self.get_memories(character_name)
            with open(memory_path, 'w', encoding='utf-8') as f:
                json.dump({'memories': memories}, f, ensure_ascii=False, indent=4, default=str)
            logger.info(f"Экспорт в JSON для {character_name}: {history_path}, {memory_path}")
        return output_dir

    def migrate_memory_from_json(self, json_path: str, character_name: str) -> int:
        """Мигрирует память из JSON-файла в БД."""
        if not os.path.exists(json_path):
            return 0
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            memories = data.get('memories', [])
            inserted = 0
            for mem in memories:
                key = mem.get('key', '')
                value = mem.get('value', '')
                priority = mem.get('priority', 'medium')
                memory_type = mem.get('type', 'fact')
                timestamp = mem.get('timestamp', datetime.now().isoformat())
                self.insert_memory(character_name, key, value, priority, memory_type, timestamp)
                inserted += 1
            return inserted
        except Exception as e:
            print(f"Ошибка миграции памяти из {json_path}: {e}")
            return 0

    # Метод для экспорта (для пункта 8)

    def export_to_json(self, character_name: str, output_path: str):
        """Экспортирует историю и память в JSON-файл."""
        history = self.get_history(character_name)
        memories = self.get_memories(character_name)
        export_data = {
            'character_name': character_name,
            'history': {'messages': history},
            'memory': {'memories': memories}
        }
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=4, default=str)