"""Focused tests for immutable shared world-time and DSL age metadata."""
from __future__ import annotations

import datetime as dt
import sqlite3
import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[2]
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from managers.lore_timeline import (
    describe_event_age, ensure_world_anchor, lore_dates_for_results,
    read_world_anchor, strip_age_before_start,
)

UTC = dt.timezone.utc
START = dt.datetime(2026, 11, 15, 12, 0, tzinfo=UTC)


class TemporaryWorldDB:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.executescript("""
            CREATE TABLE variables (
                character_id TEXT, key TEXT, value TEXT,
                PRIMARY KEY(character_id, key)
            );
            CREATE TABLE history (timestamp TEXT, role TEXT);
            CREATE TABLE memories (
                character_id TEXT, eternal_id INTEGER, lore_age_days INTEGER,
                type TEXT, is_deleted INTEGER DEFAULT 0,
                date_created TEXT
            );
        """)

    class _Connection:
        def __init__(self, conn):
            self.conn = conn

        def __enter__(self):
            return self.conn

        def __exit__(self, *exc):
            return False

    def connection(self):
        return self._Connection(self.conn)


class WorldLoreTimelineTests(unittest.TestCase):
    def setUp(self):
        self.db = TemporaryWorldDB()
        self.cur = self.db.conn.cursor()

    def tearDown(self):
        self.db.conn.close()

    def test_parse_marker_does_not_enter_content(self):
        text, age = strip_age_before_start("Normal | Я ждала игрока AGE_BEFORE_START 6mo")
        self.assertEqual(text, "Normal | Я ждала игрока")
        self.assertEqual(age, 180)
        self.assertEqual(strip_age_before_start("Normal | обычный сид"), ("Normal | обычный сид", None))
        self.assertEqual(strip_age_before_start("Normal | вчера AGE_BEFORE_START 2w")[1], 14)
        self.assertEqual(strip_age_before_start("Normal | давно AGE_BEFORE_START 2y")[1], 730)
        with self.assertRaises(ValueError):
            strip_age_before_start("Normal | ошибка AGE_BEFORE_START 0mo")
        with self.assertRaises(ValueError):
            strip_age_before_start("Normal | ошибка AGE_BEFORE_START 6months")

    def test_world_anchor_is_shared_immutable_even_after_history_cleanup(self):
        anchor = ensure_world_anchor(self.cur, now=START)
        self.assertEqual(anchor, START)
        self.cur.execute("INSERT INTO history VALUES (?, 'user')", ("2024-01-01 00:00:00",))
        self.assertEqual(ensure_world_anchor(self.cur, now=START + dt.timedelta(days=100)), START)
        self.cur.execute("DELETE FROM history")
        self.assertEqual(read_world_anchor(self.cur), START)

    def test_existing_database_uses_first_dialogue_as_migration_proxy(self):
        self.cur.execute("INSERT INTO history VALUES (?, 'user')", ("2026-09-01 10:00:00",))
        anchor = ensure_world_anchor(self.cur, now=START)
        self.assertLess(anchor, START)
        self.assertEqual(ensure_world_anchor(self.cur, now=START + dt.timedelta(days=500)), anchor)

    def test_age_grows_across_offline_time(self):
        self.assertEqual(describe_event_age(180, anchor=START, now=START), "около 6 месяцев назад")
        self.assertEqual(
            describe_event_age(180, anchor=START, now=START + dt.timedelta(days=90)),
            "около 9 месяцев назад",
        )

    def test_same_world_clock_for_two_mitas_and_no_ingestion_date_leak(self):
        ensure_world_anchor(self.cur, now=START)
        for cid in ("Kind", "Mila"):
            self.cur.execute(
                "INSERT INTO memories VALUES (?, ?, ?, 'seed_lore', 0, ?)",
                (cid, 7, 180, "15.11.2026 12:00:00"),
            )
        results = [{"source": "memory", "id": 7, "type": "seed_lore"}]
        kind = lore_dates_for_results(self.db, "Kind", results, now=START + dt.timedelta(days=90))
        mila = lore_dates_for_results(self.db, "Mila", results, now=START + dt.timedelta(days=90))
        self.assertEqual(kind, mila)
        self.assertEqual(kind[7], "около 9 месяцев назад")
        self.assertNotIn("2026", kind[7])

    def test_untimed_or_live_memories_are_not_given_fake_story_dates(self):
        ensure_world_anchor(self.cur, now=START)
        self.cur.execute(
            "INSERT INTO memories VALUES ('Kind', 11, NULL, 'seed_lore', 0, '15.11.2026')"
        )
        self.cur.execute(
            "INSERT INTO memories VALUES ('Kind', 12, 180, 'fact', 0, '15.11.2026')"
        )
        results = [
            {"source": "memory", "id": 11, "type": "seed_lore"},
            {"source": "memory", "id": 12, "type": "fact"},
        ]
        self.assertEqual(lore_dates_for_results(self.db, "Kind", results, now=START), {})


if __name__ == "__main__":
    unittest.main()
