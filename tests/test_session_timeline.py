from __future__ import annotations

import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from domain.timeline import (
    CausalLink, CausalRelation, ConcurrentTimelineWrite, EventDraft, EventKind,
    InvalidTimelineOperation, JsonDocument, TimelineConflict, TimelineNotFound,
)
from infrastructure.timeline.sqlite import SQLiteTimelineRepository
from services.session_timeline import SessionTimeline


class TimelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "timeline.db"
        self.repo = SQLiteTimelineRepository(self.path)
        self.timeline = SessionTimeline.create(self.repo, session_id="session", branch_id="main")

    def publish(self, key, *, observers=("A",), kind=EventKind.UNITY_EVENT, **kwargs):
        return self.timeline.publish(kind, {"name": key}, observers=observers, key=key, **kwargs)

    def test_json_has_value_semantics_and_rejects_lossy_values(self):
        source = {"nested": [{"text": "привет"}]}
        payload = JsonDocument(source)
        source["nested"][0]["text"] = "changed"
        detached = payload.to_dict()
        detached["nested"].clear()
        self.assertEqual(payload.to_dict(), {"nested": [{"text": "привет"}]})
        for invalid in ({1: "key"}, {"n": float("nan")}, {"n": object()}):
            with self.assertRaises(InvalidTimelineOperation):
                JsonDocument(invalid)

    def test_reopen_preserves_order_payload_observers_and_causality(self):
        first = self.publish("door")
        response = self.timeline.publish(
            EventKind.CHARACTER_MESSAGE, {"content": "I heard it"}, actor_id="A",
            observers=("A",), links=(CausalLink(CausalRelation.REACT_TO, first.event_id),), key="react",
        )
        reopened = SessionTimeline(SQLiteTimelineRepository(self.path), "main")
        self.assertEqual(tuple(reopened.events()), (first, response))
        self.assertEqual(reopened.messages("A")[0]["role"], "assistant")

    def test_atomic_batch_can_link_to_prefix_and_rolls_back_on_invalid_suffix(self):
        question = self.timeline.draft(EventKind.PLAYER_MESSAGE, {"content": "Hi"},
                                       actor_id="Player", observers=("A",), key="question")
        answer = self.timeline.draft(EventKind.CHARACTER_MESSAGE, {"content": "Hello"},
                                     actor_id="A", observers=("A",), key="answer",
                                     links=(CausalLink(CausalRelation.REPLY_TO, question.event_id),))
        committed = self.timeline.append((question, answer), expected_head=0, key="turn")
        self.assertEqual([e.sequence for e in committed], [1, 2])
        invalid = self.timeline.draft(EventKind.CHARACTER_MESSAGE, actor_id="B", observers=("B",),
                                      links=(CausalLink(CausalRelation.REPLY_TO, question.event_id),))
        with self.assertRaises(InvalidTimelineOperation):
            self.timeline.append((self.timeline.draft(EventKind.UNITY_EVENT), invalid),
                                 expected_head=2, key="bad-turn")
        self.assertEqual(self.timeline.branch.head_sequence, 2)
        self.assertEqual(len(tuple(self.timeline.events())), 2)

    def test_retry_is_identical_after_head_advanced_and_changed_intent_is_rejected(self):
        first = self.publish("first")
        self.publish("later")
        self.assertEqual(self.publish("first"), first)
        with self.assertRaises(TimelineConflict):
            self.timeline.publish(EventKind.UNITY_EVENT, {"name": "different"},
                                  observers=("A",), key="first")
        self.assertEqual(self.timeline.branch.head_sequence, 2)

    def test_external_message_identity_is_unique_in_a_branch_world_and_batches_are_atomic(self):
        first = self.timeline.draft(EventKind.PLAYER_MESSAGE, {"message_id": "same", "content": "one"},
                                    actor_id="Player", observers=("A",))
        duplicate = self.timeline.draft(EventKind.PLAYER_MESSAGE, {"message_id": "same", "content": "two"},
                                        actor_id="Player", observers=("A",))
        with self.assertRaises(TimelineConflict):
            self.timeline.append((first, duplicate), expected_head=0, key="duplicates")
        self.assertEqual(self.timeline.branch.head_sequence, 0)
        self.timeline.append((first,), expected_head=0, key="first")
        checkpoint = self.timeline.checkpoint({}, key="save")
        child = self.timeline.fork(checkpoint.event_id).timeline
        with self.assertRaises(TimelineConflict):
            child.append((duplicate,), expected_head=child.branch.head_sequence, key="inherited-duplicate")
        self.timeline.publish(EventKind.PLAYER_MESSAGE, {"message_id": "future", "content": "parent"},
                              actor_id="Player", observers=("A",), key="future")
        alternative = child.publish(EventKind.PLAYER_MESSAGE, {"message_id": "future", "content": "child"},
                                     actor_id="Player", observers=("A",), key="future")
        self.assertEqual(self.repo.find_message(child.branch_id, "future"), alternative)

    def test_automatic_audience_is_frozen_on_retry(self):
        joined = self.timeline.join("A", key="join-a")
        first = self.timeline.publish(EventKind.UNITY_EVENT, {"name": "door"}, key="door")
        self.timeline.join("B", key="join-b")
        self.assertEqual(self.timeline.join("A", key="join-a"), joined)
        self.assertEqual(self.timeline.publish(EventKind.UNITY_EVENT, {"name": "door"}, key="door"), first)
        self.assertFalse(self.timeline.knows("B", first.event_id))

    def test_simultaneous_writers_have_one_winner_and_no_partial_append(self):
        barrier = Barrier(2)

        def write(key):
            repo = SQLiteTimelineRepository(self.path)
            draft = EventDraft(EventKind.UNITY_EVENT, JsonDocument({"key": key}))
            barrier.wait()
            try:
                return repo.append("main", (draft,), expected_head=0, idempotency_key=key)
            except ConcurrentTimelineWrite:
                return None

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(write, ("a", "b")))
        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertEqual(self.timeline.branch.head_sequence, 1)

    def test_private_event_requires_explicit_later_disclosure(self):
        secret = self.publish("secret", observers=("A",))
        self.publish("public", observers=("A", "B"))
        self.assertFalse(self.timeline.knows("B", secret.event_id))
        learned = self.timeline.disclose(secret.event_id, ("B",), key="tell-b")
        before = self.timeline.character_view("B", through=learned.sequence - 1)
        after = self.timeline.character_view("B")
        self.assertNotIn(secret.event_id, {item.event.event_id for item in before})
        self.assertEqual(next(item.learned_at for item in after if item.event == secret), learned.sequence)
        self.assertFalse(self.timeline.knows("C", secret.event_id))

    def test_leaving_and_rejoining_does_not_reveal_missed_events(self):
        self.timeline.join("A", key="join")
        seen = self.timeline.publish(EventKind.UNITY_EVENT, key="seen")
        self.timeline.leave("A", key="leave")
        missed = self.timeline.publish(EventKind.UNITY_EVENT, key="missed")
        self.timeline.join("A", key="return")
        self.assertTrue(self.timeline.knows("A", seen.event_id))
        self.assertFalse(self.timeline.knows("A", missed.event_id))

    def test_nested_forks_preserve_parent_future_and_clip_all_ancestor_segments(self):
        self.timeline.join("A", key="join")
        checkpoint = self.timeline.checkpoint({"world": {"lives": 2}}, key="save")
        old_future = self.publish("old-future")
        restored = self.timeline.fork(checkpoint.event_id, branch_id="alternate")
        child = restored.timeline
        self.assertEqual(restored.snapshot.to_dict(), {"world": {"lives": 2}})
        self.assertEqual(child.present(), frozenset({"A"}))
        self.assertEqual([e.kind for e in child.events()][-1], EventKind.BRANCH_CREATED)
        with self.assertRaises(TimelineNotFound):
            child.event(old_future.event_id)
        child_checkpoint = child.checkpoint({"world": {"lives": 1}}, key="save")
        child.publish(EventKind.UNITY_EVENT, key="child-future")
        nested = child.fork(child_checkpoint.event_id, branch_id="nested").timeline
        sequences = [e.sequence for e in nested.events()]
        self.assertEqual(sequences, list(range(1, nested.branch.head_sequence + 1)))
        self.assertEqual(self.timeline.event(old_future.event_id), old_future)
        self.assertEqual(self.timeline.fork(checkpoint.event_id, branch_id="alternate").timeline.branch_id,
                         "alternate")

    def test_causality_cannot_reference_a_sibling_or_future_event(self):
        checkpoint = self.timeline.checkpoint({}, key="save")
        future = self.publish("future")
        child = self.timeline.fork(checkpoint.event_id, branch_id="child").timeline
        with self.assertRaises(TimelineNotFound):
            child.publish(EventKind.UNITY_EVENT, links=(CausalLink(CausalRelation.CAUSED_BY, future.event_id),),
                          observers=(), key="bad")
        with self.assertRaises(TimelineNotFound):
            self.publish("missing", links=(CausalLink(CausalRelation.CAUSED_BY, "missing"),))

    def test_order_is_not_inferred_as_causality(self):
        self.publish("door")
        unsolicited = self.timeline.publish(EventKind.CHARACTER_MESSAGE, {"content": "New topic"},
                                            actor_id="A", observers=("A",), key="initiate")
        self.assertEqual(unsolicited.links, ())

    def test_read_is_paged_and_bounded_at_a_fixed_head(self):
        for i in range(7):
            self.publish(str(i), observers=("A",) if i % 2 == 0 else ("B",))
        first = self.repo.read("main", limit=2, observer="A")
        self.assertEqual([event.sequence for event in first], [1, 3])
        second = self.repo.read("main", after=first[-1].sequence, through=6, limit=2, observer="A")
        self.assertEqual([event.sequence for event in second], [5])
        for kwargs in ({"limit": 0}, {"after": -1}, {"through": -1}, {"observer": ""}):
            with self.assertRaises(InvalidTimelineOperation):
                self.repo.read("main", **kwargs)

    def test_session_and_fork_identity_conflicts_are_explicit(self):
        self.assertEqual(self.repo.create_session("session", "main"), self.timeline.branch)
        with self.assertRaises(TimelineConflict):
            self.repo.create_session("session", "other")
        event = self.publish("not-a-checkpoint")
        with self.assertRaises(InvalidTimelineOperation):
            self.timeline.fork(event.event_id)


if __name__ == "__main__":
    unittest.main()
