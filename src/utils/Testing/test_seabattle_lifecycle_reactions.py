"""Regression checks for Sea Battle lifecycle reactions."""
from __future__ import annotations

import sys
import queue
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_SRC = Path(__file__).resolve().parents[2]
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from modules.SeaBattle.seabattle_instance import SeaBattleGame


class _EventBus:
    def __init__(self):
        self.events = []

    def emit(self, name, payload):
        self.events.append((name, payload))


class _Character:
    char_id = "Mita"

    def __init__(self):
        self.event_bus = _EventBus()
        self.variables = {"playingGame": True}

    def get_variable(self, key, default=None):
        return self.variables.get(key, default)

    def set_variable(self, key, value):
        self.variables[key] = value


class _Settings:
    def get(self, key, default=None):
        return {"REACT_ENABLED": True, "REACT_L2_ENABLED": True}.get(key, default)


class _DslInterpreter:
    def __init__(self):
        self.paths = []

    def process_file(self, path):
        self.paths.append(path)
        return "game state", []


class SeaBattleLifecycleReactionTests(unittest.TestCase):
    def test_finishing_placement_emits_reaction(self):
        character = _Character()
        game = SeaBattleGame(character)

        with patch("modules.SeaBattle.seabattle_instance.use", return_value=_Settings()):
            game._dispatch_placement_completed_reaction()

        self.assertEqual(len(character.event_bus.events), 1)
        _event, payload = character.event_bus.events[0]
        self.assertEqual(payload["event_type"], "react")
        self.assertIn("finished placing all ships", payload["system_input"])
        self.assertIn("PlaceShipsRandomly", payload["system_input"])

    def test_player_shot_requests_an_immediate_sea_battle_move(self):
        character = _Character()
        game = SeaBattleGame(character)

        with patch("modules.SeaBattle.seabattle_instance.use", return_value=_Settings()):
            game._dispatch_player_target_reaction({"coord": "A1", "result": "miss"})

        self.assertEqual(len(character.event_bus.events), 1)
        _event, payload = character.event_bus.events[0]
        self.assertIn("MakeMove,<coordinate>", payload["system_input"])
        self.assertNotIn("Do not take a Sea Battle turn", payload["system_input"])

    def test_game_over_emits_reaction_without_another_shot(self):
        character = _Character()
        game = SeaBattleGame(character)

        with patch("modules.SeaBattle.seabattle_instance.use", return_value=_Settings()):
            game._dispatch_game_over_reaction({"winner": 0, "player_id": 0})

        self.assertEqual(len(character.event_bus.events), 1)
        _event, payload = character.event_bus.events[0]
        self.assertIn("The player won", payload["system_input"])
        self.assertIn("do not take another shot", payload["system_input"])

    def test_runtime_state_uses_shared_game_prompt(self):
        character = _Character()
        character.dsl_interpreter = _DslInterpreter()
        game = SeaBattleGame(character)
        game.state_queue = queue.Queue()
        game.state_queue.put({
            "phase": "battle",
            "is_player_turn": False,
            "mita_id": "mita",
            "mita_my_board_str": "my board",
            "mita_opponent_view_str": "opponent board",
            "mita_ships_to_place": [],
            "hunt_info": {},
            "shot_history_str": "",
        })

        self.assertEqual(game.get_state_prompt(), "game state")
        self.assertEqual(character.dsl_interpreter.paths, ["_CommonPrompts/seabattle.system"])

    def test_closing_window_emits_reaction(self):
        character = _Character()
        game = SeaBattleGame(character)

        with patch("modules.SeaBattle.seabattle_instance.use", return_value=_Settings()):
            game._dispatch_player_close_reaction()

        self.assertEqual(len(character.event_bus.events), 1)
        _event, payload = character.event_bus.events[0]
        self.assertIn("closed the Sea Battle game window", payload["system_input"])


if __name__ == "__main__":
    unittest.main()
