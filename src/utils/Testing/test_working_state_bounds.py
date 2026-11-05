"""Working-state limits, stale-epoch protection and prompt rendering."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_SRC = Path(__file__).resolve().parents[2]
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from domain.working_state import (
    FOCUS_MAX_CHARS,
    ITEM_MAX_CHARS,
    MAX_NEXT_STEPS,
    MAX_OPEN_LOOPS,
    content_length,
    normalize_working_state_update,
    working_state_transition,
)
from managers.working_state_manager import WorkingStateManager
from schemas.structured_response import StructuredResponse


class WorkingStateNormalizationTests(unittest.TestCase):
    def test_item_counts_and_lengths_are_capped(self):
        state = normalize_working_state_update({
            "focus": "f" * (FOCUS_MAX_CHARS + 50),
            "open_loops": [f"loop {index}" for index in range(6)],
            "next_steps": ["s" * (ITEM_MAX_CHARS + 80), "b", "c", "d"],
        })
        self.assertIsNotNone(state)
        self.assertEqual(len(state["focus"]), FOCUS_MAX_CHARS)
        self.assertEqual(len(state["open_loops"]), MAX_OPEN_LOOPS)
        self.assertEqual(len(state["next_steps"]), MAX_NEXT_STEPS)
        self.assertEqual(len(state["next_steps"][0]), ITEM_MAX_CHARS)

    def test_total_budget_drops_least_important_fields(self):
        state = normalize_working_state_update({
            "focus": "Keep the focus",
            "situation": ["s" * 120 for _ in range(3)],
            "assumptions": ["a" * 120 for _ in range(3)],
            "open_loops": ["o" * 120 for _ in range(3)],
            "next_steps": ["n" * 120 for _ in range(2)],
        }, max_chars=400)
        self.assertIsNotNone(state)
        self.assertLessEqual(content_length(state), 400)
        self.assertEqual(state.get("focus"), "Keep the focus")
        self.assertNotIn("assumptions", state)

    def test_scalar_and_string_list_shapes_are_accepted(self):
        self.assertEqual(
            normalize_working_state_update("Just focus"),
            {"focus": "Just focus"},
        )
        self.assertEqual(
            normalize_working_state_update({"open_loops": "one loop"}),
            {"open_loops": ["one loop"]},
        )

    def test_empty_update_is_rejected(self):
        self.assertIsNone(normalize_working_state_update({}))
        self.assertIsNone(normalize_working_state_update("   "))
        self.assertIsNone(normalize_working_state_update(None))


class WorkingStateManagerTests(unittest.TestCase):
    def _manager(self):
        return WorkingStateManager().bind("Mita", "Mita")

    def test_empty_update_keeps_last_valid_state(self):
        manager = self._manager()
        self.assertTrue(manager.update({"focus": "Keep me"}))

        self.assertFalse(manager.update({}))
        self.assertFalse(manager.update({"unknown": "value"}))
        self.assertIn("Keep me", manager.format_for_prompt())

    def test_stale_epoch_update_is_dropped(self):
        manager = self._manager()
        self.assertTrue(manager.update({"focus": "Before reset"}, epoch=1))

        manager.clear(epoch=2)

        self.assertFalse(manager.update({"focus": "Late reply"}, epoch=1))
        self.assertEqual(manager.format_for_prompt(), "")
        self.assertTrue(manager.update({"focus": "Current story"}, epoch=2))
        self.assertIn("Current story", manager.format_for_prompt())

    def test_render_marks_state_as_interpretation_not_fact(self):
        manager = self._manager()
        manager.update({
            "focus": "Finish the test",
            "open_loops": ["Check the music"],
            "next_steps": ["Answer briefly"],
        })
        prompt = manager.format_for_prompt()
        self.assertTrue(prompt.startswith("[WORKING STATE]"))
        self.assertIn("not established fact", prompt)
        self.assertIn("take precedence", prompt)
        self.assertIn("Focus: Finish the test", prompt)

    def test_snapshot_round_trip_keeps_fields(self):
        manager = self._manager()
        manager.update({"focus": "Snapshot", "situation": ["context"]})
        snapshot = manager.snapshot()

        manager.clear()
        self.assertEqual(manager.format_for_prompt(), "")

        manager.restore_snapshot(snapshot)
        self.assertIn("Snapshot", manager.format_for_prompt())


class WorkingStateTransitionTests(unittest.TestCase):
    """An omitted optional field must not erase the previous handoff."""

    def test_omitted_field_keeps_previous_note(self):
        response = StructuredResponse()
        self.assertEqual(working_state_transition(response), (False, None))

    def test_explicit_null_clears_note(self):
        response = StructuredResponse.model_validate({"working_state": None})
        commit, value = working_state_transition(response)
        self.assertTrue(commit)
        self.assertIsNone(value)

    def test_provided_object_is_committed(self):
        response = StructuredResponse.model_validate(
            {"working_state": {"focus": "Next scene"}}
        )
        commit, value = working_state_transition(response)
        self.assertTrue(commit)
        self.assertEqual(value.focus, "Next scene")

    def test_plain_object_without_field_tracking_uses_value_presence(self):
        from types import SimpleNamespace
        self.assertEqual(
            working_state_transition(SimpleNamespace(working_state=None)),
            (False, None),
        )
        self.assertTrue(working_state_transition(
            SimpleNamespace(working_state={"focus": "x"})
        )[0])


if __name__ == "__main__":
    unittest.main()
