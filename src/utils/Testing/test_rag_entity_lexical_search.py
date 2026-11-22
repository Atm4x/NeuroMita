"""Entity-aware lexical recall without a vector model."""
from __future__ import annotations

import sqlite3
import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[2]
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from managers.database_manager import DatabaseManager
from managers.rag.pipeline.repositories.memory_repo import MemoryRepository
from managers.rag.pipeline.types import SchemaInfo
from managers.rag.rag_utils import entity_alias_phrases, keyword_score


class EntityLexicalSearchTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        try:
            self.conn.execute("CREATE VIRTUAL TABLE fts_probe USING fts5(content)")
            self.conn.execute("DROP TABLE fts_probe")
        except sqlite3.OperationalError:
            self.skipTest("SQLite FTS5 is unavailable")
        self.conn.executescript("""
            CREATE TABLE history (id INTEGER PRIMARY KEY, content TEXT, character_id TEXT);
            CREATE TABLE memories (
                id INTEGER PRIMARY KEY, eternal_id INTEGER, character_id TEXT,
                content TEXT, type TEXT, priority TEXT, date_created TEXT,
                participants TEXT, entities TEXT, is_deleted INTEGER DEFAULT 0,
                embedding BLOB, is_forgotten INTEGER DEFAULT 0
            );
            INSERT INTO memories
                (id, eternal_id, character_id, content, type, priority, entities)
            VALUES (1, 1, 'crazy', 'Я сама взяла нож.', 'fact', 'Normal',
                    '["Crazy Mita", "Kind Mita"]');
            CREATE VIRTUAL TABLE memories_fts USING fts5(content, type, priority, participants);
            INSERT INTO memories_fts(rowid, content, type, priority, participants)
            SELECT id, content, type, priority, COALESCE(participants, '') FROM memories;
        """)
        # Isolated instance: no singleton, application DB or embedding service.
        self.db = object.__new__(DatabaseManager)
        self.db.sqlite_supports_fts5 = lambda: True

    def tearDown(self):
        self.conn.close()

    def test_existing_index_upgrades_and_keeps_text(self):
        self.assertFalse(self.db._fts5_schema_present(self.conn))
        self.assertTrue(self.db._ensure_fts5_schema(self.conn))
        self.assertTrue(self.db._fts5_schema_present(self.conn))
        self.assertEqual(
            self.conn.execute('SELECT rowid FROM memories_fts WHERE memories_fts MATCH ?', ('"Crazy Mita"',)).fetchall(),
            [(1,)],
        )
        self.assertEqual(self.conn.execute("SELECT content FROM memories WHERE id=1").fetchone()[0],
                         "Я сама взяла нож.")

    def test_entity_update_changes_fts_matches(self):
        self.assertTrue(self.db._ensure_fts5_schema(self.conn))
        self.conn.execute("UPDATE memories SET entities=? WHERE id=1", ('["Flower Mita"]',))
        self.assertEqual(
            self.conn.execute('SELECT rowid FROM memories_fts WHERE memories_fts MATCH ?', ('"Crazy Mita"',)).fetchall(),
            [],
        )
        self.assertEqual(
            self.conn.execute('SELECT rowid FROM memories_fts WHERE memories_fts MATCH ?', ('"Flower Mita"',)).fetchall(),
            [(1,)],
        )

    def test_keyword_fallback_matches_entities_without_embeddings(self):
        schema = SchemaInfo(
            history_cols=frozenset({"content", "character_id"}),
            mem_cols=frozenset({"content", "entities", "embedding", "is_deleted", "is_forgotten", "type"}),
        )
        repo = MemoryRepository(self.db, "crazy", schema)
        rows = repo.keyword_rows(self.conn.cursor(), keywords=["Crazy Mita"], limit=10)
        self.assertEqual([row["eternal_id"] for row in rows], [1])
        score, matches = keyword_score(
            ["Crazy Mita"], rows[0]["content"] + " Crazy Mita Kind Mita",
        )
        self.assertEqual((score, matches), (1.0, 1))

    def test_localized_aliases(self):
        self.assertIn("Crazy Mita", entity_alias_phrases("Что делала Безумная Мита?"))
        self.assertIn("Crazy Mita", entity_alias_phrases("Почему Безумная сбежала?"))
        self.assertIn("Kind Mita", entity_alias_phrases("Чем занималась Добрая Мита?"))
        self.assertIn("Безумная Мита", entity_alias_phrases("Tell me about Crazy Mita"))
        self.assertIn("Добрая Мита", entity_alias_phrases("Tell me about Kind Mita"))
        self.assertEqual(entity_alias_phrases("Расскажи про нож"), [])


if __name__ == "__main__":
    unittest.main()
