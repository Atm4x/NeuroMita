from __future__ import annotations

import os
import sqlite3
from pathlib import Path
import queue
import sys
import tempfile
from threading import Event, Thread
from types import SimpleNamespace
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.services import services
from core.state_barrier import StateBarrier
from domain.timeline import JsonDocument
from infrastructure.timeline.sqlite import SQLiteTimelineRepository
from infrastructure.timeline.restoration import SQLiteRestorationJournal
from managers.game_manager import GameManager
from managers.session_state_participants import GamesSnapshot
from modules.Chess.board_logic import PureBoardLogic
from modules.SeaBattle.seabattle_logic import SeaBattleEngine
from modules.SeaBattle.seabattle_instance import SeaBattleGame
from modules.session_snapshot import GameSnapshotEndpoint, GameStateQueue, snapshot_request
from services.timeline_runtime import SessionTimelineRuntime
from services.session_restoration import SessionRestoration


class GameSnapshotTests(unittest.TestCase):
    def test_real_seabattle_process_restores_and_can_be_recreated_from_checkpoint(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "world.db"
            repository = SQLiteTimelineRepository(path)
            runtime = SessionTimelineRuntime(repository, repository)
            previous = {key: services().get_optional(key) for key in (StateBarrier, SessionTimelineRuntime)}
            services().register(StateBarrier, runtime.state, replace=True)
            services().register(SessionTimelineRuntime, runtime, replace=True)
            variables = {"playingGame": False}
            character = SimpleNamespace(char_id="A", get_variable=lambda key, default=None: variables.get(key, default),
                                        set_variable=lambda key, value: variables.update({key: value}))
            manager = GameManager(character)
            character.game_manager = manager
            character_manager = SimpleNamespace(get_all_characters=lambda: ["A"], get_loaded_characters=lambda: [character],
                get_loaded_character=lambda _identity: character, get_character=lambda _identity: character)
            SessionRestoration(runtime, (GamesSnapshot(character_manager, runtime),),
                               SQLiteRestorationJournal(lambda: sqlite3.connect(path)))
            game = SeaBattleGame(character, "seabattle", host=manager)
            game.timeline_selection = runtime.selection
            manager.active_game = game
            try:
                game.start({})
                self.assertIsNotNone(game.gui_process)
                self.assertTrue(game.gui_process.is_alive())
                checkpoint = runtime.checkpoint()
                saved = checkpoint.payload.to_dict()["snapshot"]["participants"]["games"]["state"]
                game.command_queue.put({"action": "mita_place_ship", "spec": "A1,1,H"})
                changed = runtime.checkpoint()
                changed_state = changed.payload.to_dict()["snapshot"]["participants"]["games"]["state"]
                self.assertNotEqual(saved["games"]["A"]["state"], changed_state["games"]["A"]["state"])
                source_branch = runtime.selection.branch_id
                game._reaction_stop_event.set()
                game._reaction_listener.join(2)
                game.reaction_queue.put({"event": "player_target_selected", "coord": "A1", "result": "miss",
                                         "mover": "Player", "semantic_id": "accepted-before-restore", "react": True})
                runtime.restore(checkpoint.event_id)
                self.assertTrue(any(event.payload.to_dict().get("name") == "SeaBattleShot"
                                    for event in repository.read(source_branch)))
                restored = runtime.checkpoint()
                restored_state = restored.payload.to_dict()["snapshot"]["participants"]["games"]["state"]
                self.assertEqual(restored_state["games"]["A"], saved["games"]["A"])
                first_pid = manager.active_game.gui_process.pid
                manager.active_game.cleanup()
                runtime.restore(checkpoint.event_id, checkpoint_branch_id=source_branch)
                self.assertIsNotNone(manager.active_game)
                self.assertNotEqual(manager.active_game.gui_process.pid, first_pid)
                recreated = runtime.checkpoint().payload.to_dict()["snapshot"]["participants"]["games"]["state"]
                self.assertEqual(recreated["games"]["A"], saved["games"]["A"])
            finally:
                if manager.active_game is not None:
                    manager.active_game.cleanup()
                for key, value in previous.items():
                    services().unregister(key)
                    if value is not None:
                        services().register(key, value)

    def test_chess_repetition_history_survives_json_transfer_without_publishing_moves(self):
        moves = []
        original = PureBoardLogic(on_move=lambda *move: moves.append(move))
        for move in ["g1f3", "g8f6", "f3g1", "f6g8"] * 2:
            self.assertTrue(original.make_move(move)[0])
        restored_moves = []
        restored = PureBoardLogic(on_move=lambda *move: restored_moves.append(move))
        restored.restore_snapshot(JsonDocument(original.snapshot()).to_dict())
        self.assertEqual(restored.snapshot(), original.snapshot())
        self.assertTrue(restored.board.can_claim_threefold_repetition())
        self.assertEqual(restored_moves, [])
        invalid = original.snapshot()
        invalid["fen"] = PureBoardLogic().get_fen()
        invalid["moves"] = invalid["moves"][:-1]
        before = restored.snapshot()
        with self.assertRaises(ValueError):
            restored.restore_snapshot(invalid)
        self.assertEqual(restored.snapshot(), before)

    def test_seabattle_damage_turn_and_placement_round_trip_and_continue_identically(self):
        original = SeaBattleEngine()
        self.assertTrue(original.place_ship(original.player_id, 0, 0, 1, "h")[0])
        self.assertTrue(original.place_ship(original.mita_id, 1, 1, 1, "h")[0])
        original.game_phase = "battle"
        original.make_move(original.player_id, 9, 9)
        original.make_move(original.mita_id, 9, 8)
        saved = JsonDocument(original.snapshot())
        restored = SeaBattleEngine()
        restored.restore_snapshot(saved.to_dict())
        self.assertEqual(JsonDocument(restored.snapshot()), saved)
        self.assertEqual(original.make_move(original.player_id, 1, 1), restored.make_move(restored.player_id, 1, 1))
        self.assertEqual(JsonDocument(restored.snapshot()), JsonDocument(original.snapshot()))

    def test_gui_endpoint_requires_pause_and_normalizes_json_without_replaying_notifications(self):
        responses, notifications, views = queue.Queue(), queue.Queue(), queue.Queue()
        board = SeaBattleEngine()
        state_queue = GameStateQueue(views)
        paused = []
        endpoint = GameSnapshotEndpoint(responses, notifications, lambda: {"board": board.snapshot(), "react_enabled": False},
            lambda state: board.restore_snapshot(state["board"]), paused.append, state_queue)
        state = {"board": JsonDocument(board.snapshot()).to_dict(), "react_enabled": False}
        endpoint.handle({"action": "session_restore", "request_id": "early", "state": state})
        self.assertIn("error", responses.get_nowait())
        endpoint.handle({"action": "session_pause", "request_id": "pause"})
        self.assertEqual(responses.get_nowait()["state"], state)
        self.assertEqual(notifications.get_nowait(), {"event": "session_barrier", "request_id": "pause"})
        endpoint.handle({"action": "session_restore", "request_id": "restore", "state": state})
        response = responses.get_nowait()
        self.assertEqual(response["state"], state)
        self.assertEqual(response["generation"], 1)
        self.assertTrue(notifications.empty())
        state_queue.put({"board": "new"})
        self.assertEqual(views.get_nowait()["_session_generation"], 1)

    def test_host_pause_drains_accepted_facts_before_snapshot_and_rejects_old_views(self):
        with tempfile.TemporaryDirectory() as folder:
            repository = SQLiteTimelineRepository(Path(folder) / "world.db")
            runtime = SessionTimelineRuntime(repository, repository)
            previous = {key: services().get_optional(key) for key in (StateBarrier, SessionTimelineRuntime)}
            services().register(StateBarrier, runtime.state, replace=True)
            services().register(SessionTimelineRuntime, runtime, replace=True)
            stopped = Event()
            variables = {"playingGame": True}
            character = SimpleNamespace(char_id="A", get_variable=lambda key, default=None: variables.get(key, default),
                                        set_variable=lambda key, value: variables.update({key: value}))
            manager = GameManager(character)
            character.game_manager = manager
            game = SeaBattleGame(character, "seabattle", host=manager)
            manager.active_game = game
            game.timeline_selection = runtime.selection
            game.command_queue, game.snapshot_queue, game.reaction_queue = queue.Queue(), queue.Queue(), queue.Queue()
            game.state_queue = queue.Queue()
            board = SeaBattleEngine()
            endpoint = GameSnapshotEndpoint(game.snapshot_queue, game.reaction_queue,
                lambda: {"board": board.snapshot(), "react_enabled": False},
                lambda state: board.restore_snapshot(state["board"]), lambda _paused: None, GameStateQueue(game.state_queue))

            def process():
                while not stopped.is_set():
                    try:
                        endpoint.handle(game.command_queue.get(timeout=.05))
                    except queue.Empty:
                        pass

            worker = Thread(target=process)
            worker.start()
            try:
                game.reaction_queue.put({"event": "player_target_selected", "coord": "A1", "result": "miss",
                                         "mover": "Player", "semantic_id": "accepted", "react": True})
                with runtime.state.exclusive():
                    game.pause_for_snapshot()
                    snapshot = game.capture_paused_snapshot()
                    self.assertEqual(snapshot["game_id"], "seabattle")
                    self.assertEqual(len(tuple(runtime.timeline.events())), 1)
                    game.apply_paused_snapshot(snapshot["state"])
                    self.assertFalse(game.accepts_state({"_session_generation": 0}))
                    self.assertTrue(game.accepts_state({"_session_generation": 1}))
                    snapshot_request(game.command_queue, game.snapshot_queue, "session_resume")
            finally:
                stopped.set()
                worker.join(2)
                for key, value in previous.items():
                    services().unregister(key)
                    if value is not None:
                        services().register(key, value)


if __name__ == "__main__":
    unittest.main()
