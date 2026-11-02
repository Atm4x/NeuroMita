from __future__ import annotations

import sys
import unittest
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QLabel

PROJECT_SRC = Path(__file__).resolve().parents[2]
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from services.contracts import (
    DialogueParticipantView,
    DialogueRuntimeSnapshot,
    DialogueRuntimeSource,
)
from ui.chat.dialogue_presentation import format_conversation_title, format_runtime_source
from ui.chat.message_renderer import _group_segments_by_target
from ui.chat.structured_panel import StructuredOutputPanel


class DialoguePresentationTests(unittest.TestCase):
    def test_segment_targets_form_separate_visible_bubble_groups(self) -> None:
        groups = _group_segments_by_target([
            {"text": "For Kind, part one.", "target": "Kind"},
            {"text": "For Kind, part two.", "target": "Kind"},
            {"text": "For Cappie.", "target": "Cappie"},
            {"text": "For Player."},
        ])

        self.assertEqual(groups, [
            ("Kind", ["For Kind, part one.", "For Kind, part two."]),
            ("Cappie", ["For Cappie."]),
            ("Player", ["For Player."]),
        ])

    def test_structured_panel_shows_target_on_each_segment(self) -> None:
        app = QApplication.instance() or QApplication([])
        panel = StructuredOutputPanel({
            "segments": [
                {"text": "For Kind.", "target": "Kind"},
                {"text": "For Cappie.", "target": "Cappie"},
            ],
        })
        labels = [label.text() for label in panel.findChildren(QLabel)]
        self.assertIn("target: Kind", labels)
        self.assertIn("target: Cappie", labels)
        panel.close()
        app.processEvents()

    def test_structured_panel_shows_intents_in_brief_mode(self) -> None:
        app = QApplication.instance() or QApplication([])
        panel = StructuredOutputPanel({
            "segments": [{
                "text": "Move.",
                "intents": [{
                    "type": "actor.set_movement_mode",
                    "payload": {},
                }],
            }],
        })
        labels = [label.text() for label in panel.findChildren(QLabel)]
        self.assertIn("🧠 intent: actor.set_movement_mode {}", labels)
        panel.close()
        app.processEvents()

    def test_title_keeps_single_character_fallback(self) -> None:
        self.assertEqual(
            format_conversation_title(None, "Crazy"),
            "Conversation with Crazy",
        )

    def test_title_lists_multi_mita_participants_and_hides_gm(self) -> None:
        snapshot = DialogueRuntimeSnapshot(
            source=DialogueRuntimeSource.UNITY,
            conversation_id="unity:one",
            participants=(
                DialogueParticipantView("a", "A", "Alpha"),
                DialogueParticipantView("b", "B", "Beta"),
                DialogueParticipantView("gm", "GameMaster", "Game Master"),
            ),
        )
        self.assertEqual(format_conversation_title(snapshot), "Conversation: Alpha, Beta")
        self.assertEqual(format_runtime_source(snapshot), "Game")

    def test_title_collapses_large_sessions(self) -> None:
        participants = tuple(
            DialogueParticipantView(str(i), f"Mita{i}", f"Mita {i}")
            for i in range(4)
        )
        snapshot = DialogueRuntimeSnapshot(
            source=DialogueRuntimeSource.UNITY,
            conversation_id="unity:one",
            participants=participants,
        )
        self.assertEqual(format_conversation_title(snapshot), "Conversation with Mitas (4)")
        self.assertEqual(format_runtime_source(snapshot), "Game")

    def test_structured_panel_json_view_keeps_zero_and_false(self) -> None:
        visible = StructuredOutputPanel._visible_json_payload({
            "segments": [{"text": "Hi", "emotions": []}],
            "attitude_change": 0,
            "boredom_change": 0.0,
            "stress_change": False,
            "memory_add": [],
            "memory_merge": [],
            "reminder_add": None,
            "custom_fields": {},
            "entities": [],
            "relations": [],
            "tool_call": None,
            "secret_exposed": None,
            "timer_add": [],
            "quiet_text": "",
            "response_protocol_version": 3,
        })

        self.assertEqual(visible["attitude_change"], 0)
        self.assertEqual(visible["boredom_change"], 0.0)
        self.assertIs(visible["stress_change"], False)
        self.assertEqual(visible["response_protocol_version"], 3)
        self.assertEqual(visible["segments"][0]["emotions"], [])
        for hidden in (
            "memory_add", "memory_merge", "reminder_add", "custom_fields",
            "entities", "relations", "tool_call", "secret_exposed",
            "timer_add", "quiet_text",
        ):
            self.assertNotIn(hidden, visible)

    def test_structured_panel_json_mode_shows_raw_model_json(self) -> None:
        app = QApplication.instance() or QApplication([])
        raw = '{"segments": [{"text": "Hi"}], "memory_add": [], "tool_call": null}'
        panel = StructuredOutputPanel(
            {"_raw_json": raw, "segments": [{"text": "Hi"}], "memory_add": [], "tool_call": None},
            mode="json",
        )
        labels = [label.text() for label in panel.findChildren(QLabel)]
        json_label = next(text for text in labels if '"segments"' in text)
        self.assertIn('"memory_add": []', json_label)
        self.assertIn('"tool_call": null', json_label)
        self.assertTrue(any(
            text == "Исходный JSON модели" or text == "Raw model JSON"
            for text in labels
        ))
        panel.close()
        app.processEvents()

    def test_structured_panel_json_mode_hides_normalized_empty_defaults(self) -> None:
        app = QApplication.instance() or QApplication([])
        panel = StructuredOutputPanel(
            {
                "segments": [{"text": "Hi", "emotions": []}],
                "attitude_change": 0,
                "stress_change": False,
                "memory_add": [],
                "custom_fields": None,
                "entities": [],
                "tool_call": None,
                "response_protocol_version": 3,
            },
            mode="json",
        )
        labels = [label.text() for label in panel.findChildren(QLabel)]
        json_label = next(text for text in labels if '"segments"' in text)
        self.assertIn('"attitude_change": 0', json_label)
        self.assertIn('"stress_change": false', json_label)
        self.assertIn('"emotions": []', json_label)
        for hidden in ("memory_add", "custom_fields", "entities", "tool_call"):
            self.assertNotIn(hidden, json_label)
        self.assertTrue(any(
            text.startswith("Нормализованный ответ")
            or text.startswith("Normalized response")
            for text in labels
        ))
        panel.close()
        app.processEvents()


if __name__ == "__main__":
    unittest.main()
