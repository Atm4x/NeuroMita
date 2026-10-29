from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from domain.timeline import EventKind, TimelineConflict
from infrastructure.timeline.context import SQLiteContextSummaries
from infrastructure.timeline.sqlite import SQLiteTimelineRepository
from managers.timeline_history_view import TimelineHistoryView
from services.conversation_timeline import ConversationTimeline
from services.timeline_context import TimelineContext
from services.timeline_runtime import SessionTimelineRuntime


class _Cache:
    def __init__(self):
        self.messages = []
        self.variables = {}

    def load_history(self):
        return {"messages": self.messages.copy(), "variables": self.variables.copy()}

    def add_messages(self, messages):
        self.messages.extend(messages)

    def clear_history(self):
        self.messages.clear()

    def update_variables_batch(self, values):
        self.variables.update(values)


class HistoryViewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "world.db"
        repository = SQLiteTimelineRepository(self.path)
        self.runtime = SessionTimelineRuntime(repository, repository)
        self.conversation = ConversationTimeline(self.runtime)
        self.cache = _Cache()
        self.view = TimelineHistoryView("A", self.cache, self.conversation)
        summaries = SQLiteContextSummaries(lambda: sqlite3.connect(self.path))
        self.context = TimelineContext(self.conversation, summaries)

    @staticmethod
    def message(index, content=None):
        return {"message_id": f"m:{index}", "role": "user", "speaker": "Player",
                "content": str(index) if content is None else content}

    def test_cache_is_not_conversation_authority(self):
        self.view.add_messages([self.message(1), self.message(2)])
        self.cache.messages = [self.message(3, "cache-only")]
        self.assertEqual([message["content"] for message in self.view.load_history()["messages"]], ["1", "2"])

    def test_canonical_history_does_not_read_disposable_message_rows(self):
        self.view.add_message(self.message(1))
        self.cache.load_variables = lambda: {"mood": 5}
        with patch.object(self.cache, "load_history", side_effect=AssertionError("Disposable rows must not be read")):
            history = self.view.load_history()
        self.assertEqual(history["variables"], {"mood": 5})
        self.assertEqual(history["messages"][0]["content"], "1")

    def test_note_and_message_paging_share_one_projection(self):
        self.view.add_messages([self.message(1), {"message_id": "note", "role": "system", "content": "A fact"}, self.message(2)])
        self.assertEqual(self.view.get_total_messages_count(), 3)
        self.assertEqual([message["message_id"] for message in self.view.get_recent_messages(1, 1)], ["note"])
        self.assertEqual(self.view.get_recent_messages(0), [])

    def test_hide_edit_and_restore_preserve_original_fact_and_other_character_view(self):
        first = self.conversation.record_message(self.message(1), ("A", "B"), actor_id="Player", player=True)
        self.view.add_message(self.message(2))
        self.assertTrue(self.view.delete_message("m:1"))
        self.assertEqual(len(self.conversation.messages("B")), 1)
        self.assertEqual(first.payload.to_dict()["content"], "1")
        self.view.add_message(self.message(1))
        self.assertTrue(self.view.contains_message_id("m:1"))
        changed = self.view.load_history()
        changed["messages"][0]["content"] = "Edited"
        self.view.save_history(changed)
        self.assertEqual(self.view.load_history()["messages"][0]["content"], "Edited")
        self.assertEqual(self.runtime.timeline.event(first.event_id).payload.to_dict()["content"], "1")

    def test_reset_forgets_old_knowledge_and_explicit_redisclosure_can_restore_it(self):
        self.view.add_message(self.message(1))
        event = self.conversation.find_message("m:1")
        self.view.clear_history()
        self.assertFalse(self.runtime.timeline.knows("A", event.event_id))
        self.assertEqual(self.view.load_history()["messages"], [])
        self.view.add_message(self.message(1))
        self.assertTrue(self.runtime.timeline.knows("A", event.event_id))
        self.assertTrue(self.view.contains_message_id("m:1"))

    def test_invalid_history_batch_does_not_commit_a_valid_prefix(self):
        before = self.runtime.timeline.branch.head_sequence
        with self.assertRaises(TimelineConflict):
            self.view.add_messages([self.message(1), self.message(1, "conflict")])
        self.assertEqual(self.runtime.timeline.branch.head_sequence, before)

    def test_loading_an_older_character_snapshot_restores_original_message_order(self):
        self.view.add_messages([self.message(1), self.message(2)])
        snapshot = self.view.load_history()
        self.view.delete_message("m:1")
        self.view.add_message(self.message(3))
        self.view.save_history(snapshot)
        self.assertEqual([message["message_id"] for message in self.view.load_history()["messages"]],
                         ["m:1", "m:2"])

    def test_invalid_snapshot_replacement_does_not_partially_hide_messages(self):
        self.view.add_messages([self.message(1), self.message(2)])
        head = self.runtime.timeline.branch.head_sequence
        with self.assertRaises(TimelineConflict):
            self.view.save_history({"messages": [self.message(3), self.message(3)]})
        self.assertEqual(self.runtime.timeline.branch.head_sequence, head)
        self.assertEqual([message["message_id"] for message in self.view.load_history()["messages"]], ["m:1", "m:2"])

    def test_summary_is_rejected_after_prefix_edit_or_context_reset(self):
        self.view.add_messages([self.message(1), self.message(2)])
        messages = self.conversation.context_messages("A")
        self.context.store("A", messages[:1], "Summary of 1")
        summary, suffix = self.context.unsummarized("A")
        self.assertEqual(summary, "Summary of 1")
        self.assertEqual([message["message_id"] for message in suffix], ["m:2"])
        data = self.view.load_history()
        data["messages"][0]["content"] = "Revised"
        self.view.save_history(data)
        self.assertEqual(self.context.unsummarized("A")[0], "")
        self.view.clear_history()
        self.assertEqual(self.context.unsummarized("A"), ("", []))

    def test_stale_summary_cannot_publish_after_its_source_changed(self):
        self.view.add_messages([self.message(1), self.message(2)])
        prefix = self.conversation.context_messages("A")
        self.view.delete_message("m:1")
        self.context.store("A", prefix, "Stale summary")
        self.assertEqual(self.context.unsummarized("A")[0], "")

    def test_verified_summary_reads_only_the_unsummarized_acquisition_suffix(self):
        self.view.add_messages([self.message(1), self.message(2)])
        prefix = self.conversation.context_messages("A")
        self.context.store("A", prefix[:1], "Summary")
        self.view.add_message(self.message(3))
        with patch.object(self.runtime.repository, "read", wraps=self.runtime.repository.read) as read:
            summary, remaining = self.context.unsummarized("A")
        self.assertEqual(summary, "Summary")
        self.assertEqual([message["message_id"] for message in remaining], ["m:2", "m:3"])
        self.assertTrue(all(call.kwargs["after"] >= prefix[0]["timeline_learned_at"] for call in read.call_args_list))

    def test_learning_another_characters_editorial_event_does_not_change_own_projection(self):
        self.conversation.record_message(self.message(1), ("A", "B"), actor_id="Player", player=True)
        self.view.delete_message("m:1")
        hidden = list(self.runtime.timeline.events())[-1]
        self.runtime.timeline.disclose(hidden.event_id, ("B",), key="tell-b-about-editorial-change")
        self.assertEqual([message["message_id"] for message in self.conversation.messages("B")], ["m:1"])

    def test_suffix_does_not_redisclose_a_fact_already_in_the_summary(self):
        self.view.add_message(self.message(1))
        source = self.conversation.find_message("m:1")
        prefix = self.conversation.context_messages("A")
        self.context.store("A", prefix, "Summary")
        self.runtime.timeline.disclose(source.event_id, ("A",), key="redundant-reminder")
        self.assertEqual(self.context.unsummarized("A"), ("Summary", []))

    def test_branch_has_its_own_summary_and_can_reply_to_inherited_message_identity(self):
        self.view.add_message(self.message(1))
        original = self.conversation.find_message("m:1")
        self.context.store("A", self.conversation.context_messages("A"), "Original summary")
        checkpoint = self.runtime.timeline.checkpoint({}, key="save")
        self.runtime.restore(checkpoint.event_id)
        self.assertEqual(self.conversation.find_message("m:1"), original)
        self.assertEqual(self.context.unsummarized("A")[0], "")
        retry = self.conversation.record_message(self.message(1), ("A",), actor_id="Player", player=True)
        self.assertEqual(retry, original)

    def test_world_events_enter_only_the_context_of_their_witnesses(self):
        self.runtime.timeline.publish(EventKind.GAME_ENDED, {"game_id": "chess", "description": "Player won"},
                                      observers=("A",), key="game")
        self.assertIn("Player won", self.conversation.context_messages("A")[0]["content"])
        self.assertEqual(self.conversation.context_messages("B"), ())


if __name__ == "__main__":
    unittest.main()
