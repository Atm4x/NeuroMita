"""Facts a Unity request brought must not also appear as its own history."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_SRC = Path(__file__).resolve().parents[2]
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from infrastructure.timeline.sqlite import SQLiteTimelineRepository
from services.conversation_timeline import ConversationTimeline
from services.timeline_runtime import SessionTimelineRuntime
from services.unity_timeline import UnityTimelineIngress, UnityIngestResult


class UnityEventSameTurnExclusionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repository = SQLiteTimelineRepository(Path(self._tmp.name) / "timeline.db")
        self.runtime = SessionTimelineRuntime(self.repository, self.repository)
        self.conversation = ConversationTimeline(self.runtime)
        self.ingress = UnityTimelineIngress(self.runtime)

    def tearDown(self):
        self._tmp.cleanup()

    def _request(self, req_id: str, *descriptions: str) -> dict:
        return {
            "req_id": req_id,
            "type": "react",
            "context": {"runtime_events": list(descriptions)},
        }

    def _history_texts(self, character_id: str) -> str:
        return "\n".join(str(item.get("content") or "") for item in
                          self.conversation.context_messages(character_id))

    def test_ingest_reports_every_event_it_created(self):
        result = self.ingress.ingest(
            self._request("r1", "Player crouched nearby.", "Player moved about 8 m nearby."),
            "Crazy", ["Crazy"],
        )

        self.assertIsInstance(result, UnityIngestResult)
        self.assertEqual(len(result.event_ids), 2)
        self.assertIn(result.trigger_id, result.event_ids)

    def test_the_turn_hides_the_events_it_brought(self):
        result = self.ingress.ingest(
            self._request("r1", "Player moved about 8 m nearby."), "Crazy", ["Crazy"],
        )
        turn = self.runtime.capture(character_id="Crazy",
                                    consumed_event_ids=result.event_ids)

        with self.runtime.turn_scope(turn):
            history = self._history_texts("Crazy")

        self.assertNotIn("Player moved about 8 m nearby.", history)

    def test_the_next_turn_sees_them_as_past_session_events(self):
        result = self.ingress.ingest(
            self._request("r1", "Player moved about 8 m nearby."), "Crazy", ["Crazy"],
        )
        first = self.runtime.capture(character_id="Crazy",
                                     consumed_event_ids=result.event_ids)
        with self.runtime.turn_scope(first):
            self.assertNotIn("Player moved", self._history_texts("Crazy"))

        second = self.runtime.capture(character_id="Crazy")
        with self.runtime.turn_scope(second):
            history = self._history_texts("Crazy")

        self.assertIn("[Event]", history)
        self.assertIn("Player moved about 8 m nearby.", history)

    def test_a_turn_without_consumed_events_keeps_the_full_window(self):
        self.ingress.ingest(self._request("r1", "Player crouched nearby."), "Crazy", ["Crazy"])
        turn = self.runtime.capture(character_id="Crazy")

        with self.runtime.turn_scope(turn):
            self.assertIn("Player crouched nearby.", self._history_texts("Crazy"))

    def test_a_repeated_request_reuses_the_same_event_ids(self):
        first = self.ingress.ingest(self._request("r1", "Door opened."), "Crazy", ["Crazy"])
        second = self.ingress.ingest(self._request("r1", "Door opened."), "Crazy", ["Crazy"])

        self.assertEqual(first.event_ids, second.event_ids)


    def test_history_replays_speech_without_the_old_turn_instruction(self):
        envelope = (
            "[DIALOGUE] Participants in this conversation (3):\nPlayer\nCrazy (Mita)\nKind (Mita)\n"
            "[SPEAKER] Kind (Mita) said the following full reply:\n"
            "<FULL_REPLY>Wait by the door.\nI will come back.</FULL_REPLY>\n"
            "Segment addressing:\nSegment addressed to you: <Wait by the door.>\n"
            "Now it is your turn to speak."
        )
        sentences = {"reaction_events": [{"reason_type": "DialogueAuto", "reason_content": envelope}]}
        first = self.ingress.ingest({"req_id": "turn1", "type": "react", "data": sentences}, "Crazy", [])
        retried = self.ingress.ingest({"req_id": "turn1", "type": "react", "data": sentences}, "Crazy", [])
        again = self.ingress.ingest({"req_id": "turn2", "type": "react", "data": sentences}, "Crazy", [])
        self.assertEqual(first, retried)
        self.assertNotEqual(first, again)
        self.assertEqual(self.runtime.timeline.event(first.trigger_id).payload.to_dict()["description"], envelope)

        turn = self.runtime.capture(character_id="Crazy", consumed_event_ids=again.event_ids)
        with self.runtime.turn_scope(turn):
            prompt_history = self._history_texts("Crazy")
        self.assertEqual(prompt_history.count("Wait by the door."), 1)
        self.assertIn("[Past dialogue] Kind (Mita) said:", prompt_history)
        self.assertNotIn("Now it is your turn", prompt_history)
        self.assertNotIn("[DIALOGUE]", prompt_history)
        self.assertEqual(self._history_texts("Crazy").count("Wait by the door."), 2)

    def test_explicitly_private_event_stays_out_of_prompt_and_history(self):
        from controllers.prompt_controller import PromptController
        from game_connections.handlers.actions.create_task import build_game_state_payload, _build_react_prompt

        known = {"description": "Door opened.", "observers": ["B", "A"]}
        secret = {"description": "B learned a private clue.", "observers": ["B"]}
        request = {"req_id": "visible", "type": "react", "context": {"runtime_events": [known, secret]}}
        self.ingress.ingest(request, "A", ["A", "B"])

        state = build_game_state_payload(request["context"], "A")
        rendered = PromptController._build_unity_runtime_events_message(state)
        self.assertIn("Door opened.", rendered["content"])
        self.assertNotIn("private clue", rendered["content"])
        self.assertNotIn("private clue", self._history_texts("A"))
        self.assertIn("private clue", self._history_texts("B"))

        private_batch = {"reaction_events": [{"reason_content": "Private", "observers": ["B"]}],
                         "reason_content": "Private"}
        self.assertFalse(_build_react_prompt(private_batch, character_id="A")[0])
        self.assertTrue(_build_react_prompt(private_batch, character_id="B")[0])

    def test_a_private_fallback_reason_does_not_create_a_public_trigger(self):
        from game_connections.handlers.actions.create_task import _build_react_prompt

        data = {"reason_type": "DialogueAuto", "reason_content": "Private", "observers": ["B"]}
        request = {"req_id": "private-fallback", "type": "react", "data": data}
        result = self.ingress.ingest(request, "A", ["A", "B"])
        self.assertIsNone(result.trigger_id)
        self.assertFalse(_build_react_prompt(data, character_id="A")[0])
        self.assertNotIn("Private", self._history_texts("A"))
        self.assertIn("Private", self._history_texts("B"))


    def test_dialogue_auto_appears_once_on_the_gemini_wire(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from controllers.history_controller import HistoryController
        from controllers.prompt_controller import PromptController
        from game_connections.handlers.actions.create_task import _build_react_prompt
        from handlers.llm_providers.base import LLMRequest
        from handlers.llm_providers.gemini_provider import GeminiProvider
        from handlers.llm_providers.message_preprocessor import preprocess_messages_for_provider
        from services.contracts import PromptBuildRequest, RequestPolicy
        from services.timeline_context import TimelineContext

        marker = "An earlier witness saw the blue key."
        reason = (
            "[DIALOGUE] Participants in this conversation (3):\nPlayer\nCrazy (Mita)\nKind (Mita)\n"
            "[SPEAKER] Kind (Mita) said the following to the group or another participant:\n"
            f"<FULL_REPLY>{marker}</FULL_REPLY>\n"
            "You heard this as a participant in the conversation, but were not addressed."
        )
        data = {"reaction_events": [{"reason_type": "DialogueAuto", "reason_content": reason}]}
        request = {"req_id": "auto", "type": "react", "data": data,
                   "context": {"runtime_events": ["Another observation from this turn."]}}
        ingest = self.ingress.ingest(request, "Crazy", ["Crazy"])
        queued = self.runtime.capture(character_id="Crazy", consumed_event_ids=ingest.event_ids)
        lines, *_ = _build_react_prompt(data, character_id="Crazy")
        instruction = "\n".join(lines)
        with self.runtime.turn_scope(queued):
            entered = self.conversation.begin_turn(
                character_id="Crazy", recipients=["Crazy"], incoming=None,
                actor_id="Kind", player=False, origin_message_id=None, event_type="react",
                instruction=instruction, operation_id="auto", target_event_id=ingest.trigger_id,
            )

        char = SimpleNamespace(char_id="Crazy", get_variable=lambda key, default=None: default)
        summaries = SimpleNamespace(load=lambda *_: None)
        context = TimelineContext(self.conversation, summaries)
        history = HistoryController()
        with self.runtime.turn_scope(entered), patch(
            "controllers.history_controller.services", return_value=SimpleNamespace(get_optional=lambda _: context),
        ):
            prepared = history._prepare_for_prompt_locked(char, 10, False, False, {})
        self.assertEqual(entered.consumed_event_ids, ingest.event_ids)
        self.assertFalse(any("Another observation" in m["content"] for m in prepared.messages))
        builder = PromptController()
        builder._build_system_messages = lambda *_a, **_kw: ([], [], [])
        builder._build_system_state_message = lambda *_a, **_kw: None
        with patch("controllers.prompt_controller.use", return_value=SimpleNamespace(
            prepare_for_prompt=lambda **_: prepared,
        )):
            result = builder.build(PromptBuildRequest(
                character=char, event_type="react", system_input=instruction,
                policy=RequestPolicy(system_input_role="event"),
            ))
        provider = GeminiProvider()
        req = LLMRequest(model="offline-test", messages=result.messages)
        preprocess_messages_for_provider(req, provider)
        wire = provider._format_messages_for_gemini_api(req.messages)
        contents = [item for item in wire["contents"] if any(marker in part.get("text", "") for part in item["parts"])]
        self.assertEqual(len(contents), 1)
        self.assertEqual(contents[0]["role"], "user")
        self.assertIn("[RUNTIME EVENT]", contents[0]["parts"][0]["text"])
        self.assertNotIn("[Current UnityEvent]", repr(wire))

    def test_target_not_already_rendered_remains_available(self):
        result = self.ingress.ingest(self._request("separate", "Door opened."), "Crazy", ["Crazy"])
        turn = self.conversation.begin_turn(
            character_id="Crazy", recipients=["Crazy"], incoming=None, actor_id="",
            player=False, origin_message_id=None, event_type="react", instruction="",
            operation_id="look", target_event_id=result.trigger_id,
        )
        with self.runtime.turn_scope(turn):
            self.assertIn("Door opened.", self.conversation.target_context("Crazy")["content"])


if __name__ == "__main__":
    unittest.main()
