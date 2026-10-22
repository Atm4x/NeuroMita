from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from domain.timeline import EventKind, InvalidTimelineOperation, JsonDocument, TimelineConflict, TimelineNotFound
from domain.timeline.archive import SessionArchive
from infrastructure.timeline.bootstrap import bootstrap_timeline
from infrastructure.timeline.sqlite import SQLiteTimelineRepository
from services.session_timeline import SessionTimeline


class TransferTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.source = SQLiteTimelineRepository(self.path / "source.db")
        self.destination = SQLiteTimelineRepository(self.path / "destination.db")
        self.timeline = SessionTimeline.create(self.source, session_id="session", branch_id="main")

    def archive(self):
        self.timeline.join("A", key="join")
        self.timeline.publish(EventKind.PLAYER_MESSAGE, {"message_id": "hello", "content": "Привет"},
                              actor_id="Player", key="hello")
        checkpoint = self.timeline.checkpoint({"world": {"lives": 3}}, key="save")
        child = self.timeline.fork(checkpoint.event_id, branch_id="child").timeline
        child.publish(EventKind.GAME_ACTION, {"move": "e2e4"}, observers=("A",), key="move")
        self.timeline.publish(EventKind.UNITY_EVENT, {"name": "old-future"}, key="old-future")
        return self.source.export_session("session")

    def test_json_round_trip_preserves_all_worlds_identities_timestamps_and_receipts(self):
        archive = self.archive()
        decoded = SessionArchive.from_document(JsonDocument.parse(archive.to_document().canonical))
        self.destination.import_session(decoded)
        self.assertEqual(self.destination.export_session("session").to_document(), archive.to_document())
        for branch in archive.branches:
            original = tuple(SessionTimeline(self.source, branch.branch_id).events())
            restored = tuple(SessionTimeline(self.destination, branch.branch_id).events())
            self.assertEqual(restored, original)
        child = SessionTimeline(self.destination, "child")
        head = child.branch.head_sequence
        child.publish(EventKind.GAME_ACTION, {"move": "e2e4"}, observers=("A",), key="move")
        self.assertEqual(child.branch.head_sequence, head)

    def test_import_is_atomic_when_destination_contains_a_colliding_branch(self):
        archive = self.archive()
        self.destination.create_session("other", "child")
        with self.assertRaises(TimelineConflict):
            self.destination.import_session(archive)
        with self.assertRaises(TimelineNotFound):
            self.destination.get_branch("main")
        self.assertEqual(self.destination.get_branch("child").session_id, "other")

    def test_archive_rejects_cycles_sequence_gaps_unknown_causality_and_tampered_receipts(self):
        document = self.archive().to_document()
        corruptions = []
        data = document.to_dict()
        next(branch for branch in data["branches"] if branch["branch_id"] == "child")["parent_branch_id"] = "child"
        corruptions.append(data)
        data = document.to_dict()
        data["events"][0]["sequence"] += 10
        corruptions.append(data)
        data = document.to_dict()
        data["events"][-1]["links"] = [["caused_by", "missing"]]
        corruptions.append(data)
        data = document.to_dict()
        data["operations"][0]["intent"]["events"] = []
        corruptions.append(data)
        data = document.to_dict()
        data["events"][0]["observers"] = "A"
        corruptions.append(data)
        data = document.to_dict()
        data["events"][0]["schema_version"] = 1.0
        corruptions.append(data)
        for data in corruptions:
            with self.subTest(data=data["events"][0]["sequence"]):
                with self.assertRaises((InvalidTimelineOperation, TimelineNotFound)):
                    SessionArchive.from_document(JsonDocument(data))

    def test_bootstrap_preserves_old_time_and_witnesses_and_never_reimports_into_a_new_session(self):
        path = self.path / "bootstrap.db"
        database = SimpleNamespace(get_connection=lambda: sqlite3.connect(path))
        database.connection = lambda: closing(database.get_connection())
        histories = {
            "A": [{"message_id": "shared", "role": "user", "speaker": "Player", "content": "Hi",
                   "time": "30.09.2026 10:00:00", "_history_row_id": 1}],
            "B": [{"message_id": "shared", "role": "user", "speaker": "Player", "content": "Hi",
                   "time": "30.09.2026 10:00:00", "_history_row_id": 2},
                  {"message_id": "secret", "role": "user", "speaker": "Player", "content": "Private",
                   "time": "01.10.2026 10:00:00", "_history_row_id": 3}],
        }
        resources = SimpleNamespace(history_for=lambda character: SimpleNamespace(
            export_timeline_history=lambda: histories[character],
        ))
        conversation = bootstrap_timeline(database, resources, ["A", "B"])
        messages = conversation.messages("A")
        self.assertEqual([message["message_id"] for message in messages], ["shared"])
        self.assertEqual(messages[0]["time"], "2026-09-30 10:00:00")
        self.assertEqual(len(conversation.messages("B")), 2)
        conversation.runtime.start_session()
        reopened = bootstrap_timeline(database, resources, ["A", "B"])
        self.assertEqual(reopened.messages("A"), ())


if __name__ == "__main__":
    unittest.main()
