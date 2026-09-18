"""Regression tests for mini-games started from the desktop settings panel."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_SRC = Path(__file__).resolve().parents[2]
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from managers.game_manager import GameManager


class _Character:
    char_id = "Mita"

    def __init__(self) -> None:
        self.app_vars = {}


class _Settings:
    def __init__(self, **values) -> None:
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)


class ManualGameLaunchTests(unittest.TestCase):
    def test_launch_uses_chat_api_when_game_requests_are_accepted(self) -> None:
        character = _Character()
        manager = GameManager(character)
        settings = _Settings(IGNORE_GAME_REQUESTS=False)

        with patch.object(manager, "start_game", return_value=True) as start_game:
            with patch("managers.game_manager.use", return_value=settings):
                with patch("managers.game_manager.ChatAPI.react", return_value=True) as react:
                    self.assertTrue(manager.start_game_from_player("chess"))

        start_game.assert_called_once_with("chess")
        react.assert_called_once()
        kwargs = react.call_args.kwargs
        self.assertEqual(kwargs["character_id"], "Mita")
        self.assertTrue(kwargs["visible"])
        self.assertIn("chess", kwargs["instruction"])

    def test_launch_does_not_react_when_game_requests_are_muted(self) -> None:
        character = _Character()
        manager = GameManager(character)
        settings = _Settings(IGNORE_GAME_REQUESTS=True)

        with patch.object(manager, "start_game", return_value=True):
            with patch("managers.game_manager.use", return_value=settings):
                with patch("managers.game_manager.ChatAPI.react") as react:
                    self.assertTrue(manager.start_game_from_player("seabattle"))

        react.assert_not_called()

    def test_start_game_injects_manager_as_game_host(self) -> None:
        character = _Character()
        manager = GameManager(character)

        class _Game:
            def __init__(self, received_character, game_id, host=None):
                self.character = received_character
                self.game_id = game_id
                self.host = host
                self.started_with = None

            def start(self, params):
                self.started_with = params

        manager.available_games = {"fake": _Game}
        with patch.object(manager, "_is_game_launch_allowed", return_value=True):
            self.assertTrue(manager.start_game("fake"))

        self.assertIs(manager.active_game.host, manager)
        self.assertIs(manager.active_game.character, character)
        self.assertEqual(manager.active_game.started_with, {})

    def test_active_game_reaction_is_routed_through_chat_api(self) -> None:
        character = _Character()
        manager = GameManager(character)
        game = object()
        manager.active_game = game

        with patch("managers.game_manager.ChatAPI.react", return_value=True) as react:
            self.assertTrue(manager.request_character_reaction(game, "game event"))

        react.assert_called_once_with(
            character_id="Mita",
            instruction="game event",
            visible=True,
            sender="Player",
        )

    def test_stale_game_cannot_request_character_reaction(self) -> None:
        character = _Character()
        manager = GameManager(character)
        manager.active_game = object()
        stale_game = object()

        with patch("managers.game_manager.ChatAPI.react") as react:
            self.assertFalse(manager.request_character_reaction(stale_game, "stale event"))

        react.assert_not_called()


if __name__ == "__main__":
    unittest.main()
