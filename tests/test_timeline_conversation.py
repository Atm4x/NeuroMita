from __future__ import annotations

import sys
import tempfile
import sqlite3
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from domain.timeline import CausalRelation, ConcurrentTimelineWrite, EventKind, InvalidTimelineOperation
from infrastructure.timeline.sqlite import SQLiteTimelineRepository
from infrastructure.timeline.assets import SQLiteTimelineAssets
from managers.conversation_event_writer import ConversationEventWriter
from services.conversation_timeline import ConversationTimeline
from services.timeline_runtime import SessionTimelineRuntime


class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "world.db"
        self.repo = SQLiteTimelineRepository(self.path)
        self.runtime = SessionTimelineRuntime(self.repo, self.repo)
        self.conversation = ConversationTimeline(self.runtime, SQLiteTimelineAssets(lambda: sqlite3.connect(self.path)))

    @staticmethod
    def message(message_id="in:question", content="Hello"):
        return {"message_id": message_id, "content": content, "speaker": "Player"}

    def begin(self, **kwargs):
        args = dict(character_id="A", recipients=("A", "B"), incoming=self.message(),
                    actor_id="Player", player=True, origin_message_id=None,
                    event_type="chat", instruction="", operation_id="op")
        args.update(kwargs)
        return self.conversation.begin_turn(**args)

    def test_incoming_fact_survives_generation_failure_and_is_not_duplicated_on_retry(self):
        first = self.begin()
        self.assertEqual(len(tuple(self.runtime.timeline.events())), 1)
        retry = self.begin()
        self.assertEqual(retry.trigger_id, first.trigger_id)
        self.assertEqual(len(tuple(self.runtime.timeline.events())), 1)

    def test_completed_turn_has_one_shared_message_and_per_character_roles(self):
        turn = self.begin()
        with self.runtime.turn_scope(turn):
            self.conversation.complete_turn(self.message(), {
                "message_id": "out:answer", "speaker": "A", "content": "Hi",
            }, ("A", "B"), player=True, origin_message_id=None)
        events = tuple(self.runtime.timeline.events())
        self.assertEqual(len(events), 2)
        self.assertEqual(events[1].links[0].relation, CausalRelation.REPLY_TO)
        self.assertEqual(events[1].links[0].event_id, events[0].event_id)
        self.assertEqual(self.conversation.messages("A")[-1]["role"], "assistant")
        self.assertEqual(self.conversation.messages("B")[-1]["role"], "user")
        self.assertEqual(self.conversation.messages("C"), ())

    def test_prompt_world_is_pinned_and_does_not_duplicate_current_input(self):
        turn = self.begin()
        self.conversation.record_message(self.message("in:later", "Later"), ("A",), actor_id="Player", player=True)
        with self.runtime.turn_scope(turn):
            self.assertEqual(self.conversation.messages("A"), ())
        self.assertEqual(len(self.conversation.messages("A")), 2)

    def test_reaction_and_proactive_opportunity_remain_distinct(self):
        event = self.runtime.timeline.publish(EventKind.GAME_ENDED, {"game": "chess"},
                                             observers=("A",), key="end")
        turn = self.begin(incoming=None, target_event_id=event.event_id)
        with self.runtime.turn_scope(turn):
            self.conversation.complete_turn(None, {"message_id": "out:react", "speaker": "A", "content": "Won!"},
                                            ("A",), player=True, origin_message_id=None)
        reply = self.conversation.find_message("out:react")
        self.assertEqual(reply.links[0].relation, CausalRelation.REACT_TO)
        opportunity = self.begin(incoming=None, initiate=True, operation_id="proactive")
        self.assertEqual(self.runtime.timeline.event(opportunity.trigger_id).kind, EventKind.PROACTIVE_OPPORTUNITY)
        with self.runtime.turn_scope(opportunity):
            self.conversation.complete_turn(None, {"message_id": "out:initiative", "speaker": "A", "content": "A new topic"},
                                            ("A",), player=True, origin_message_id=None)
        self.assertEqual(self.conversation.find_message("out:initiative").links[0].relation, CausalRelation.CAUSED_BY)
        afk = self.begin(incoming=None, event_type="idle_timeout", operation_id="afk")
        self.assertEqual(self.runtime.timeline.event(afk.trigger_id).kind, EventKind.PLAYER_INACTIVE)

    def test_private_event_cannot_be_used_as_reaction_target(self):
        event = self.runtime.timeline.publish(EventKind.UNITY_EVENT, observers=("B",), key="secret")
        with self.assertRaises(InvalidTimelineOperation):
            self.begin(incoming=None, target_event_id=event.event_id)

    def test_switching_away_and_back_invalidates_a_running_turn(self):
        turn = self.begin()
        original = self.runtime.selection.branch_id
        with self.runtime.turn_scope(turn):
            self.runtime.start_session()
            self.runtime.activate(original)
            with self.assertRaises(ConcurrentTimelineWrite):
                self.conversation.complete_turn(None, {
                    "message_id": "out:late", "speaker": "A", "content": "Too late",
                }, ("A",), player=True, origin_message_id=None)
        self.assertEqual(len(tuple(self.runtime.timeline.events())), 1)

    def test_selected_session_survives_reopen_and_new_session_is_empty(self):
        self.begin()
        self.runtime.start_session()
        selected = self.runtime.selection
        reopened = SessionTimelineRuntime(SQLiteTimelineRepository(self.path), SQLiteTimelineRepository(self.path))
        self.assertEqual(reopened.selection, selected)
        self.assertEqual(tuple(reopened.timeline.events()), ())

    def test_import_only_grants_the_character_who_actually_had_the_message(self):
        first = dict(self.message(), role="user", _history_row_id=10)
        self.assertEqual(self.conversation.import_history("A", (first,)), 1)
        self.assertEqual(self.conversation.import_history("B", (first,)), 0)
        event = self.conversation.find_message(first["message_id"])
        self.assertEqual(event.observers, frozenset({"A"}))
        self.assertTrue(self.runtime.timeline.knows("B", event.event_id))
        self.assertFalse(self.runtime.timeline.knows("C", event.event_id))

    def test_transport_and_provider_diagnostics_are_not_session_facts(self):
        message = dict(self.message(), thinking="private", llm_model="provider", sample_id="sample",
                       structured_data={"text": "hi", "_raw_json": "debug", "reasoning": "private"})
        event = self.conversation.record_message(message, ("A",), actor_id="Player", player=True)
        payload = event.payload.to_dict()["message"]
        self.assertNotIn("thinking", payload)
        self.assertNotIn("llm_model", payload)
        self.assertEqual(payload["structured_data"], {"text": "hi"})

    def test_reply_by_timeline_identity_includes_the_original_target_without_new_input(self):
        first = self.begin()
        turn = self.begin(incoming=None, origin_message_id=first.trigger_id)
        with self.runtime.turn_scope(turn):
            self.assertTrue(turn.reply)
            self.assertEqual(self.conversation.messages("A"), ())
            self.assertEqual(self.conversation.target_context("A")["content"], "Hello")

    def test_camera_observation_is_not_a_player_utterance_or_a_duplicate_prompt_image(self):
        incoming = self.message("camera:1", [{"type": "image_url", "image_url": {"url": "data:image/png;base64,AA=="}}])
        incoming["image_source"] = "mita_camera"
        turn = self.begin(incoming=None, observation_message=incoming)
        event = self.runtime.timeline.event(turn.trigger_id)
        self.assertEqual(event.kind, EventKind.CHARACTER_OBSERVATION)
        self.assertEqual(event.actor_id, "A")
        self.assertFalse(turn.reply)
        with self.runtime.turn_scope(turn):
            self.assertEqual(self.conversation.context_messages("A"), ())
            self.assertIsNone(self.conversation.target_context("A"))
        self.assertEqual(self.conversation.messages("A")[0]["role"], "user")
        self.assertEqual(self.conversation.messages("B"), ())

    def test_writer_separates_player_speech_from_private_camera_and_retries_both(self):
        from services.contracts import ChatGenerationRequest

        caches = {identity: [] for identity in ("A", "B")}
        characters = {identity: SimpleNamespace(char_id=identity, add_messages_to_history=caches[identity].extend)
                      for identity in caches}
        writer = ConversationEventWriter(characters.get, self.conversation)
        request = ChatGenerationRequest(character_id="A", user_input="Look around", req_id="camera-text",
                                        image_data=[b"picture"], image_source="MITA_CAMERA", participants=["A", "B"])
        turn = writer.begin_turn(request, "A")
        retry = writer.begin_turn(request, "A")
        self.assertEqual(turn.input_event_ids, retry.input_event_ids)
        events = tuple(self.runtime.timeline.events())
        self.assertEqual([event.kind for event in events], [EventKind.PLAYER_MESSAGE, EventKind.CHARACTER_OBSERVATION])
        self.assertEqual(events[0].observers, frozenset({"A", "B"}))
        self.assertEqual(events[1].observers, frozenset({"A"}))
        self.assertEqual(turn.trigger_id, events[0].event_id)
        self.assertTrue(turn.reply)
        with self.runtime.turn_scope(turn):
            self.assertEqual(self.conversation.context_messages("A"), ())
            writer.write_turn(responder_character_id="A", sender="Player", participants=["A", "B"],
                              user_input="Look around", image_data=[b"picture"], image_source="mita_camera",
                              req_id="camera-text", origin_message_id=None, assistant_text="I see it",
                              assistant_target="Player", event_type="chat", task_uid=None)
        outgoing = tuple(self.runtime.timeline.events())[-1]
        self.assertEqual(outgoing.links[0].event_id, events[0].event_id)
        self.assertEqual(len(self.conversation.messages("A")), 3)
        self.assertEqual(len(self.conversation.messages("B")), 2)
        self.assertEqual(caches["B"][0]["content"], [{"type": "text", "text": "Look around"}])

    def test_camera_only_is_private_even_in_compatibility_cache_fanout(self):
        from services.contracts import ChatGenerationRequest

        caches = {identity: [] for identity in ("A", "B")}
        characters = {identity: SimpleNamespace(char_id=identity, add_messages_to_history=caches[identity].extend)
                      for identity in caches}
        writer = ConversationEventWriter(characters.get, self.conversation)
        request = ChatGenerationRequest(character_id="A", req_id="camera-only", image_data=[b"picture"],
                                        image_source="mita_camera", participants=["A", "B"])
        turn = writer.begin_turn(request, "A")
        self.assertFalse(turn.reply)
        with self.runtime.turn_scope(turn):
            writer.write_turn(responder_character_id="A", sender="Player", participants=["A", "B"],
                              user_input="", image_data=[b"picture"], image_source="mita_camera",
                              req_id="camera-only", origin_message_id=None, assistant_text="I see it",
                              assistant_target="Player", event_type="chat", task_uid=None)
        self.assertEqual(len(caches["A"]), 2)
        self.assertEqual(len(caches["B"]), 1)
        self.assertEqual(caches["B"][0]["speaker"], "A")
        self.assertEqual(tuple(self.runtime.timeline.events())[-1].links[0].relation, CausalRelation.REACT_TO)

    def test_queued_turn_is_invalidated_by_a_character_context_reset(self):
        queued = self.runtime.capture(character_id="A")
        self.runtime.timeline.publish(EventKind.CONTEXT_RESET, observers=("A",), key="reset")
        with self.assertRaises(ConcurrentTimelineWrite):
            with self.runtime.turn_scope(queued):
                self.fail("Stale work must not reach generation")

    def test_switching_session_cancels_the_actual_generation_token(self):
        from core.cancellation import CancellationToken

        cancellation = CancellationToken()
        with self.runtime.turn_scope(self.runtime.capture(character_id="A"), cancellation=cancellation):
            self.runtime.start_session()
            self.assertTrue(cancellation.cancelled)

    def test_nested_scope_keeps_outer_cancellation_registration(self):
        from core.cancellation import CancellationToken

        cancellation = CancellationToken()
        turn = self.runtime.capture(character_id="A")
        with self.runtime.turn_scope(turn, cancellation=cancellation):
            with self.runtime.turn_scope(turn, cancellation=cancellation):
                pass
            self.runtime.start_session()
            self.assertTrue(cancellation.cancelled)

    def test_real_model_generation_boundary_records_input_before_provider_failure(self):
        from controllers.model_controller import ModelController
        from services.contracts import ChatGenerationRequest

        character = SimpleNamespace(char_id="A")
        controller = object.__new__(ModelController)
        controller._get_character_ref = lambda _: character
        controller.event_writer = ConversationEventWriter(lambda _: character, self.conversation)
        controller._generate_chat_serialized = lambda *_: None
        request = ChatGenerationRequest(character_id="A", user_input="Failure test", req_id="failed")
        self.assertIsNone(controller.generate_chat(request))
        self.assertEqual(self.conversation.find_message("in:failed").payload.to_dict()["content"],
                         [{"type": "text", "text": "Failure test"}])

    def test_writer_projects_one_canonical_turn_into_two_character_caches(self):
        from services.contracts import ChatGenerationRequest

        characters = {identity: SimpleNamespace(char_id=identity, add_messages_to_history=lambda rows: list(range(len(rows))))
                      for identity in ("A", "B")}
        writer = ConversationEventWriter(characters.get, self.conversation)
        request = ChatGenerationRequest(character_id="A", user_input="Hello", req_id="multi", task_uid="task", participants=["A", "B"])
        turn = writer.begin_turn(request, "A")
        with self.runtime.turn_scope(turn):
            result = writer.write_turn(
                responder_character_id="A", sender="Player", participants=["A", "B"], user_input="Hello",
                image_data=[], req_id="multi", origin_message_id=None, assistant_text="Hi",
                assistant_target="Player", event_type="chat", task_uid="task",
            )
        self.assertTrue(result.history_committed)
        self.assertEqual(len(tuple(self.runtime.timeline.events())), 2)
        self.assertEqual(self.conversation.find_message("out:task").payload.to_dict()["message"]["context_world"]["through"],
                         turn.context_head)

    def test_semantic_reaction_policy_does_not_delete_the_event(self):
        from controllers.chat_controller import ChatController

        event = self.runtime.timeline.publish(EventKind.GAME_ENDED, observers=("A",), key="ended")
        controller = object.__new__(ChatController)
        controller.settings = {"REACT_ENABLED": False}
        with patch("controllers.chat_controller.use", return_value=self.conversation):
            self.assertFalse(controller.react(character_id="A", event_id=event.event_id))
        self.assertEqual(self.runtime.timeline.event(event.event_id), event)


if __name__ == "__main__":
    unittest.main()
