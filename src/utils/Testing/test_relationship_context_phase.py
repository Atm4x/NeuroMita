"""First-encounter marker: migration, encounter transition and prompt block."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_SRC = Path(__file__).resolve().parents[2]
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from characters.character import Character
from controllers.prompt_controller import PromptController


class _PhaseCharacter:
    char_id = "TestChar"

    def __init__(self, phase: str | None = "unmet"):
        self.phase = phase

    def get_variable(self, name, default=None):
        if name == "relationship_context_phase":
            return self.phase if self.phase is not None else default
        return default


class _StubHistory:
    def __init__(self, messages):
        self._messages = list(messages)

    def load_history(self):
        return {"messages": list(self._messages)}


class _StubResources:
    def __init__(self, history):
        self._history = history

    def history_for(self, *_args, **_kwargs):
        return self._history


class RelationshipMigrationTests(unittest.TestCase):
    def test_existing_marker_is_not_overwritten(self):
        self.assertIsNone(
            Character._relationship_phase_after_load(
                {"relationship_context_phase": "acquainted"},
                has_history=True,
                has_memory=True,
            )
        )

    def test_old_database_with_history_becomes_acquainted(self):
        self.assertEqual(
            Character._relationship_phase_after_load(
                {},
                has_history=True,
                has_memory=False,
            ),
            "acquainted",
        )

    def test_old_database_with_memory_becomes_acquainted(self):
        self.assertEqual(
            Character._relationship_phase_after_load(
                {},
                has_history=False,
                has_memory=True,
            ),
            "acquainted",
        )

    def test_fresh_database_keeps_default(self):
        self.assertIsNone(
            Character._relationship_phase_after_load(
                {},
                has_history=False,
                has_memory=False,
            )
        )


class EncounterTransitionTests(unittest.TestCase):
    def _character(self, *, history_messages=None):
        character = Character.__new__(Character)
        character.char_id = "TestChar"
        character.name = "TestChar"
        character.storage_name = "TestChar"
        character._vars = {"relationship_context_phase": "unmet"}
        character.get_variable = lambda key, default=None: character._vars.get(key, default)
        character.set_variable = lambda key, value: character._vars.__setitem__(key, value)
        character._resource_manager = _StubResources(_StubHistory(history_messages or []))
        return character

    @staticmethod
    def _assistant(event_type="chat", text="Hello there."):
        return {"role": "assistant", "event_type": event_type, "content": text}

    @staticmethod
    def _player(text="Hi."):
        return {"role": "user", "event_type": "answer", "content": text}

    def test_completed_dialog_turn_marks_acquainted(self):
        character = self._character()

        character._maybe_mark_encounter([self._player(), self._assistant()])

        self.assertEqual(character._vars["relationship_context_phase"], "acquainted")

    def test_player_earlier_in_history_is_enough(self):
        character = self._character(history_messages=[self._player()])

        character._maybe_mark_encounter([self._assistant()])

        self.assertEqual(character._vars["relationship_context_phase"], "acquainted")

    def test_autonomous_event_does_not_mark_acquainted(self):
        character = self._character(history_messages=[self._player()])

        character._maybe_mark_encounter([self._assistant(event_type="idle")])

        self.assertEqual(character._vars["relationship_context_phase"], "unmet")

    def test_reply_without_player_does_not_mark_acquainted(self):
        character = self._character()

        character._maybe_mark_encounter([self._assistant()])

        self.assertEqual(character._vars["relationship_context_phase"], "unmet")

    def test_empty_reply_does_not_mark_acquainted(self):
        character = self._character(history_messages=[self._player()])

        character._maybe_mark_encounter([self._assistant(text="   ")])

        self.assertEqual(character._vars["relationship_context_phase"], "unmet")


class FirstEncounterPromptTests(unittest.TestCase):
    def test_unmet_without_history_gets_first_encounter_block(self):
        message = PromptController._build_relationship_context_message(
            _PhaseCharacter("unmet"),
            has_history=False,
            has_summary=False,
        )

        self.assertIsNotNone(message)
        self.assertTrue(message["content"].startswith("[First Encounter]"))
        self.assertIn("Do not invent previous meetings", message["content"])

    def test_acquainted_gets_no_block(self):
        self.assertIsNone(
            PromptController._build_relationship_context_message(
                _PhaseCharacter("acquainted"),
                has_history=False,
                has_summary=False,
            )
        )

    def test_missing_marker_defaults_to_unmet(self):
        message = PromptController._build_relationship_context_message(
            _PhaseCharacter(None),
            has_history=False,
            has_summary=False,
        )

        self.assertIsNotNone(message)

    def test_contradictory_history_suppresses_block(self):
        self.assertIsNone(
            PromptController._build_relationship_context_message(
                _PhaseCharacter("unmet"),
                has_history=True,
                has_summary=False,
            )
        )


if __name__ == "__main__":
    unittest.main()
