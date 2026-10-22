from __future__ import annotations

import queue
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.services import services
from domain.timeline import EventKind, TimelineConflict
from infrastructure.timeline.sqlite import SQLiteTimelineRepository
from managers.game_manager import GameManager
from modules.Chess.game_instance import ChessGame
from services.timeline_runtime import SessionTimelineRuntime
from services.unity_timeline import UnityTimelineIngress


class ProducerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        repository = SQLiteTimelineRepository(Path(self.temp.name) / "world.db")
        self.runtime = SessionTimelineRuntime(repository, repository)
        self.unity = UnityTimelineIngress(self.runtime)
        self.previous = services().get_optional(SessionTimelineRuntime)
        services().register(SessionTimelineRuntime, self.runtime, replace=True)
        self.addCleanup(self._restore_services)

    def _restore_services(self):
        services().unregister(SessionTimelineRuntime)
        if self.previous is not None:
            services().register(SessionTimelineRuntime, self.previous)

    def test_unity_facts_are_independent_of_reaction_admission_and_retry_roster_drift(self):
        request = {"req_id": "unity-1", "type": "react", "data": {}, "context": {
            "dialogue": {"conversation_id": "room", "participants": [
                {"actor_id": "a", "character_id": "A"},
                {"actor_id": "b", "character_id": "B", "can_hear_speaker": False},
            ]}, "runtime_events": [{"name": "ItemPickedUp", "data": {"item_id": "key"}}],
        }}
        event_id = self.unity.ingest(request, "A", ["A", "B"])
        event = self.runtime.timeline.event(event_id)
        self.assertEqual(event.kind, EventKind.UNITY_EVENT)
        self.assertTrue(self.runtime.timeline.knows("A", event_id))
        self.assertFalse(self.runtime.timeline.knows("B", event_id))
        self.runtime.timeline.leave("A", key="later-left")
        head = self.runtime.timeline.branch.head_sequence
        self.assertEqual(self.unity.ingest(request, "A", ["A", "B"]), event_id)
        self.assertEqual(self.runtime.timeline.branch.head_sequence, head)
        self.assertNotIn("A", self.runtime.timeline.present())

    def test_changed_unity_request_identity_fails_and_timer_kinds_differ(self):
        request = {"req_id": "1", "type": "idle_timeout", "context": {}}
        event_id = self.unity.ingest(request, "A", ["A"])
        self.assertEqual(self.runtime.timeline.event(event_id).kind, EventKind.PLAYER_INACTIVE)
        with self.assertRaises(TimelineConflict):
            self.unity.ingest(dict(request, type="periodic"), "A", ["A"])
        opportunity = self.unity.ingest({"req_id": "2", "type": "periodic"}, "A", ["A"])
        self.assertEqual(self.runtime.timeline.event(opportunity).kind, EventKind.PROACTIVE_OPPORTUNITY)

    def test_empty_ingress_keeps_only_a_receipt_without_technical_timeline_events(self):
        request = {"req_id": "empty", "type": "answer"}
        self.assertIsNone(self.unity.ingest(request, "A", ["A"]))
        self.assertIsNone(self.unity.ingest(request, "A", ["A"]))
        self.assertEqual(tuple(self.runtime.timeline.events()), ())

    def test_ingress_reaction_target_is_witnessed_by_the_requested_character(self):
        request = {"req_id": "private-events", "type": "react", "context": {"runtime_events": [
            {"name": "Public", "observers": ["A", "B"]},
            {"name": "Private", "observers": ["B"]},
        ]}}
        target = self.unity.ingest(request, "A", ["A", "B"])
        events = tuple(self.runtime.timeline.events())
        self.assertEqual(target, events[0].event_id)
        self.assertFalse(self.runtime.timeline.knows("A", events[1].event_id))
        self.assertEqual(self.unity.ingest(request, "A", ["A", "B"]), target)
        private = {"req_id": "only-private", "type": "react", "context": {"runtime_events": [
            {"name": "Private", "observers": ["B"]},
        ]}}
        self.assertIsNone(self.unity.ingest(private, "A", ["A", "B"]))

    def test_retry_cannot_change_the_fallback_reason_kind(self):
        request = {"req_id": "reason", "type": "react", "data": {"reason": "noise", "reason_type": "Door"}}
        self.unity.ingest(request, "A", ["A"])
        with self.assertRaises(TimelineConflict):
            self.unity.ingest(dict(request, data={"reason": "noise", "reason_type": "Footstep"}), "A", ["A"])

    def _game(self):
        character = SimpleNamespace(char_id="A", get_variable=lambda *_: True)
        manager = GameManager(character)
        game = ChessGame(character, "chess", host=manager)
        game.timeline_selection = self.runtime.selection
        manager.active_game = game
        return manager, game

    def test_game_move_receipt_and_reaction_share_one_fact(self):
        manager, game = self._game()
        move = {"semantic_id": "move-1", "uci": "e2e4", "san": "e4", "mover": "Player", "ply": 1}
        event_id = game._publish_chess_move(move)
        with patch("managers.game_manager.ChatAPI.react", return_value=False) as react:
            game._dispatch_player_move_reaction(move)
        self.assertEqual(react.call_args.kwargs["event_id"], event_id)
        self.assertEqual(len(tuple(self.runtime.timeline.events())), 1)
        self.assertEqual(self.runtime.timeline.event(event_id).payload.to_dict()["data"]["uci"], "e2e4")

    def test_old_game_cannot_emit_into_new_session(self):
        manager, game = self._game()
        self.runtime.start_session()
        self.assertIsNone(game.publish_event("ChessMove", {"uci": "e2e4"}))
        with patch("managers.game_manager.ChatAPI.react") as react:
            self.assertFalse(manager.request_character_reaction(game, "late"))
            react.assert_not_called()
        self.assertEqual(tuple(self.runtime.timeline.events()), ())

    def test_board_model_reports_every_accepted_move_including_character_moves(self):
        from modules.Chess.board_logic import PureBoardLogic

        events = []
        board = PureBoardLogic(on_move=lambda *event: events.append(event))
        self.assertTrue(board.make_move("e2e4")[0])
        self.assertTrue(board.make_move("c7c5")[0])
        self.assertFalse(board.make_move("c7c5")[0])
        self.assertEqual([event[:2] for event in events], [("e2e4", "e4"), ("c7c5", "c5")])

    def test_chess_controller_publishes_move_facts_without_starting_the_engine(self):
        from modules.Chess.engine_handler import ChessGameController

        events = queue.Queue()
        controller = ChessGameController(1500, True, None, None, None, None, semantic_event_queue=events)
        controller.board_logic.make_move("e2e4")
        controller.board_logic.make_move("c7c5")
        first, second = events.get_nowait(), events.get_nowait()
        self.assertEqual((first["mover"], second["mover"]), ("Player", "Character"))
        self.assertFalse(first["react"])
        self.assertNotEqual(first["semantic_id"], second["semantic_id"])
        self.assertTrue(events.empty())


if __name__ == "__main__":
    unittest.main()
