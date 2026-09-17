"""Regression checks for chess player-move reactions and the checked GUI option."""
from __future__ import annotations

import os
import queue
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_SRC = Path(__file__).resolve().parents[2]
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from PyQt6.QtWidgets import QApplication

from modules.Chess.chess_board import ChessGuiTkinter
from modules.Chess.game_instance import ChessGame


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


class _Controller:
    current_maia_elo = 1500
    is_auto = False

    def get_player_color_is_white_for_gui(self):
        return True


class _DslInterpreter:
    def __init__(self):
        self.paths = []

    def process_file(self, path):
        self.paths.append(path)
        return "game state", []


class ChessMoveReactionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_player_move_emits_l2_reaction(self):
        character = _Character()
        game = ChessGame(character, "chess")

        with patch("modules.Chess.game_instance.use", return_value=_Settings()):
            game._dispatch_player_move_reaction({"uci": "e2e4", "san": "e4"})

        self.assertEqual(len(character.event_bus.events), 1)
        _event, payload = character.event_bus.events[0]
        self.assertEqual(payload["event_type"], "react")
        self.assertEqual(payload["policy"]["react_level"], 2)
        self.assertIn("e4", payload["system_input"])
        self.assertIn("RequestBestChessMove", payload["system_input"])
        self.assertNotIn("Do not make a chess move", payload["system_input"])

    def test_player_closing_chess_emits_l2_reaction(self):
        character = _Character()
        game = ChessGame(character, "chess")

        with patch("modules.Chess.game_instance.use", return_value=_Settings()):
            game._dispatch_player_close_reaction()

        self.assertEqual(len(character.event_bus.events), 1)
        _event, payload = character.event_bus.events[0]
        self.assertEqual(payload["event_type"], "react")
        self.assertIn("closed the chess game window", payload["system_input"])

    def test_game_over_emits_reaction_without_a_chess_move(self):
        character = _Character()
        game = ChessGame(character, "chess")

        with patch("modules.Chess.game_instance.use", return_value=_Settings()):
            game._dispatch_game_over_reaction({"outcome": "Checkmate."})

        self.assertEqual(len(character.event_bus.events), 1)
        _event, payload = character.event_bus.events[0]
        self.assertIn("game has ended", payload["system_input"])
        self.assertIn("do not make a chess move", payload["system_input"])

    def test_chess_reaction_checkbox_is_checked_by_default(self):
        window = ChessGuiTkinter(_Controller())
        try:
            self.assertIsNotNone(window.mita_reaction_checkbox)
            self.assertTrue(window.mita_reaction_checkbox.isChecked())
        finally:
            window.hide()
            window.deleteLater()

    def test_runtime_state_uses_shared_game_prompt(self):
        character = _Character()
        character.dsl_interpreter = _DslInterpreter()
        game = ChessGame(character, "chess")
        game.state_queue = queue.Queue()
        game.state_queue.put({
            "player_is_white_in_gui": True,
            "turn": "black",
            "current_elo": 1500,
            "last_move_san": "e4",
            "fen": "test-fen",
            "board_ascii": None,
            "is_game_over": False,
            "outcome_message": "Playing",
            "legal_moves_uci": ["e7e5"],
            "legal_moves_short": ["e7e5"],
            "is_auto": False,
            "is_cheat": False,
        })

        self.assertEqual(game.get_state_prompt(), "game state")
        self.assertEqual(character.dsl_interpreter.paths, ["_CommonPrompts/chess.system"])


if __name__ == "__main__":
    unittest.main()
