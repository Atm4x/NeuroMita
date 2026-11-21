from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from DSL.dsl_engine import DslInterpreter
from DSL.post_dsl_engine import PostDslInterpreter
from ui.settings.dialogue_settings import add_dialogue_settings_section


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PROMPTS_ROOT = PROJECT_ROOT / "extra" / "Prompts"


class _PromptResolver:
    def __init__(self, files: dict[str, str]):
        self.files = files

    def resolve_path(self, path: str) -> str:
        return path

    def load_text(self, path: str, _context: str) -> str:
        return self.files[path]

    def get_dirname(self, _path: str) -> str:
        return ""


class _PostResolver:
    def __init__(self, script: str):
        self.script = script

    def resolve_path(self, path: str) -> str:
        return path

    def load_text(self, _path: str, _context: str) -> str:
        return self.script


class _Character:
    def __init__(self, variables: dict | None = None):
        self.char_id = "Test"
        self.base_data_path = "."
        self.variables = dict(variables or {})
        self.app_vars = {}

    def set_variable(self, key: str, value) -> None:
        self.variables[key] = value


class RoleplayPromptTests(unittest.TestCase):
    def _render_prompt(self, enabled: bool) -> str:
        files = {
            "main_template.txt": "[<format.script>]\n[<dialogue.txt>]\n",
            "format.script": (
                PROMPTS_ROOT / "Structural" / "response_format_json.script"
            ).read_text(encoding="utf-8"),
            "dialogue.txt": (
                PROMPTS_ROOT / "Common" / "Dialogue.txt"
            ).read_text(encoding="utf-8"),
        }
        variables = {
            "SCHEMA_REASONING_ENABLED": False,
            "ENABLE_GAMES": False,
            "GRAPH_EXTRACTION_ENABLED": False,
            "RAG_ENABLED": False,
            "MITA_CAMERA_ENABLED": False,
            "MITA_CAMERA_ON_DEMAND": False,
            "TOOLS_DESCRIPTION": "",
            "CUSTOM_PARAMS_SCHEMA": "",
        }
        character = _Character(variables)
        interpreter = DslInterpreter(character, _PromptResolver(files))
        blocks, _system_messages = interpreter.process_main_template(
            "main_template.txt",
            feature_overrides={
                "support_intents": True,
                "response_sparse_format": False,
                "roleplay_actions": enabled,
            },
        )
        return "\n".join(blocks)

    def test_roleplay_instructions_are_absent_when_disabled(self):
        rendered = self._render_prompt(False)

        self.assertIn('"text" must contain ONLY spoken words', rendered)
        self.assertIn("Do not narrate the event; respond to it.", rendered)
        self.assertNotIn("[RP Action Fallback]", rendered)

    def test_roleplay_instructions_are_added_when_enabled(self):
        rendered = self._render_prompt(True)

        self.assertIn("[RP Action Fallback]", rendered)
        self.assertIn("never both perform and narrate the same action", rendered.lower())
        self.assertNotIn("ONLY spoken words", rendered)
        self.assertNotIn("Do not narrate the event; respond to it.", rendered)


class PostDslConditionalRuleTests(unittest.TestCase):
    ASTERISK_SCRIPT = r"""
RULE RemoveAsterisks
    WHEN default("ROLEPLAY_ACTIONS_ENABLED", False) == False
    MATCH REGEX "(\*{1,3})"
    ACTIONS
        REMOVE_MATCH
    END_ACTIONS
END_RULE
"""

    FIELD_SCRIPT = """
RULE SetScoreWhenEnabled
    WHEN ROLEPLAY_ACTIONS_ENABLED == True
    MATCH FIELD "delta"
    ACTIONS
        SET score = delta
    END_ACTIONS
END_RULE
"""

    def _interpreter(self, script: str, enabled: bool | None):
        variables = {}
        if enabled is not None:
            variables["ROLEPLAY_ACTIONS_ENABLED"] = enabled
        character = _Character(variables)
        return PostDslInterpreter(character, _PostResolver(script)), character

    def test_asterisks_are_removed_when_roleplay_is_disabled(self):
        interpreter, _character = self._interpreter(self.ASTERISK_SCRIPT, False)

        self.assertEqual(interpreter.process("*обняла*"), "обняла")

    def test_asterisks_are_preserved_when_roleplay_is_enabled(self):
        interpreter, _character = self._interpreter(self.ASTERISK_SCRIPT, True)

        self.assertEqual(interpreter.process("*обняла*"), "*обняла*")

    def test_missing_setting_keeps_legacy_asterisk_cleanup(self):
        interpreter, _character = self._interpreter(self.ASTERISK_SCRIPT, None)

        self.assertEqual(interpreter.process("*обняла*"), "обняла")

    def test_when_condition_also_gates_structured_field_rules(self):
        disabled, disabled_character = self._interpreter(self.FIELD_SCRIPT, False)
        enabled, enabled_character = self._interpreter(self.FIELD_SCRIPT, True)

        disabled.process_structured_fields({"delta": 3})
        enabled.process_structured_fields({"delta": 3})

        self.assertNotIn("score", disabled_character.variables)
        self.assertEqual(enabled_character.variables["score"], 3)


class RoleplaySettingsTests(unittest.TestCase):
    @patch("ui.settings.dialogue_settings.create_settings_section")
    def test_roleplay_actions_setting_is_opt_in(self, create_section):
        add_dialogue_settings_section(SimpleNamespace(), object())

        config = create_section.call_args.args[3]
        setting = next(
            item for item in config
            if item.get("key") == "ROLEPLAY_ACTIONS_ENABLED"
        )

        self.assertEqual(setting["type"], "checkbutton")
        self.assertIs(setting["default_checkbutton"], False)
        self.assertEqual(setting["widget_name"], "ROLEPLAY_ACTIONS_ENABLED")


if __name__ == "__main__":
    unittest.main()
