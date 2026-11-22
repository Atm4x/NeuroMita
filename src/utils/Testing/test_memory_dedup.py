from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

PROJECT_SRC = __import__("pathlib").Path(__file__).resolve().parents[2]
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from managers.database_manager import DatabaseManager


class MemoryDedupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix="nm_dedup_")
        DatabaseManager._instance = None
        DatabaseManager._path_override = os.path.join(cls._tmp, "world.db")
        from managers.memory_manager import MemoryManager
        cls._MM = MemoryManager

    @classmethod
    def tearDownClass(cls):
        DatabaseManager._instance = None
        DatabaseManager._path_override = None

    def _fresh_mm(self, name):
        mm = self._MM(name)
        mm.rag = None
        mm._dedup_enabled = lambda: True
        mm._maintenance_enabled = lambda: True
        return mm

    def _active(self, mm):
        with mm.db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT eternal_id, priority, content, date_created, entities FROM memories "
                "WHERE character_id=? AND is_deleted=0 AND is_forgotten=0 ORDER BY eternal_id",
                (mm.storage_key,),
            )
            return cur.fetchall()

    def test_exact_replay_keeps_date_and_does_not_reindex(self):
        mm = self._fresh_mm("DedupInsert")
        date = "15.11.2025 08:10:00"
        content = "Добрая узнала о погоне из логов."
        eid1 = mm.add_memory(content, date=date, priority="normal", entities=["Kind"])
        with patch.object(mm, "_schedule_embed") as embed:
            eid2 = mm.add_memory(content, date=date, priority="high", entities=["Kind"])
            embed.assert_not_called()
        self.assertEqual(eid2, eid1)
        self.assertEqual(self._active(mm), [(eid1, "high", content, date, '["Kind"]')])

    def test_dedup_keeps_distinct_memories(self):
        mm = self._fresh_mm("DedupDistinct")
        date = "15.11.2025 08:10:00"
        claims = [
            "Игрок принёс ключ в комнату в 5 часов.",
            "Игрок не принёс ключ в комнату в 5 часов.",
            "Игрок принёс ключ в комнату в 6 часов.",
            "Ключ принёс игроку в комнату в 5 часов.",
        ]
        for claim in claims:
            mm.add_memory(claim, date=date)
        mm.add_memory(claims[0], date="18.11.2025 08:10:00")
        mm.add_memory(claims[0], date=date, entities=["PreviousPlayer"])
        self.assertEqual([row[2] for row in self._active(mm)], claims + [claims[0], claims[0]])

    def test_maintenance_collapses_accumulated_duplicates(self):
        mm = self._fresh_mm("DedupSweep")
        mm._dedup_enabled = lambda: False
        date = "15.11.2025 08:10:00"
        content = "Player promised to bring flowers tomorrow"
        eid = mm.add_memory(content, priority="normal", date=date)
        mm.add_memory(content, priority="high", date=date)
        later = mm.add_memory(content, date="17.11.2025 08:10:00")
        detail = mm.add_memory(content + " morning", date=date)
        self.assertEqual(len(self._active(mm)), 4)

        res = mm.run_maintenance()
        self.assertEqual(res["merged"], 1)
        self.assertEqual(res["clusters"], 1)

        rows = self._active(mm)
        self.assertEqual([row[0] for row in rows], [eid, later, detail])
        self.assertEqual(rows[0][1:4], ("high", content, date))
        self.assertEqual(mm.run_maintenance(), {"merged": 0, "clusters": 0})

    def test_islands_are_not_deduped(self):
        mm = self._fresh_mm("DedupIslands")
        a = mm.upsert_island("island:relationship", "We are close friends now", priority="high")
        b = mm.add_memory("We are close friends now", priority="normal")
        # Остров и обычный факт с тем же текстом не должны схлопнуться друг в друга.
        self.assertIsNotNone(a)
        self.assertIsNotNone(b)
        self.assertNotEqual(a, b)

    def test_seed_fact_does_not_restore_retired_canon_with_same_text(self):
        mm = self._fresh_mm("DedupLore")
        text = "Reports mention a blue key."
        lore = mm.seed_rag_memory(text)
        self.assertEqual(mm.retire_seed_memories([text]), 1)
        fact = mm.add_memory(text, skip_if_exists=True)
        self.assertNotEqual(lore, fact)
        self.assertEqual(mm.add_memory(text, skip_if_exists=True), fact)
        with mm.db.connection() as conn:
            states = conn.execute(
                "SELECT type, is_deleted, is_forgotten FROM memories "
                "WHERE character_id=? ORDER BY eternal_id", (mm.storage_key,),
            ).fetchall()
        self.assertEqual(states, [("seed_lore", 1, 1), ("fact", 0, 0)])


if __name__ == "__main__":
    unittest.main()
