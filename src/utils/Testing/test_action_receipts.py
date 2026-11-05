"""Action refs, execution receipts and their projection into the prompt."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_SRC = Path(__file__).resolve().parents[2]
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from domain.action_refs import action_ref
from game_connections.handlers.actions.action_receipt import parse_receipts
from managers.action_memory import (
    append_requested_actions,
    render_requested_actions,
    requested_action_records,
    requested_action_records_from_messages,
    requested_actions_from_structured,
)
from managers.action_receipt_ledger import ActionReceiptLedger


STRUCTURED = {
    "segments": [
        {"text": "ok", "clothes": ["school"]},
        {"text": "hm", "music": ["calm_1", "calm_2"]},
    ]
}


class ActionRefTests(unittest.TestCase):
    def test_ref_is_stable_and_position_sensitive(self):
        first = action_ref("turn-1", 0, "clothes", 0)
        self.assertEqual(first, action_ref("turn-1", 0, "clothes", 0))
        self.assertNotEqual(first, action_ref("turn-2", 0, "clothes", 0))
        self.assertNotEqual(first, action_ref("turn-1", 0, "clothes", 1))
        self.assertNotEqual(first, action_ref("turn-1", 1, "clothes", 0))
        self.assertEqual(len(first), 16)


class ReceiptLedgerTests(unittest.TestCase):
    def _ledger(self, name="Mita"):
        return ActionReceiptLedger().bind(name, name)

    def test_status_aliases_and_unknown_values(self):
        ledger = self._ledger()
        ledger.record("a", "ok")
        ledger.record("b", "error", detail="no such outfit")
        ledger.record("c", "whatever")
        self.assertEqual(ledger.status_for("a"), "applied")
        self.assertEqual(ledger.status_for("b"), "failed")
        self.assertEqual(ledger.receipt_for("b")["detail"], "no such outfit")
        self.assertEqual(ledger.status_for("c"), "unknown")

    def test_ledger_is_bounded(self):
        ledger = self._ledger()
        for index in range(30):
            ledger.record(f"ref-{index}", "applied", max_receipts=20)
        self.assertEqual(ledger.status_for("ref-0"), "")
        self.assertEqual(ledger.status_for("ref-29"), "applied")

    def test_ledgers_are_per_character(self):
        first = self._ledger("Mita")
        second = self._ledger("Kind")
        first.record("shared", "applied")
        self.assertEqual(second.status_for("shared"), "")

    def test_clear_forgets_receipts(self):
        ledger = self._ledger()
        ledger.record("a", "applied")
        ledger.clear()
        self.assertEqual(ledger.status_for("a"), "")


class ReceiptPayloadTests(unittest.TestCase):
    def test_valid_receipts_get_refs(self):
        parsed = parse_receipts("turn-1", [
            {"segment": 0, "field": "clothes", "index": 0, "status": "applied"},
            {"segment": 1, "field": "music", "index": 1, "status": "failed", "detail": "no track"},
        ])
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]["ref"], action_ref("turn-1", 0, "clothes", 0))
        self.assertEqual(parsed[1]["status"], "failed")
        self.assertEqual(parsed[1]["detail"], "no track")

    def test_malformed_receipts_are_dropped(self):
        self.assertEqual(parse_receipts("", [{"segment": 0, "field": "clothes"}]), [])
        self.assertEqual(parse_receipts("turn-1", [
            "nope",
            {"segment": -1, "field": "clothes", "index": 0},
            {"segment": 0, "field": "", "index": 0},
            {"segment": "x", "field": "clothes", "index": 0},
        ]), [])


class ActionProjectionTests(unittest.TestCase):
    def test_records_keep_refs_while_plain_list_stays_compatible(self):
        records = requested_action_records(STRUCTURED, turn_uid="turn-1")
        self.assertEqual(len(records), 3)
        self.assertTrue(all(record["ref"] for record in records))
        self.assertEqual(
            requested_actions_from_structured(STRUCTURED),
            ["outfit: school", "music: calm_1", "music: calm_2"],
        )

    def test_records_from_messages_use_the_turn_uid(self):
        records = requested_action_records_from_messages([
            {"role": "assistant", "task_uid": "turn-9", "structured_data": STRUCTURED},
            {"role": "user", "structured_data": STRUCTURED},
        ])
        self.assertEqual(len(records), 3)
        self.assertEqual(records[0]["ref"], action_ref("turn-9", 0, "clothes", 0))

    def test_render_marks_confirmed_and_failed_actions(self):
        records = requested_action_records(STRUCTURED, turn_uid="turn-1")
        receipts = {
            records[0]["ref"]: "applied",
            records[1]["ref"]: "failed",
        }
        rendered = render_requested_actions(records, receipts)
        self.assertIn("- outfit: school [applied]", rendered)
        self.assertIn("- music: calm_1 [failed]", rendered)
        self.assertIn("- music: calm_2\n", rendered)
        self.assertNotIn("calm_2 [", rendered)

    def test_append_accepts_a_lookup_callable(self):
        records = requested_action_records(STRUCTURED, turn_uid="turn-1")
        statuses = {records[0]["ref"]: "completed"}
        projected = append_requested_actions(
            "Sure.", records, lambda ref: statuses.get(ref, "")
        )
        self.assertIn("outfit: school [completed]", projected)
        self.assertIn("[REQUESTED ACTIONS THIS TURN]", projected)


if __name__ == "__main__":
    unittest.main()
