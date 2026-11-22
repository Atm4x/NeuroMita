from __future__ import annotations

import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from domain.timeline import EventKind
from infrastructure.timeline.sqlite import SQLiteTimelineRepository
from services.conversation_timeline import ConversationTimeline
from services.timeline_history_queries import TimelineHistoryQueries
from services.timeline_runtime import SessionTimelineRuntime


class HistoryQueryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repository = SQLiteTimelineRepository(Path(self.temp.name) / "world.db")
        self.runtime = SessionTimelineRuntime(self.repository, self.repository)
        self.conversation = ConversationTimeline(self.runtime)
        self.queries = self.conversation.history_queries

    def add(self, index, recipients=("A",)):
        return self.conversation.record_message({"message_id": str(index), "content": [{"type": "text", "text": str(index)}]},
                                               recipients, actor_id="Player", player=True)

    def test_new_pages_consume_only_new_facts_and_return_detached_data(self):
        self.add(1)
        branch = self.runtime.timeline.branch_id
        self.queries.page(branch, "A", limit=10)
        old_head = self.runtime.timeline.branch.head_sequence
        self.add(2)
        with patch.object(self.repository, "read", wraps=self.repository.read) as read:
            page = self.queries.page(branch, "A", limit=10)
        self.assertTrue(all(call.kwargs["after"] >= old_head for call in read.call_args_list))
        page[0]["content"][0]["text"] = "changed by caller"
        self.assertEqual(self.queries.page(branch, "A", limit=10)[0]["content"][0]["text"], "1")
        with patch.object(self.repository, "read", wraps=self.repository.read) as read:
            self.assertEqual(self.queries.count(branch, "A"), 2)
            self.assertTrue(self.queries.contains(branch, "A", "1"))
            read.assert_not_called()

    def test_hidden_revised_restored_and_reset_views_match_reconstruction(self):
        first = self.add(1, ("A", "B"))
        second = self.add(2)
        timeline = self.runtime.timeline
        for action in (
            lambda: timeline.publish(EventKind.MESSAGE_REVISED,
                                     {"event_id": first.event_id, "message": {"content": "edited"}},
                                     observers=("A",), key="edit"),
            lambda: timeline.publish(EventKind.MESSAGE_HIDDEN, {"event_ids": [first.event_id]}, observers=("A",), key="hide"),
            lambda: timeline.publish(EventKind.MESSAGE_RESTORED, {"event_id": first.event_id}, observers=("A",), key="restore"),
            lambda: timeline.publish(EventKind.CONTEXT_RESET, observers=("A",), key="reset"),
            lambda: timeline.disclose(second.event_id, ("A",), key="redisclose"),
        ):
            for character in ("A", "B"):
                self.assertEqual(self.queries.messages(timeline.branch_id, character), timeline.messages(character))
            action()
        for character in ("A", "B"):
            self.assertEqual(self.queries.messages(timeline.branch_id, character), timeline.messages(character))

    def test_historical_queries_never_use_a_newer_cached_projection(self):
        first = self.add(1)
        timeline = self.runtime.timeline
        head = timeline.branch.head_sequence
        timeline.publish(EventKind.MESSAGE_REVISED, {"event_id": first.event_id, "message": {"content": "new"}},
                         observers=("A",), key="new")
        self.assertEqual(self.queries.messages(timeline.branch_id, "A")[0]["content"], "new")
        with ThreadPoolExecutor(max_workers=3) as pool:
            results = list(pool.map(lambda _: self.queries.messages(timeline.branch_id, "A", through=head), range(6)))
        self.assertTrue(all(result[0]["content"] == [{"type": "text", "text": "1"}] for result in results))
        self.assertEqual(self.queries.messages(timeline.branch_id, "A")[0]["content"], "new")

    def test_projection_eviction_is_semantically_invisible(self):
        self.add(1, ("A", "B"))
        queries = TimelineHistoryQueries(self.repository, max_views=1)
        branch = self.runtime.timeline.branch_id
        original = queries.messages(branch, "A")
        queries.messages(branch, "B")
        with patch.object(self.repository, "read", wraps=self.repository.read) as read:
            reconstructed = queries.messages(branch, "A")
        self.assertEqual(reconstructed, original)
        self.assertTrue(any(call.kwargs["after"] == 0 for call in read.call_args_list))

    def test_disclosing_a_past_reset_is_information_rather_than_a_new_reset(self):
        timeline = self.runtime.timeline
        old_reset = timeline.publish(EventKind.CONTEXT_RESET, observers=("A",), key="old-reset")
        self.add(1)
        timeline.publish(EventKind.CONTEXT_RESET, observers=("A",), key="new-reset")
        self.add(2)
        self.queries.messages(timeline.branch_id, "A")
        timeline.disclose(old_reset.event_id, ("A",), key="tell-about-old-reset")
        messages = self.queries.messages(timeline.branch_id, "A")
        self.assertEqual([message["message_id"] for message in messages], ["2"])
        self.assertEqual(messages, timeline.messages("A"))


if __name__ == "__main__":
    unittest.main()
