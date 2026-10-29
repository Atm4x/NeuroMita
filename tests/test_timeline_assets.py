from __future__ import annotations

import base64
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from contextlib import closing

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from domain.timeline import EventKind, InvalidTimelineOperation, JsonDocument
from domain.timeline.archive import SessionArchive
from domain.timeline.assets import TimelineAsset
from infrastructure.timeline.assets import SQLiteTimelineAssets
from infrastructure.timeline.sqlite import SQLiteTimelineRepository
from services.conversation_timeline import ConversationTimeline
from services.timeline_runtime import SessionTimelineRuntime


class TimelineAssetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "world.db"
        self.repository = SQLiteTimelineRepository(self.path)
        self.assets = SQLiteTimelineAssets(lambda: sqlite3.connect(self.path))
        self.runtime = SessionTimelineRuntime(self.repository, self.repository)
        self.conversation = ConversationTimeline(self.runtime, self.assets)

    @staticmethod
    def image(data=b"opaque-image-content"):
        return {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(data).decode("ascii")},
                "display_role": "assistant"}

    def record(self, identity, parts):
        return self.conversation.record_message({"message_id": identity, "content": parts}, ("A",), actor_id="Player", player=True)

    def test_identical_images_are_stored_once_and_events_hold_only_immutable_references(self):
        first = self.record("one", [self.image()])
        second = self.record("two", [self.image()])
        self.assertEqual(first.payload.to_dict()["content"], second.payload.to_dict()["content"])
        reference = first.payload.to_dict()["content"][0]
        self.assertEqual(reference["type"], "image_ref")
        self.assertNotIn("base64", first.payload.canonical)
        with closing(sqlite3.connect(self.path)) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM timeline_assets").fetchone()[0], 1)
        self.assertEqual(self.conversation.content.materialize(self.conversation.messages("A"))[0]["content"], [self.image()])

    def test_text_context_and_metadata_paging_do_not_load_image_bytes(self):
        first = self.record("one", [self.image(b"old")])
        last = self.record("two", [self.image(b"new")])
        with patch.object(self.assets, "get", wraps=self.assets.get) as get:
            self.conversation.context_messages("A")
            page = self.conversation.history_queries.page(self.runtime.timeline.branch_id, "A", limit=1)
            get.assert_not_called()
            hydrated = self.conversation.content.materialize(page)
        self.assertEqual(hydrated[0]["content"], [self.image(b"new")])
        self.assertEqual([call.args[0] for call in get.call_args_list], [last.payload.to_dict()["content"][0]["asset_id"]])
        self.assertNotEqual(first.payload.to_dict()["content"], last.payload.to_dict()["content"])

    def test_one_materialization_reads_a_shared_attachment_only_once(self):
        self.record("one", [self.image(), self.image()])
        with patch.object(self.assets, "get", wraps=self.assets.get) as get:
            materialized = self.conversation.content.materialize(self.conversation.messages("A"))
        self.assertEqual(get.call_count, 1)
        self.assertEqual(materialized[0]["content"], [self.image(), self.image()])

    def test_reused_reference_must_match_metadata_even_after_the_blob_is_memoized(self):
        self.record("one", [self.image(), self.image()])
        messages = list(self.conversation.messages("A"))
        messages[0]["content"][1]["byte_size"] += 1
        with self.assertRaises(InvalidTimelineOperation):
            self.conversation.content.materialize(messages)

    def test_history_editing_does_not_materialize_attachments(self):
        from managers.timeline_history_view import TimelineHistoryView

        self.record("one", [self.image(b"old")])
        self.record("two", [self.image(b"new")])
        view = TimelineHistoryView("A", SimpleNamespace(load_history=lambda: {"variables": {}}), self.conversation)
        with patch.object(self.assets, "get", wraps=self.assets.get) as get:
            self.assertEqual(len(view.get_messages_for_compression(1)), 1)
            self.assertTrue(view.delete_message("one"))
            get.assert_not_called()
            self.assertEqual(view.load_history()["messages"][0]["content"], [self.image(b"new")])
            self.assertEqual(get.call_count, 1)

    def test_portable_archive_contains_attachment_closure_and_preserves_image_content(self):
        self.record("one", [self.image()])
        self.record("two", [self.image()])
        archive = self.repository.export_session(self.runtime.timeline.branch.session_id)
        self.assertEqual(len(archive.assets), 1)
        decoded = SessionArchive.from_document(JsonDocument.parse(archive.to_document().canonical))
        target_path = Path(self.temp.name) / "target.db"
        target = SQLiteTimelineRepository(target_path)
        target.import_session(decoded)
        store = SQLiteTimelineAssets(lambda: sqlite3.connect(target_path))
        target.select("copy", archive.root_branch_id, expected=None)
        conversation = ConversationTimeline(SessionTimelineRuntime(target, target, workspace_name="copy"), store)
        self.assertEqual(conversation.content.materialize(conversation.messages("A")),
                         self.conversation.content.materialize(self.conversation.messages("A")))

    def test_missing_or_tampered_attachments_fail_before_event_publication_or_import(self):
        self.record("one", [self.image()])
        archive = self.repository.export_session(self.runtime.timeline.branch.session_id).to_document().to_dict()
        archive["assets"] = []
        with self.assertRaises(InvalidTimelineOperation):
            SessionArchive.from_document(JsonDocument(archive))
        asset = TimelineAsset.create("image/png", b"missing")
        timeline = self.runtime.timeline
        head = timeline.branch.head_sequence
        with self.assertRaises(InvalidTimelineOperation):
            timeline.publish(EventKind.PLAYER_MESSAGE, {"content": [asset.reference()]},
                             actor_id="Player", observers=("A",), key="missing-asset")
        self.assertEqual(timeline.branch.head_sequence, head)

    def test_corrupted_asset_bytes_are_not_returned_to_a_provider(self):
        event = self.record("one", [self.image()])
        identity = event.payload.to_dict()["content"][0]["asset_id"]
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute("UPDATE timeline_assets SET content=? WHERE asset_id=?", (b"corrupt", identity))
            conn.commit()
        with self.assertRaises(InvalidTimelineOperation):
            self.assets.get(identity)

    def test_image_retry_uses_reference_identity_instead_of_republishing_binary_content(self):
        first = self.record("one", [self.image()])
        self.assertEqual(self.record("one", [self.image()]), first)
        self.assertEqual(self.runtime.timeline.branch.head_sequence, 1)
        asset = TimelineAsset.create("image/jpg", b"same")
        self.assertEqual(asset, TimelineAsset.create("image/jpeg", b"same"))
        self.assertNotEqual(asset.asset_id, TimelineAsset.create("image/png", b"same").asset_id)

    def test_failed_semantic_append_does_not_export_unreachable_staged_assets(self):
        with self.assertRaises(InvalidTimelineOperation):
            self.conversation.record_message({"message_id": "bad", "content": [self.image()]}, ("A",), actor_id="")
        archive = self.repository.export_session(self.runtime.timeline.branch.session_id)
        self.assertEqual(archive.events, ())
        self.assertEqual(archive.assets, ())


if __name__ == "__main__":
    unittest.main()
