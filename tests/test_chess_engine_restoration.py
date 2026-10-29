from __future__ import annotations

from pathlib import Path
import queue
import sys
from threading import Event, Thread
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import chess
import chess.engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from modules.Chess.engine_handler import ChessGameController
from modules.session_snapshot import validate_game_state


class ChessEngineRestorationTests(unittest.TestCase):
    def setUp(self):
        self.notifications = queue.Queue()
        self.states = queue.Queue()
        self.threads = []
        self.statuses = []
        self.controller = ChessGameController(1500, False, self.states, self.statuses.append,
            lambda: None, lambda _result: None, semantic_event_queue=self.notifications)

        def start(_owner, _name, compute):
            worker = Thread(target=compute, daemon=True)
            self.threads.append(worker)
            worker.start()
            return worker

        supervisor = SimpleNamespace(start_thread=start)
        patched = patch("modules.Chess.engine_handler.task_supervisor", return_value=supervisor)
        patched.start()
        self.addCleanup(patched.stop)

    def _start_analysis(self, *, error=None):
        entered, release = Event(), Event()
        calls = []

        def play(board, _limit):
            calls.append(board.copy(stack=True))
            entered.set()
            if not release.wait(3):
                raise TimeoutError("Test engine was not released")
            if error is not None:
                raise error
            return SimpleNamespace(move=chess.Move.from_uci("e2e4"))

        self.controller.engine = SimpleNamespace(play=play)
        self.controller.request_engine_move_auto()
        self.assertTrue(entered.wait(1))
        self.addCleanup(release.set)
        return release, calls

    def _finish_analysis(self, release):
        release.set()
        for worker in self.threads:
            worker.join(2)
            self.assertFalse(worker.is_alive())

    def test_worker_never_applies_a_move_and_paused_owner_defers_its_result(self):
        release, _calls = self._start_analysis()
        self.controller.set_session_paused(True)
        self._finish_analysis(release)
        self.assertEqual(self.controller.board_logic.snapshot()["moves"], [])
        self.assertTrue(self.notifications.empty())
        self.controller.process_engine_results()
        self.assertTrue(self.controller.engine_move_pending)
        self.assertEqual(self.controller.board_logic.snapshot()["moves"], [])
        self.controller.set_session_paused(False)
        self.controller.process_engine_results()
        self.assertEqual(self.controller.board_logic.snapshot()["moves"], ["e2e4"])
        self.assertFalse(self.controller.engine_move_pending)
        self.assertEqual(self.notifications.get_nowait()["uci"], "e2e4")
        self.assertTrue(self.notifications.empty())

    def test_restore_invalidates_old_analysis_even_when_the_position_matches(self):
        release, _calls = self._start_analysis()
        self.controller.set_session_paused(True)
        self.controller.restore_engine_work(False)
        self._finish_analysis(release)
        self.controller.set_session_paused(False)
        self.controller.process_engine_results()
        self.assertEqual(self.controller.board_logic.snapshot()["moves"], [])
        self.assertFalse(self.controller.engine_move_pending)
        self.assertTrue(self.notifications.empty())

    def test_restored_pending_request_is_recomputed_and_publishes_exactly_one_move(self):
        release, calls = self._start_analysis()
        self.controller.set_session_paused(True)
        self.controller.restore_engine_work(True)
        self._finish_analysis(release)
        self.controller.process_engine_results()
        self.assertEqual(len(calls), 1)
        self.controller.set_session_paused(False)
        self.controller.process_engine_results()
        self._finish_analysis(release)
        self.controller.process_engine_results()
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.controller.board_logic.snapshot()["moves"], ["e2e4"])
        self.assertEqual(self.notifications.qsize(), 1)

    def test_same_generation_position_change_rejects_an_obsolete_move(self):
        release, _calls = self._start_analysis()
        self.controller.board_logic.make_move("d2d4")
        self.notifications.get_nowait()
        self._finish_analysis(release)
        self.controller.process_engine_results()
        self.assertEqual(self.controller.board_logic.snapshot()["moves"], ["d2d4"])
        self.assertTrue(self.notifications.empty())

    def test_failure_from_an_old_engine_cannot_clear_its_replacement(self):
        release, _calls = self._start_analysis(error=chess.engine.EngineTerminatedError("old engine exited"))
        replacement = object()
        self.controller.set_session_paused(True)
        self.controller.restore_engine_work(False)
        self.controller.engine = replacement
        self._finish_analysis(release)
        self.controller.set_session_paused(False)
        self.controller.process_engine_results()
        self.assertIs(self.controller.engine, replacement)
        self.assertTrue(self.states.empty())

    def test_chess_snapshot_preserves_pending_work_as_explicit_intent(self):
        snapshot = {"board": self.controller.board_logic.snapshot(), "elo": 1500, "player_is_white": False,
            "is_auto": False, "is_cheat": False, "react_enabled": True, "engine_pending": True}
        validate_game_state("chess", snapshot)
        snapshot["engine_pending"] = "true"
        with self.assertRaises(ValueError):
            validate_game_state("chess", snapshot)


if __name__ == "__main__":
    unittest.main()
