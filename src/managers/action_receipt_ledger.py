"""Bounded per-character ledger of Unity receipts for requested actions."""
from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Any, Iterable

from managers.character_scoped_service import CharacterScopedService

MAX_RECEIPTS = 400

_STATUS_ALIASES = {
    "ok": "applied",
    "success": "applied",
    "done": "applied",
    "error": "failed",
    "failure": "failed",
    "cancel": "cancelled",
    "canceled": "cancelled",
}

STATUSES = (
    "queued",
    "started",
    "applied",
    "completed",
    "cancelled",
    "failed",
    "rejected",
    "unknown",
)

_SHORT_LABELS = {
    "queued": "queued",
    "started": "in progress",
    "applied": "applied",
    "completed": "completed",
    "cancelled": "interrupted",
    "failed": "failed",
    "rejected": "rejected",
    "unknown": "unconfirmed",
}

MAX_DETAIL_CHARS = 160


def normalize_status(value: Any) -> str:
    status = str(value or "").strip().lower()
    status = _STATUS_ALIASES.get(status, status)
    return status if status in STATUSES else "unknown"


def short_label(status: Any) -> str:
    return _SHORT_LABELS.get(normalize_status(status), "unconfirmed")


def _as_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


class ActionReceiptLedger(CharacterScopedService):
    """Remember what Unity reported about actions it was asked to perform.

    Receipts are advisory evidence, not a second action log: they only
    annotate the existing requested-action projection.
    """

    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.RLock()
        self._receipts: dict[str, OrderedDict[str, dict]] = {}

    def record(
        self,
        ref: str,
        status: Any,
        *,
        detail: str = "",
        turn_uid: str = "",
        seq: int = 0,
        max_receipts: int = MAX_RECEIPTS,
    ) -> bool:
        key = str(ref or "").strip()
        if not key:
            return False
        limit = max(20, int(max_receipts or MAX_RECEIPTS))
        sequence = _as_int(seq)
        entry = {
            "ref": key,
            "status": normalize_status(status),
            "detail": " ".join(str(detail or "").split())[:MAX_DETAIL_CHARS],
            "turn_uid": str(turn_uid or ""),
            "seq": sequence,
        }
        with self._lock:
            receipts = self._receipts.setdefault(self.storage_key, OrderedDict())
            previous = receipts.get(key)
            if previous is not None and _as_int(previous.get("seq")) > sequence:
                # An older report must never roll an action back. Unity may
                # flush a queued receipt after the command already reported its
                # real outcome, and the two arrive out of order.
                return False
            receipts.pop(key, None)
            receipts[key] = entry
            while len(receipts) > limit:
                receipts.popitem(last=False)
        return True

    def record_many(self, receipts: Iterable[dict], *, turn_uid: str = "") -> int:
        stored = 0
        for raw in receipts or ():
            if not isinstance(raw, dict):
                continue
            ref = str(raw.get("ref") or "").strip()
            if not ref:
                continue
            if self.record(
                ref,
                raw.get("status"),
                detail=str(raw.get("detail") or ""),
                turn_uid=str(raw.get("turn_uid") or turn_uid),
                seq=raw.get("seq"),
            ):
                stored += 1
        return stored

    def receipt_for(self, ref: str) -> dict | None:
        key = str(ref or "").strip()
        if not key:
            return None
        with self._lock:
            entry = self._receipts.get(self.storage_key, {}).get(key)
            return dict(entry) if entry else None

    def status_for(self, ref: str) -> str:
        entry = self.receipt_for(ref)
        return str(entry["status"]) if entry else ""

    def clear(self, **_: object) -> None:
        with self._lock:
            self._receipts.pop(self.storage_key, None)
