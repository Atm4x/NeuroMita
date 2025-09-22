import sqlite3
import os
from datetime import datetime

class DatabaseManager:
    def __init__(self, db_path="data/neuromita.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = None
        self._connect()
        self._create_tables()

    def _connect(self):
        """Устанавливает соединение с базой данных."""
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row # Для доступа к столбцам по имени
            print(f"Подключено к базе данных: {self.db_path}")

    def _close(self):
        """Закрывает соединение с базой данных."""
        if self.conn:
            self.conn.close()
            self.conn = None
            print(f"Соединение с базой данных {self.db_path} закрыто.")

    def _create_tables(self):
        """Создает таблицы history и memory, если они не существуют."""
        cursor = self.conn.cursor()

        # Таблица для истории сообщений
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

        # Таблица для памяти (фактов)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character_name TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                faiss_vector BLOB
            )
        """)
        self.conn.commit()
        print("Таблицы history и memory проверены/созданы.")

    def add_history_message(self, character_name: str, role: str, content: str, timestamp: str = None, faiss_vector: bytes = None):
        """Добавляет сообщение в историю."""
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO history (character_name, role, content, timestamp, faiss_vector)
            VALUES (?, ?, ?, ?, ?)
        """, (character_name, role, content, timestamp, faiss_vector))
        self.conn.commit()
        return cursor.lastrowid

    def get_history_messages(self, character_name: str, limit: int = None):
        """Получает историю сообщений для персонажа."""
        cursor = self.conn.cursor()
        query = "SELECT id, role, content, timestamp, faiss_vector FROM history WHERE character_name = ? ORDER BY timestamp ASC"
        params = [character_name]
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_all_history_messages(self, character_name: str):
        """Получает всю историю сообщений для персонажа."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, role, content, timestamp FROM history WHERE character_name = ? ORDER BY timestamp ASC", (character_name,))
        return [dict(row) for row in cursor.fetchall()]

    def clear_history(self, character_name: str):
        """Очищает историю сообщений для персонажа."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM history WHERE character_name = ?", (character_name,))
        self.conn.commit()

    def delete_history_messages_by_ids(self, ids: list[int]):
        """Удаляет сообщения из истории по списку ID."""
        if not ids:
            return
        cursor = self.conn.cursor()
        placeholders = ','.join('?' for _ in ids)
        cursor.execute(f"DELETE FROM history WHERE id IN ({placeholders})", ids)
        self.conn.commit()

    def add_memory_fact(self, character_name: str, key: str, value: str, timestamp: str = None, faiss_vector: bytes = None):
        """Добавляет факт в память."""
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO memory (character_name, key, value, timestamp, faiss_vector)
            VALUES (?, ?, ?, ?, ?)
        """, (character_name, key, value, timestamp, faiss_vector))
        self.conn.commit()
        return cursor.lastrowid

    def get_memory_facts(self, character_name: str):
        """Получает все факты из памяти для персонажа."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, key, value, timestamp, faiss_vector FROM memory WHERE character_name = ?", (character_name,))
        return {row['key']: row['value'] for row in cursor.fetchall()}

    def get_all_memory_facts_list(self, character_name: str):
        """Получает все факты из памяти для персонажа в виде списка словарей."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, key, value, timestamp FROM memory WHERE character_name = ?", (character_name,))
        return [dict(row) for row in cursor.fetchall()]

    def update_memory_fact(self, character_name: str, key: str, value: str, timestamp: str = None, faiss_vector: bytes = None):
        """Обновляет существующий факт в памяти или добавляет новый."""
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO memory (character_name, key, value, timestamp, faiss_vector)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(character_name, key) DO UPDATE SET
                value = EXCLUDED.value,
                timestamp = EXCLUDED.timestamp,
                faiss_vector = EXCLUDED.faiss_vector
        """, (character_name, key, value, timestamp, faiss_vector))
        self.conn.commit()

    def delete_memory_fact(self, character_name: str, key: str):
        """Удаляет факт из памяти для персонажа."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM memory WHERE character_name = ? AND key = ?", (character_name, key))
        self.conn.commit()

    def clear_memory(self, character_name: str):
        """Очищает всю память для персонажа."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM memory WHERE character_name = ?", (character_name,))
        self.conn.commit()

    def get_all_character_names(self):
        """Получает список всех уникальных имен персонажей из истории и памяти."""
        cursor = self.conn.cursor()
        history_chars = cursor.execute("SELECT DISTINCT character_name FROM history").fetchall()
        memory_chars = cursor.execute("SELECT DISTINCT character_name FROM memory").fetchall()
        all_chars = set([row['character_name'] for row in history_chars] + [row['character_name'] for row in memory_chars])
        return list(all_chars)

    def __del__(self):
        self._close()
