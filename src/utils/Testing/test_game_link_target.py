"""Tests for Unity target tracking used by desktop mini-game launch."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_SRC = Path(__file__).resolve().parents[2]
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from services.game_link_service import DisconnectedGameLinkService, ServerGameLinkService
from ui.settings.game_settings import _select_manual_game_character


class _Character:
    def __init__(self, char_id, display_name=None):
        self.char_id = char_id
        self.display_name = display_name or char_id


class GameLinkTargetTests(unittest.TestCase):
    def test_server_game_link_tracks_and_clears_unity_target(self):
        service = ServerGameLinkService()

        service.set_connected(True)
        service.set_unity_target_character_id("Kind")
        self.assertEqual(service.unity_target_character_id(), "Kind")

        service.set_connected(False)
        self.assertEqual(service.unity_target_character_id(), "")

    def test_disconnected_game_link_has_no_unity_target(self):
        service = DisconnectedGameLinkService()
        self.assertEqual(service.unity_target_character_id(), "")

    def test_unity_character_is_the_default_launch_target(self):
        launcher = _Character("Crazy")
        unity = _Character("Kind")
        received = {}

        target = _select_manual_game_character(
            launcher,
            unity,
            lambda choices, preferred: received.update(choices=choices, preferred=preferred) or preferred,
        )

        self.assertIs(target, unity)
        self.assertEqual(received["preferred"], "Kind (Kind)")
        self.assertEqual(received["choices"], ["Kind (Kind)", "Crazy (Crazy)"])

    def test_launcher_character_can_be_selected_without_switching_registry(self):
        launcher = _Character("Crazy")
        unity = _Character("Kind")

        target = _select_manual_game_character(
            launcher,
            unity,
            lambda choices, _preferred: choices[1],
        )

        self.assertIs(target, launcher)

    def test_cancelled_target_selection_does_not_start_a_game(self):
        launcher = _Character("Crazy")
        unity = _Character("Kind")

        target = _select_manual_game_character(launcher, unity, lambda *_: None)

        self.assertIsNone(target)


if __name__ == "__main__":
    unittest.main()
