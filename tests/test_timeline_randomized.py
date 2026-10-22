from __future__ import annotations

import random
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from domain.timeline import CausalRelation, EventKind, JsonDocument
from domain.timeline.archive import SessionArchive, draft_from_event
from infrastructure.timeline.sqlite import SQLiteTimelineRepository
from services.session_timeline import SessionTimeline


class TimelineModelTests(unittest.TestCase):
    def test_randomized_branches_and_knowledge_match_an_independent_model(self):
        for seed in (13, 47, 103, 366):
            with self.subTest(seed=seed), tempfile.TemporaryDirectory() as folder:
                self._campaign(seed, Path(folder))

    def _campaign(self, seed, folder):
        rng = random.Random(seed)
        repository = SQLiteTimelineRepository(folder / "source.db")
        root = SessionTimeline.create(repository, session_id=f"s:{seed}", branch_id=f"root:{seed}")
        timelines = {root.branch_id: root}
        parents = {root.branch_id: (None, 0)}
        local = {root.branch_id: []}
        all_events = {}
        receipts = []
        characters = ("A", "B", "C")

        def world(branch_id):
            parent, cutoff = parents[branch_id]
            inherited = [event for event in world(parent) if event.sequence <= cutoff] if parent else []
            return inherited + local[branch_id]

        def known(events, character):
            result = {}
            preceding = {}
            for event in events:
                preceding[event.event_id] = event
                if character not in event.observers:
                    continue
                if event.kind is EventKind.CONTEXT_RESET:
                    result.clear()
                result.setdefault(event.event_id, (event, event.sequence))
                if event.kind is EventKind.EVENT_OBSERVED:
                    target = next(link.event_id for link in event.links if link.relation is CausalRelation.OBSERVES)
                    result.setdefault(target, (preceding[target], event.sequence))
            return result

        def verify():
            for branch_id, timeline in timelines.items():
                expected = world(branch_id)
                self.assertEqual(list(timeline.events()), expected)
                self.assertEqual(timeline.branch.head_sequence, expected[-1].sequence if expected else 0)
                cutoff = rng.randrange(timeline.branch.head_sequence + 1)
                prefix = [event for event in expected if event.sequence <= cutoff]
                present = set()
                for event in prefix:
                    if event.kind is EventKind.CHARACTER_JOINED:
                        present.add(event.actor_id)
                    elif event.kind is EventKind.CHARACTER_LEFT:
                        present.discard(event.actor_id)
                self.assertEqual(timeline.present(through=cutoff), frozenset(present))
                for character in characters:
                    knowledge = known(prefix, character)
                    actual = {item.event.event_id: (item.event, item.learned_at)
                              for item in timeline.character_view(character, through=cutoff)}
                    self.assertEqual(actual, knowledge)
                    full = known(expected, character)
                    suffix = {identity: item for identity, item in full.items() if item[1] > cutoff}
                    actual_suffix = {item.event.event_id: (item.event, item.learned_at)
                                     for item in timeline.character_view(character, after=cutoff)}
                    self.assertEqual(actual_suffix, suffix)
                    samples = rng.sample(list(all_events), min(4, len(all_events)))
                    for event_id in samples:
                        self.assertEqual(timeline.knows(character, event_id, through=cutoff), event_id in knowledge)

        for step in range(90):
            timeline = rng.choice(list(timelines.values()))
            branch_id = timeline.branch_id
            preceding = world(branch_id)
            action = rng.randrange(8)
            key = f"command:{seed}:{step}"
            audience = tuple(character for character in characters if rng.choice((True, False)))
            head = timeline.branch.head_sequence
            checkpoints = [event for event in preceding if event.kind is EventKind.CHECKPOINT]
            if action == 0 and checkpoints and len(timelines) < 8:
                checkpoint = rng.choice(checkpoints)
                child = timeline.fork(checkpoint.event_id, branch_id=f"branch:{seed}:{step}").timeline
                timelines[child.branch_id] = child
                parents[child.branch_id] = (branch_id, checkpoint.sequence)
                marker = list(child.events())[-1]
                local[child.branch_id] = [marker]
                all_events[marker.event_id] = marker
                continue
            if action == 1:
                event = timeline.join(rng.choice(characters), key=key)
            elif action == 2:
                event = timeline.leave(rng.choice(characters), key=key)
            elif action == 3 and preceding:
                target = rng.choice(preceding)
                event = timeline.disclose(target.event_id, (rng.choice(characters),), key=key)
            elif action == 4:
                event = timeline.publish(EventKind.CONTEXT_RESET, observers=(rng.choice(characters),), key=key)
            elif action == 5:
                event = timeline.checkpoint({"step": step}, key=key)
            elif action == 6:
                actor = rng.choice(characters)
                event = timeline.publish(EventKind.CHARACTER_MESSAGE, {"content": key}, actor_id=actor,
                                         observers=(*audience, actor), key=key)
            else:
                event = timeline.publish(EventKind.UNITY_EVENT, {"name": key}, observers=audience, key=key)
            local[branch_id].append(event)
            all_events[event.event_id] = event
            receipts.append((branch_id, head, key, event))
            if step % 9 == 0 and receipts:
                owner, original_head, operation_key, original = rng.choice(receipts)
                retry = repository.append(owner, (draft_from_event(original),), expected_head=original_head,
                                          idempotency_key=operation_key)
                self.assertEqual(retry, (original,))
            if step % 15 == 0:
                verify()
        verify()
        archive = repository.export_session(root.branch.session_id)
        copy = SQLiteTimelineRepository(folder / "copy.db")
        copy.import_session(SessionArchive.from_document(JsonDocument.parse(archive.to_document().canonical)))
        for branch_id in timelines:
            self.assertEqual(list(SessionTimeline(copy, branch_id).events()), world(branch_id))


if __name__ == "__main__":
    unittest.main()
