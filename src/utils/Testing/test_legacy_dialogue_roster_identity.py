from __future__ import annotations

import unittest
from types import SimpleNamespace

from controllers.history_controller import HistoryController
from services.dialogue_roster_context import (
    neutralize_dialogue_roster_content,
    neutralize_dialogue_roster_message,
)


LEGACY_DIALOGUE = (
    "[DIALOGUE] You are in dialogue with several (4) speakers:\n"
    " Player\n"
    "Kind (Mita), its game object MitaPerson Mita)\n"
    "Cappie (Mita), its game object MitaPerson Mita)(you)\n"
    "Sleepy (Mita), its game object MitaPerson Mita)\n"
    "[DIALOGUE_UPDATE] Cappie (Mita) said: 'Hey, (you) heard me!'\n"
)

OTHER_TURN = (
    "[DIALOGUE] You are in dialogue with several (4) speakers:\n"
    " Player\n"
    "Kind (Mita), its game object MitaPerson Mita)(you)\n"
    "Cappie (Mita), its game object MitaPerson Mita)\n"
    "Sleepy (Mita), its game object MitaPerson Mita)\n"
    "[DIALOGUE_UPDATE] Sleepy (Mita) said: 'Another reply.'\n"
)


class LegacyRosterIdentityTests(unittest.TestCase):
    def test_replay_of_other_mitas_rosters_has_no_false_you(self):
        # The real log mixed "(you)" for Cappie, Kind and Sleepy in Kind's history.
        data = LEGACY_DIALOGUE + "\n" + OTHER_TURN
        result = neutralize_dialogue_roster_content(data)
        self.assertIn("Kind (Mita)\n", result)
        self.assertIn("Cappie (Mita)\n", result)
        self.assertNotIn("its game object", result)
        self.assertNotIn("(Mita)(you)", result)
        self.assertIn("said: 'Hey, (you) heard me!'", result)

    def test_inline_runtime_event_roster_is_neutral_but_speech_is_intact(self):
        compact = (
            "- [DIALOGUE] You are in dialogue with several (4) speakers: "
            "Player Sleepy (Mita), its game object MitaPerson Mita) "
            "Kind (Mita), its game object MitaPerson Mita)(you) "
            "Cappie (Mita), its game object MitaPerson Mita) "
            "[DIALOGUE_UPDATE] Cappie (Mita) said: 'I saw (you) there.'\n"
        )
        result = neutralize_dialogue_roster_content(compact)
        self.assertIn("Player Sleepy (Mita) Kind (Mita) Cappie (Mita)", result)
        self.assertNotIn("its game object", result)
        self.assertNotIn("(Mita)(you)", result)
        self.assertIn("said: 'I saw (you) there.'", result)

    def test_escaped_json_unity_event_roster_is_neutral_and_valid_json(self):
        # Older histories store a JSON description with literal \n separators.
        import json

        source = (
            '[Current UnityEvent] {"description":"[DIALOGUE] You are in '
            'dialogue with several (3) speakers: \\n Player\\n'
            'Kind (Mita), its game object MitaPerson Mita)(you)\\n'
            'Cappie (Mita), its game object MitaPerson Mita)\\n'
            '[SPEAKER] Cappie (Mita) said: hello"}'
        )
        cleaned = neutralize_dialogue_roster_content(source)
        payload = json.loads(cleaned.removeprefix("[Current UnityEvent] "))
        self.assertIn("Kind (Mita)\nCappie (Mita)", payload["description"])
        self.assertNotIn("(you)", payload["description"])
        self.assertIn("[SPEAKER] Cappie (Mita) said: hello", payload["description"])

    def test_outside_roster_and_player_message_are_untouched(self):
        text = "The Player wrote: '(you) are listening.'\n[Something Else] Keep (you)."
        self.assertEqual(neutralize_dialogue_roster_content(text), text)

    def test_multimodal_message_is_copied_not_persistently_changed(self):
        image = {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}}
        original = {"role": "user", "content": [{"type": "text", "text": LEGACY_DIALOGUE}, image]}
        result = neutralize_dialogue_roster_message(original)
        self.assertIsNot(result, original)
        self.assertEqual(original["content"][0]["text"], LEGACY_DIALOGUE)
        self.assertEqual(result["content"][0]["text"].count("(Mita)(you)"), 0)
        self.assertIs(result["content"][1], image)

    def test_history_sanitization_cleans_saved_snapshots_for_new_owner(self):
        service = HistoryController.__new__(HistoryController)
        service._action_memory_enabled = lambda: False
        service._time_gap_marker_threshold_seconds = lambda: 0
        saved = [
            {"role": "user", "speaker": "Player", "content": LEGACY_DIALOGUE},
            {"role": "user", "speaker": "Player", "content": OTHER_TURN},
        ]
        result = service._sanitize_history_for_llm(SimpleNamespace(char_id="Kind"), saved)
        self.assertEqual(len(result), 2)
        self.assertNotIn("(Mita)(you)", repr(result))
        self.assertIn("(Mita)(you)", repr(saved))
        self.assertIn("[DIALOGUE_UPDATE]", result[0]["content"])


if __name__ == "__main__":
    unittest.main()
