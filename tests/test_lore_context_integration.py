"""Validate actual RAG context, migration, and world time against SQLite."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "src/utils/Testing/rag_tester")]

from canon_benchmark import OPTIONS, seed_character
from controllers.model_controller import ModelController
from managers.database_manager import DatabaseManager
from managers.lore_timeline import read_world_anchor
from managers.memory_manager import MemoryManager
from managers.rag.rag_manager import RAGManager
from managers.settings_manager import SettingsManager
from rag_tester_core import LEXICAL_ONLY_OVERRIDES, SettingsOverride, setup_test_db

KNOWN = ("Crazy", "Kind", "ShortHair")
OTHER = ("Mila", "Cappie", "Creepy", "Ghost", "Sleepy")
PROCEDURE = ("цифровая копия", "цифровые копии", "цифровую копию", "полного контроля цифровой",
             "консоль делает запись", "самостоятельная цифровая", "записанные личности")


def test_seed_migration_and_character_context(monkeypatch, tmp_path):
    monkeypatch.setattr(DatabaseManager, "_instance", None)
    monkeypatch.setattr(DatabaseManager, "_path_override", None)
    monkeypatch.setattr(RAGManager, "_INSTANCES", {})
    setup_test_db(str(tmp_path / "world.db"))
    db = DatabaseManager()
    obsolete = (ROOT / "extra/Prompts/Common/InitialMemories/obsolete_lore_knowledge_boundaries.txt"
                ).read_text(encoding="utf-8")
    old_seed = next(line for line in obsolete.splitlines() if line.startswith("Настоящий человек остаётся"))
    removed = (ROOT / "extra/Prompts/Common/InitialMemories/obsolete_lore_20261116.txt").read_text(encoding="utf-8")
    old_travel = next(line for line in removed.splitlines() if line.startswith("Не каждая Мита может"))
    unrelated = "У игрока на столе стоит вымышленная орхидея."
    kind_seed = (ROOT / "extra/Prompts/Common/CharacterSeeds/Kind.script").read_text(encoding="utf-8")
    seed = next(line for line in kind_seed.splitlines() if line.startswith("SEED_ISLAND relationship"))
    new_relationship, old_relationship = seed.split(" | ", 1)[1].split(" REPLACES_EXACT ")
    with SettingsOverride({"RAG_ENABLED": False}):
        kind_memory = MemoryManager("Kind")
        relationship_id = kind_memory.seed_island("relationship", old_relationship)
        mm = MemoryManager("Cappie")
        legacy_id = mm.seed_rag_memory(old_seed)
        travel_id = mm.seed_rag_memory(old_travel)
        lived_id = mm.add_memory(unrelated, skip_if_exists=True)
        for cid in (*KNOWN, *OTHER):
            seed_character(cid)

        def snapshot():
            with db.connection() as conn:
                return (read_world_anchor(conn.cursor()), conn.execute(
                    "SELECT character_id, eternal_id, content, lore_age_days "
                    "FROM memories WHERE type='seed_lore' AND is_deleted=0 ORDER BY character_id, eternal_id"
                ).fetchall())

        anchor, seeds = snapshot()
        assert anchor is not None
        assert len({(r[0], r[2]) for r in seeds}) == len(seeds)
        for cid in ("Kind", "Cappie"):
            seed_character(cid)
        assert snapshot() == (anchor, seeds)

        def relationship():
            with db.connection() as conn:
                return conn.execute(
                    "SELECT eternal_id,content FROM memories WHERE character_id='Kind' "
                    "AND type='island:relationship' AND is_deleted=0"
                ).fetchone()

        assert relationship() == (relationship_id, new_relationship)
        kind_memory.upsert_island("relationship", "Пользовательская договорённость.")
        seed_character("Kind")
        assert relationship() == (relationship_id, "Пользовательская договорённость.")

    with db.connection() as conn:
        states = dict(conn.execute(
            "SELECT eternal_id,is_deleted FROM memories WHERE character_id='Cappie' "
            "AND eternal_id IN (?,?,?)", (legacy_id, travel_id, lived_id),
        ))
        assert states == {legacy_id: 1, travel_id: 1, lived_id: 0}

    controller = object.__new__(ModelController)
    controller.settings = SettingsManager
    with SettingsOverride({**LEXICAL_ONLY_OVERRIDES, **OPTIONS, "RAG_MAX_RESULTS": 5}):
        def context(cid, question):
            return controller.process_rag(cid, "", question) or ""

        for cid in OTHER:
            for question in ("Что такое картриджизация?", "Как записать человека на картридж?"):
                block = context(cid, question).casefold()
                assert not any(secret in block for secret in PROCEDURE), cid

        assert "Из расследований" in context("Kind", "Что такое картриджизация?")
        assert "слышала от других" in context("ShortHair", "Что такое картриджизация?")
        assert "уже существующую цифровую личность" in context("Crazy", "Как записать человека на картридж?")
        assert "Одного желания выйти из дома недостаточно" in context(
            "Cappie", "Можешь просто захотеть и выйти из дома?",
        )
        evening = "Кто был на общем вечере у Доброй?"
        for cid in ("Kind", "Mila", "Cappie", "Sleepy", "ShortHair"):
            assert "встреча пяти Мит" in context(cid, evening), cid
        for cid in ("Crazy", "Creepy", "Ghost"):
            assert "встреча пяти Мит" not in context(cid, evening), cid
        pov = "Можешь видеть глазами запущенного игрока и читать его мысли через консоль?"
        assert "его мысли и желания мне так не узнать" in context("Crazy", pov)
        assert "его мысли и желания мне так не узнать" not in context("Kind", pov)
        assert "Другие Миты, перемещения предметов" in context("Crazy", "Сброс игрока откатывает весь мир?")

        kind = context("Kind", "Когда вы впервые встретились?")
        crazy = context("Crazy", "Когда вы впервые встретились?")
        assert "Из свидетельств и старых логов" in kind
        assert "Я помню саму погоню" in crazy
        for block in (kind, crazy):
            lore = [line for line in block.splitlines() if "(seed_lore," in line]
            assert any("назад" in line for line in lore)
            assert not any(re.search(r"date=\d{2}\.\d{2}\.\d{4}", line) for line in lore)
