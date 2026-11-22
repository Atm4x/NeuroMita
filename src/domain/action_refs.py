"""Stable identifiers for one requested action inside an assistant turn.

Unity reports what happened to an action it was asked to perform. Both sides
derive the identifier from the same turn and position, so no shared database
or extra round trip is needed to match a receipt to a request.
"""
from __future__ import annotations

import hashlib

ACTION_REF_VERSION = "1"


def action_ref(turn_uid: str, segment_index: int, field: str, item_index: int) -> str:
    """Return a short deterministic id for one action of one turn.

    ``turn_uid`` is the task identity both processes know; the rest is the
    position of the action inside the structured response.
    """
    raw = "|".join((
        ACTION_REF_VERSION,
        str(turn_uid or "").strip(),
        str(int(segment_index)),
        str(field or "").strip(),
        str(int(item_index)),
    ))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
