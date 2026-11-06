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

        self.assertIn("[Past session event", history)
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


if __name__ == "__main__":
    unittest.main()
