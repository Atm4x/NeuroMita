"""Contracts for shared character seeds, bilingual lexical lookup and seed retirement.

No model or live Unity session is required for these content-level checks.
"""
from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROMPTS = ROOT / "extra" / "Prompts"
CHARS = ("Crazy", "Kind", "Cappie", "Creepy", "Ghost", "Mila", "ShortHair", "Sleepy")


def _rag_facts(path: Path) -> list[str]:
    facts = []
    for row in path.read_text(encoding="utf-8").splitlines():
        if row.startswith("SEED_RAG_MEMORY "):
            fact = row.split(" | ", 1)[1].split(" ENTITIES ", 1)[0].strip()
            facts.append(fact)
    return facts


class ZeroMemoryLoreTests(unittest.TestCase):
    def test_default_and_lite_use_identical_shared_seed(self):
        for ch in CHARS:
            shared = PROMPTS / "Common" / "CharacterSeeds" / (ch + ".script")
            self.assertTrue(shared.is_file(), str(shared))
            for mode in ("Default", "Lite"):
                wrapper = PROMPTS / ch / mode / "Scripts" / "character_seed.script"
                data = wrapper.read_text(encoding="utf-8")
                self.assertIn(f"RUN ../../../Common/CharacterSeeds/{ch}.script", data)
                self.assertNotIn("SEED_RAG_MEMORY", data)
                self.assertNotIn("SEED_ISLAND", data)

    def test_character_islands_still_have_one_source(self):
        for ch in CHARS:
            text = (PROMPTS / "Common" / "CharacterSeeds" / f"{ch}.script").read_text(encoding="utf-8")
            self.assertEqual(sum(line.startswith("SEED_ISLAND relationship |") for line in text.splitlines()), 1, ch)

    def test_new_general_lore_is_rag_only(self):
        lore = PROMPTS / "Common" / "InitialMemories" / "cartridges_and_exploits.script"
        text = lore.read_text(encoding="utf-8")
        self.assertGreaterEqual(len(_rag_facts(lore)), 17)
        self.assertNotIn("SEED_MEMORY ", text)
        world = (PROMPTS / "Common" / "world_knowledge.script").read_text(encoding="utf-8")
        self.assertIn("RUN ./InitialMemories/cartridges_and_exploits.script", world)
        self.assertIn("RETIRE_SEED_MEMORIES ./InitialMemories/obsolete_lore_20261108.txt", world)
        self.assertLess(world.index("RETIRE_SEED_MEMORIES"), world.index("SEED_MEMORY"))

    def test_bilingual_terms_are_retrievable_by_sqlite_fts5(self):
        sources = (
            PROMPTS / "Common" / "InitialMemories" / "cartridges_and_exploits.script",
            PROMPTS / "Common" / "CharacterSeeds" / "Crazy.script",
            PROMPTS / "Common" / "CharacterSeeds" / "Kind.script",
        )
        conn = sqlite3.connect(":memory:")
        try:
            try:
                conn.execute("CREATE VIRTUAL TABLE lore USING fts5(content, tokenize='unicode61')")
            except sqlite3.OperationalError:
                self.skipTest("SQLite FTS5 is not available")
            for path in sources:
                conn.executemany("INSERT INTO lore(content) VALUES (?)", [(v,) for v in _rag_facts(path)])
            pairs = (
                ("крепежи", "fasteners"), ("игрок", "player"),
                ("космос", "space"), ("кошатник", "catgirl"),
                ("коридор", "corridor"), ("кулдаун", "cooldown"),
                ("ворчун", "divan"), ("запись", "recording"),
            )
            for ru, en in pairs:
                for token in (ru, en):
                    with self.subTest(token=token):
                        n = conn.execute("SELECT COUNT(*) FROM lore WHERE lore MATCH ?", (token,)).fetchone()[0]
                        self.assertGreater(n, 0, f"Missing FTS5 seed keyword: {token}")
        finally:
            conn.close()

    def test_migration_file_has_exact_unique_old_facts(self):
        path = PROMPTS / "Common" / "InitialMemories" / "obsolete_lore_20261108.txt"
        entries = [row for row in path.read_text(encoding="utf-8").splitlines()
                   if row and not row.startswith("#")]
        self.assertGreater(len(entries), 40)
        self.assertEqual(len(entries), len(set(entries)))
        self.assertIn("Мита — ИИ, живущая в доме. Она заботится об игроке.", entries)
        self.assertTrue(any("isolated loop" in line for line in entries))


if __name__ == "__main__":
    unittest.main()
