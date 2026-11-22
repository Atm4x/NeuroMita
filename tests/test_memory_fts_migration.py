import sqlite3

from managers.database_manager import DatabaseManager


def test_legacy_fts_upgrade_preserves_sources_and_does_not_rebuild_twice():
    db = object.__new__(DatabaseManager)
    with sqlite3.connect(":memory:") as conn:
        conn.executescript("""
            CREATE TABLE memories(id INTEGER PRIMARY KEY, character_id TEXT, eternal_id INTEGER,
                content TEXT, type TEXT, entities TEXT, lore_age_days INTEGER);
            CREATE TABLE history(id INTEGER PRIMARY KEY, content TEXT, speaker TEXT);
            CREATE VIRTUAL TABLE memories_fts USING fts5(content, type);
            INSERT INTO memories VALUES(1, 'A', 10, 'A reported event', 'seed_lore', '["Orchid"]', 14);
            INSERT INTO memories VALUES(2, 'A', 11, 'A lived event', 'fact', '["Garden"]', NULL);
            INSERT INTO history VALUES(1, 'A past dialogue line', 'Player');
            INSERT INTO memories_fts(rowid, content, type) SELECT id, content, type FROM memories;
        """)
        db._fts5_checked = db._fts5_supported = True
        sources = [conn.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()
                   for table in ("memories", "history")]
        assert db._ensure_fts5_schema(conn)
        assert DatabaseManager._fts5_schema_present(conn)
        assert sources == [conn.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()
                           for table in ("memories", "history")]
        assert conn.execute("SELECT rowid FROM memories_fts WHERE memories_fts MATCH 'Orchid'").fetchall() == [(1,)]

        statements = []
        conn.set_trace_callback(statements.append)
        assert db._ensure_fts5_schema(conn)
        conn.set_trace_callback(None)
        assert not any('DROP TABLE' in sql.upper() for sql in statements)
        assert conn.execute("SELECT COUNT(*) FROM memories_fts").fetchone()[0] == 2

        conn.execute("UPDATE memories SET entities='[\"Meadow\"]' WHERE id=2")
        assert conn.execute("SELECT rowid FROM memories_fts WHERE memories_fts MATCH 'Meadow'").fetchall() == [(2,)]
        assert conn.execute("SELECT rowid FROM memories_fts WHERE memories_fts MATCH 'Garden'").fetchall() == []
        conn.execute("DELETE FROM memories WHERE id=2")
        assert conn.execute("SELECT rowid FROM memories_fts WHERE memories_fts MATCH 'Meadow'").fetchall() == []
