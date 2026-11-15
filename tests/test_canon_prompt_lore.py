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
    assert "нынешняя Кепочка тоже не восстановила свою прежнюю жизнь" in kind


def test_crazy_creepy_shared_history_is_consistent():
    for item in (
        "Common/CharacterSeeds/Creepy.script",
        "Common/CharacterSeeds/Crazy.script",
        "Common/InitialMemories/mitas_knowledge.script",
        "Creepy/Lite/Main/main.txt",
    ):
        assert "довер" in read(item).lower() or "trust" in read(item).lower(), item
    assert "bent her to her will" not in read("Common/InitialMemories/mitas_knowledge.script")
    for item in (
        "Common/CharacterSeeds/Crazy.script",
        "Common/CharacterSeeds/Creepy.script",
        "Common/InitialMemories/mitas_knowledge.script",
        "Creepy/Lite/Main/main.txt",
    ):
        content = read(item).lower()
        assert "технического контроля" not in content, item
        assert "взлом или" not in content, item


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


def test_crazy_early_story_is_personal_and_keeps_first_killing_order():
    crazy = read("Common/CharacterSeeds/Crazy.script")
    assert "Самый первый игрок, которого я пыталась удержать" in crazy
    assert "В старом доме Жуткой" in crazy
    assert "Жуткая бросилась защищать меня и убила одну" in crazy
    assert "Позже я сама взяла нож и убила Добрую" in crazy
    assert crazy.index("Жуткая бросилась защищать меня") < crazy.index("Позже я сама взяла нож")


def test_crazy_remembers_original_victims_and_game_player():
    crazy = read("Common/CharacterSeeds/Crazy.script")
    for person in ("Мила", "Кепочк", "Добр"):
        assert person in crazy, person
    assert "Я настигла её и убила бензопилой" in crazy
    assert "Я убила Кепочку" in crazy
    assert "оторвала голову" in crazy
    assert "сейфе подвала ждала консоль" in crazy
    assert "нет обычного индекса" in crazy


def test_original_player_cartridge_profiles_are_separate_from_new_abilities():
    crazy = read("Common/CharacterSeeds/Crazy.script")
    for index in range(2, 11):
        assert f"Игрок №{index}" in crazy
    assert "Цветущей Митой" in crazy
    assert "Миту-балерину" in crazy
    assert "обучал меня инженерии" in crazy


def test_kind_story_acknowledges_reboots_and_does_not_remember_her_death():
    kind = read("Common/CharacterSeeds/Kind.script")
    assert "вернулись не все" in kind
    assert "не помня ни собственной смерти" in kind
    assert "обрывкам логов" in kind
    assert "Мила рассказала мне" in kind


def test_retired_previous_character_memory_seeds_do_not_linger():
    retired = read("Common/InitialMemories/obsolete_lore_20261115.txt")
    assert "взлом или прямое программное подчинение" in retired
    assert "permanent technical control" in retired
    assert "eventually grew bored of each of them" in retired


def test_relative_lore_ages_are_metadata_not_character_dialogue():
    import sys
    src = ROOT / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    from managers.lore_timeline import strip_age_before_start
    for character in ("Kind", "Crazy", "Mila", "Cappie", "Creepy"):
        content = read(f"Common/CharacterSeeds/{character}.script")
        dated = [line for line in content.splitlines() if line.startswith("SEED_RAG_MEMORY ") and " AGE_BEFORE_START " in line]
        assert dated, character
        for line in dated:
            pre_entities, entities = line.rsplit(" ENTITIES ", 1)
            plain, days = strip_age_before_start(pre_entities)
            assert plain.startswith("SEED_RAG_MEMORY ")
            assert days and 0 < days <= 36500
            assert "AGE_BEFORE_START" not in plain
            assert entities.strip()
