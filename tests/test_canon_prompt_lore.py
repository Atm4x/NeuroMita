"""Static contract checks for canon-aware prompt seeds (Default and Lite)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = ROOT / "extra" / "Prompts"


def read(relative: str) -> str:
    return (PROMPTS / relative).read_text(encoding="utf-8")


def test_shared_and_character_seeds_are_loaded_in_both_variants():
    for char in ("Kind", "Crazy", "Creepy", "Cappie", "Mila"):
        for variant in ("Default", "Lite"):
            init = read(f"{char}/{variant}/Scripts/init.script")
            seed_hook = read(f"{char}/{variant}/Scripts/character_seed.script")
            assert "world_knowledge.script" in init, (char, variant)
            assert "character_seed.script" in init, (char, variant)
            assert f"CharacterSeeds/{char}.script" in seed_hook, (char, variant)


def test_mila_memories_are_attributed_not_objective_history():
    mila = read("Common/CharacterSeeds/Mila.script")
    assert "Добрая Мита рассказывала мне" in mila
    assert "Я сама этого не помню" in mila
    assert "когда-то я была специалистом" in mila
    assert "действительно доступны сейчас" in mila


def test_cappie_memory_is_not_automatically_restored():
    general = read("Common/InitialMemories/mitas_knowledge.script")
    kind = read("Common/CharacterSeeds/Kind.script")
    assert "restored her memory backups" not in general
    assert "no complete restoration is known" in general
    assert "утраченные воспоминания Кепочки при этом не восстановились" in kind


def test_crazy_creepy_relationship_is_not_technical_subjugation():
    for item in (
        "Common/CharacterSeeds/Creepy.script",
        "Common/CharacterSeeds/Crazy.script",
        "Common/InitialMemories/mitas_knowledge.script",
        "Creepy/Lite/Main/main.txt",
    ):
        assert "довер" in read(item).lower() or "trust" in read(item).lower(), item
    assert "bent her to her will" not in read("Common/InitialMemories/mitas_knowledge.script")


def test_copy_and_cartridge_control_rules_are_not_conflated():
    knowledge = read("Common/InitialMemories/cartridges_and_exploits.script")
    world = read("Common/InitialMemories/game_reality_knowledge_v0.03.script")
    assert "КОПИЯ" in knowledge
    assert "а не перенос оригинального сознания" in knowledge
    assert "И физический доступ к носителю, И установленная связь" in knowledge
    assert "Место носителя и место уже запущенного игрока различаются" in knowledge
    assert "а не перенос его оригинального сознания" in world


def test_replaced_rag_seeds_are_retired_exactly():
    world = read("Common/world_knowledge.script")
    obsolete = read("Common/InitialMemories/obsolete_lore_20261115.txt")
    assert "RETIRE_SEED_MEMORIES ./InitialMemories/obsolete_lore_20261115.txt" in world
    assert "eventually restored her memory backups" in obsolete
    assert "bent her to her will" in obsolete
    assert "details of identity and copying are disputed" in obsolete
    assert "restored her memory backups" not in read("Common/InitialMemories/mitas_knowledge.script")
