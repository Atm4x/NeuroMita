from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


PROJECT_SRC = Path(__file__).resolve().parents[2]
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from utils.structured_response_parser import (
    parse_structured_response,
    parse_structured_response_with_meta,
)
from schemas.game_master_response import GameMasterResponse


class StructuredResponseParserCoerceTests(unittest.TestCase):
    def test_scalar_segment_fields_are_coerced_to_lists(self) -> None:
        payload = {
            "segments": [
                {
                    "text": "Привет",
                    "emotions": "smileobvi",
                    "animations": "Жест пальцами",
                    "music": "Music 3 Tamagochi",
                    "movement_modes": "Стоять на месте",
                    "hint": "Не зли Миту",
                }
            ],
            "attitude_change": 1.0,
            "boredom_change": 0.5,
            "stress_change": -0.2,
        }

        response = parse_structured_response(json.dumps(payload, ensure_ascii=False))
        segment = response.segments[0]

        self.assertEqual(segment.emotions, ["smileobvi"])
        self.assertEqual(segment.animations, ["Жест пальцами"])
        self.assertEqual(segment.music, ["Music 3 Tamagochi"])
        self.assertEqual(segment.movement_modes, ["Стоять на месте"])
        self.assertEqual(segment.hint, "Не зли Миту")

    def test_direct_schema_valid_response_is_trusted(self) -> None:
        outcome = parse_structured_response_with_meta(
            json.dumps({"segments": [{"text": "Hello"}]})
        )
        self.assertEqual(outcome.parse_level, "direct")
        self.assertFalse(outcome.schema_coerced)
        self.assertTrue(outcome.control_plane_trusted)
        self.assertFalse(outcome.repaired)

    def test_truncated_invalid_numeric_tail_is_discarded_and_reported(self) -> None:
        raw = '{"segments":[{"text":"Привет"}],"boredom_change":-'

        with self.assertLogs("main_logger", level="WARNING") as captured:
            outcome = parse_structured_response_with_meta(raw)

        self.assertEqual(outcome.response.segments[0].text, "Привет")
        self.assertTrue(outcome.repaired)
        self.assertTrue(any("repaired" in line.lower() for line in captured.output))

    def test_missing_outer_brace_preserves_completed_segment_actions(self) -> None:
        raw = (
            '{"segments":[{"text":"Иду","commands":["light:on"],'
            '"intents":[{"type":"light.enable","payload":{"id":"desk"}}]}]'
        )

        outcome = parse_structured_response_with_meta(raw)

        self.assertEqual(outcome.response.segments[0].text, "Иду")
        self.assertEqual(outcome.response.segments[0].commands, ["light:on"])
        self.assertEqual(outcome.response.segments[0].intents[0].type, "light.enable")
        self.assertTrue(outcome.repaired)

    def test_unterminated_text_is_closed_without_becoming_null(self) -> None:
        raw = '{"segments":[{"text":"Привет'

        outcome = parse_structured_response_with_meta(raw)

        self.assertEqual(outcome.response.segments[0].text, "Привет")
        self.assertTrue(outcome.repaired)

    def test_truncated_outer_object_keeps_fields_after_nested_object(self) -> None:
        raw = '{"segments":[{"text":"Привет"}],"attitude_change":0'

        outcome = parse_structured_response_with_meta(raw)

        self.assertEqual(outcome.response.segments[0].text, "Привет")
        self.assertEqual(outcome.response.attitude_change, 0)
        self.assertEqual(outcome.extraction_kind, "truncated_json")
        self.assertTrue(outcome.repaired)

    def test_truncated_first_numeric_field_becomes_empty_object(self) -> None:
        raw = '{"boredom_change":-'

        outcome = parse_structured_response_with_meta(raw, model_cls=GameMasterResponse)

        self.assertEqual(outcome.response.actions, [])
        self.assertTrue(outcome.repaired)

    def test_truncated_unicode_escape_discards_only_incomplete_field(self) -> None:
        raw = r'{"segments":[{"text":"Привет \u041'

        outcome = parse_structured_response_with_meta(raw)

        self.assertEqual(outcome.response.segments[0].text, "Привет ")
        self.assertTrue(outcome.repaired)

    def test_markdown_json_fence_is_trusted(self) -> None:
        outcome = parse_structured_response_with_meta(
            "```json\n{\"segments\": [{\"text\": \"Hello\"}]}\n```"
        )
        self.assertEqual(outcome.extraction_kind, "markdown_json_fence")
        self.assertTrue(outcome.control_plane_trusted)

    def test_embedded_json_is_untrusted_for_control_plane(self) -> None:
        outcome = parse_structured_response_with_meta(
            "Model preface\n{\"segments\": [{\"text\": \"Hello\"}]}\nModel suffix"
        )
        self.assertEqual(outcome.extraction_kind, "embedded_json")
        self.assertFalse(outcome.control_plane_trusted)
        self.assertTrue(outcome.repaired)

    def test_schema_coercion_is_untrusted_for_control_plane(self) -> None:
        outcome = parse_structured_response_with_meta(
            json.dumps({"segments": [{"text": 123, "commands": "wave"}]})
        )
        self.assertTrue(outcome.schema_coerced)
        self.assertFalse(outcome.control_plane_trusted)

    def test_scalar_text_and_allow_sleep_are_coerced(self) -> None:
        payload = {
            "segments": [
                {
                    "text": 123,
                    "commands": "Continue",
                    "allow_sleep": "true",
                    "target": 77,
                }
            ],
            "attitude_change": "1.25",
            "boredom_change": "0.5",
            "stress_change": "-0.75",
        }

        response = parse_structured_response(json.dumps(payload, ensure_ascii=False))
        segment = response.segments[0]

        self.assertEqual(segment.text, "123")
        self.assertEqual(segment.commands, ["Continue"])
        self.assertTrue(segment.allow_sleep)
        self.assertEqual(segment.target, "77")
        self.assertEqual(response.attitude_change, 1.25)
        self.assertEqual(response.boredom_change, 0.5)
        self.assertEqual(response.stress_change, -0.75)

    def test_scalar_working_state_fields_are_coerced_to_lists(self) -> None:
        payload = {
            "segments": [{"text": "Enough with the acrobatics!"}],
            "working_state": {
                "focus": "Игра всё ещё не запущена.",
                "situation": "Игрок продолжает делать сальто.",
                "assumptions": "Игрок ждёт запуска игры.",
                "open_loops": "Запустить игру.",
                "next_steps": "Вернуться к запуску игры.",
            },
        }

        outcome = parse_structured_response_with_meta(
            json.dumps(payload, ensure_ascii=False)
        )

        self.assertTrue(outcome.schema_coerced)
        self.assertEqual(
            outcome.response.working_state.focus,
            "Игра всё ещё не запущена.",
        )
        self.assertEqual(
            outcome.response.working_state.situation,
            ["Игрок продолжает делать сальто."],
        )
        self.assertEqual(
            outcome.response.working_state.next_steps,
            ["Вернуться к запуску игры."],
        )

    def test_string_working_state_becomes_focus(self) -> None:
        payload = {
            "segments": [{"text": "Enough with the acrobatics!"}],
            "working_state": "Игра всё ещё не запущена.",
        }

        outcome = parse_structured_response_with_meta(
            json.dumps(payload, ensure_ascii=False)
        )

        self.assertTrue(outcome.schema_coerced)
        self.assertEqual(
            outcome.response.working_state.focus,
            "Игра всё ещё не запущена.",
        )
        self.assertEqual(outcome.response.working_state.situation, [])


if __name__ == "__main__":
    unittest.main()
