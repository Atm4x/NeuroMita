"""Unity reports what actually happened to actions of one finished turn."""
from __future__ import annotations

from typing import Any, Dict, Iterable

from domain.action_refs import action_ref
from game_connections.handlers.registry import RequestContext
from managers.character_resource_manager import get_character_resource_manager
from main_logger import logger

MAX_RECEIPTS_PER_REQUEST = 64
MAX_FIELD_CHARS = 32


def parse_receipts(turn_uid: str, items: Iterable[Any]) -> list[dict]:
    """Convert a wire receipt into the ledger form, dropping malformed entries."""
    turn = str(turn_uid or "").strip()
    if not turn or not isinstance(items, (list, tuple)):
        return []
    parsed: list[dict] = []
    for item in list(items)[:MAX_RECEIPTS_PER_REQUEST]:
        if not isinstance(item, dict):
            continue
        field = str(item.get("field") or "").strip()[:MAX_FIELD_CHARS]
        if not field:
            continue
        try:
            segment = int(item.get("segment", 0))
            index = int(item.get("index", 0))
        except (TypeError, ValueError):
            continue
        if not 0 <= segment <= 255 or not 0 <= index <= 255:
            continue
        try:
            sequence = max(0, int(item.get("seq") or 0))
        except (TypeError, ValueError):
            sequence = 0
        parsed.append({
            "ref": action_ref(turn, segment, field, index),
            "status": item.get("status"),
            "detail": str(item.get("detail") or "")[:200],
            "turn_uid": turn,
            "seq": sequence,
        })
    return parsed


class ActionReceiptAction:
    """Persist execution receipts so the next prompt can tell requested from done.

    A receipt never triggers a generation and never replaces the requested
    action list; it only annotates it for later turns.
    """

    async def handle(self, request: Dict[str, Any], ctx: RequestContext) -> None:
        data = request.get("data") if isinstance(request.get("data"), dict) else {}
        character = str(
            request.get("character") or request.get("character_id") or data.get("character") or ""
        ).strip()
        turn_uid = str(data.get("turn_uid") or data.get("task_uid") or request.get("task_uid") or "").strip()
        items = data.get("receipts") if "receipts" in data else request.get("receipts")
        receipts = parse_receipts(turn_uid, items)
        if not character or not turn_uid or not receipts:
            await ctx.server.send_error(ctx.writer, "Invalid action_receipt payload")
            return

        received = len(items) if isinstance(items, (list, tuple)) else 0
        accepted = min(received, MAX_RECEIPTS_PER_REQUEST)
        truncated = received - accepted
        invalid = accepted - len(receipts)
        if truncated:
            logger.warning(
                "[action_receipt] %s turn=%s truncated %s of %s receipts (limit=%s)",
                character, turn_uid, truncated, received, MAX_RECEIPTS_PER_REQUEST,
            )

        ledger = get_character_resource_manager().action_receipts_for(character)
        stored = ledger.record_many(receipts, turn_uid=turn_uid)
        logger.debug(
            "[action_receipt] %s turn=%s stored=%s/%s",
            character, turn_uid, stored, len(receipts),
        )
        await ctx.server.send_json(ctx.writer, {
            "type": "action_receipt_ack",
            "turn_uid": turn_uid,
            "stored": stored,
            "received": received,
            "truncated": truncated,
            "invalid": invalid,
        })
