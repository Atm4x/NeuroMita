from pathlib import Path
from types import SimpleNamespace

import pytest

from DSL.dsl_engine import DslInterpreter
from DSL.path_resolver import LocalPathResolver
from DSL.post_dsl_engine import PostDslInterpreter
from domain.roleplay import ROLEPLAY_MODE_SETTING, RoleplayMode, roleplay_spoken_text


PROMPTS = Path(__file__).resolve().parents[3] / "extra" / "Prompts"


@pytest.mark.parametrize("preset", [
    "Crazy/Default",
    "Crazy/StagesExperimental",
    "Crazy/By_mactep_kot_new_mini",
])
def test_roleplay_switches_prompt_and_asterisk_cleanup_together(preset):
    base = PROMPTS / preset
    resolver = LocalPathResolver(str(PROMPTS), str(base))
    variables = {}
    character = SimpleNamespace(
        char_id="Crazy", base_data_path=str(base), variables=variables, app_vars={},
        set_variable=variables.__setitem__,
    )
    character.dsl_interpreter = DslInterpreter(character, resolver)
    post = PostDslInterpreter(character, resolver)
    reply = "Привет. *Поправляет рукав.*"

    for mode in (*RoleplayMode, RoleplayMode.OFF):
        enabled = mode != RoleplayMode.OFF
        blocks, _ = character.dsl_interpreter.process_main_template(
            "main_template.txt",
            feature_overrides={"roleplay_mode": mode.value, "roleplay_enabled": enabled},
        )
        prompt = "\n".join(blocks)
        assert prompt.count("[Roleplay Actions]\n") == int(enabled)
        assert ("Never narrate the same action as a field, command or intent" in prompt) == enabled
        if preset != "Crazy/By_mactep_kot_new_mini":
            assert ('"text" follows [Roleplay Actions]' in prompt) == enabled
            assert ('"text" must contain ONLY spoken words' in prompt) == (not enabled)
        assert post.process(reply) == (reply if enabled else "Привет. Поправляет рукав.")
        assert "roleplay_mode" not in variables and "roleplay_enabled" not in variables
        for style, phrase in [
            (RoleplayMode.SUBTLE, "Occasionally add one short gesture"),
            (RoleplayMode.EXPRESSIVE, "Use short action beats regularly"),
            (RoleplayMode.FULL, "A purely nonverbal reply is allowed"),
        ]:
            assert (phrase in prompt) == (mode == style)


def test_roleplay_setting_uses_stable_values(monkeypatch):
    from ui.settings import dialogue_settings

    sections = []
    monkeypatch.setattr(dialogue_settings, "create_settings_section", lambda *args, **_: sections.append(args[3]))
    dialogue_settings.add_dialogue_settings_section(None, None)
    dropdown = next(item for item in sections[0] if item.get("key") == ROLEPLAY_MODE_SETTING)

    assert dropdown["type"] == "combobox"
    assert dropdown["default"] == RoleplayMode.OFF.value
    assert [RoleplayMode.from_setting(value) for _, value in dropdown["options"]] == list(RoleplayMode)
    assert RoleplayMode.from_setting(None) is RoleplayMode.OFF
    assert RoleplayMode.from_setting("invalid") is RoleplayMode.OFF


def test_only_dialogue_goes_to_voiceover():
    assert roleplay_spoken_text("Привет. *Поправляет рукав.*") == "Привет."
    assert roleplay_spoken_text("*Кивает.*") == ""
    assert roleplay_spoken_text("**Важно**: 2 * 3") == "**Важно**: 2 * 3"
