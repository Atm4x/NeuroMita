"""Deterministic, model-facing projection of structured requested actions."""
from __future__ import annotations

import json
from typing import Any, Callable, Iterable, Mapping

from core.message_content import MessageContentCodec
from domain.action_refs import action_ref
from managers.action_receipt_ledger import short_label


_SEGMENT_ACTION_FIELDS = (
    ("emotions", "emotion"),
    ("animations", "animation"),
    ("idle_animations", "idle_animation"),
    ("commands", "command"),
    ("movement_modes", "movement_mode"),
    ("visual_effects", "visual_effect"),
    ("clothes", "outfit"),
    ("music", "music"),
    ("interactions", "interaction"),
    ("face_params", "face_param"),
)


def _normalize_legacy_clothing_command(text: str) -> tuple[bool, str]:
    lowered = text.lower()
    if lowered.startswith("clothes:"):
        selection = text.split(":", 1)[1].strip()
        outfit, separator, variant = selection.partition(",")
        outfit = " ".join(outfit.split())
        variant = " ".join(variant.split())
        if not outfit:
            return True, ""
        record = f"outfit: {outfit}"
        if separator and variant:
            record += f", {variant}"
        return True, record

    if not lowered.startswith("clothescolor"):
        return False, ""

    parts = [part.strip() for part in text.split(",")]
    if len(parts) == 2 and parts[1].lower() == "reset":
        return True, "appearance recolor: reset"
    if len(parts) != 5:
        return True, ""

    part = " ".join(parts[1].split())
    try:
        rgb = tuple(int(channel) for channel in parts[2:])
    except (TypeError, ValueError):
        return True, ""
    if not part or any(channel < 0 or channel > 255 for channel in rgb):
        return True, ""
    return True, f"appearance recolor: {part} rgb({rgb[0]},{rgb[1]},{rgb[2]})"


def _iter_segment_actions(structured_data: Any) -> Iterable[tuple[int, str, int, str]]:
    """Yield ``(segment, field, index, text)`` for every requested action."""
    if not isinstance(structured_data, dict):
        return
    for segment_index, segment in enumerate(structured_data.get("segments") or []):
        if not isinstance(segment, dict):
            continue
        for field, label in _SEGMENT_ACTION_FIELDS:
            values = segment.get(field) or []
            if not isinstance(values, list):
                values = [values]
            for item_index, value in enumerate(values):
                text = " ".join(str(value or "").split()).strip()
                if not text:
                    continue
                if label == "command":
                    is_clothing_command, normalized = _normalize_legacy_clothing_command(text)
                    if is_clothing_command:
                        if normalized:
                            yield segment_index, field, item_index, normalized
                        continue
                yield segment_index, field, item_index, f"{label}: {text}"
        for field, label in (("start_game", "start_game"), ("end_game", "end_game")):
            value = " ".join(str(segment.get(field) or "").split()).strip()
            if value:
                yield segment_index, field, 0, f"{label}: {value}"
        for intent_index, intent in enumerate(segment.get("intents") or []):
            if not isinstance(intent, dict):
                continue
            intent_type = " ".join(str(intent.get("type") or "").split()).strip()
            if not intent_type:
                continue
            payload = intent.get("payload")
            try:
                payload_text = json.dumps(
                    payload or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                )
            except (TypeError, ValueError):
                payload_text = "{}"
            yield segment_index, "intents", intent_index, f"intent: {intent_type} {payload_text}"


def requested_action_records(structured_data: Any, *, turn_uid: str = "") -> list[dict]:
    """Return action records with their stable refs for receipt matching."""
    turn = str(turn_uid or "").strip()
    records: list[dict] = []
    for segment_index, field, item_index, text in _iter_segment_actions(structured_data):
        records.append({
            "text": text,
            "ref": action_ref(turn, segment_index, field, item_index) if turn else "",
            "turn_uid": turn,
            "segment": segment_index,
            "field": field,
            "index": item_index,
        })
    return records


def requested_actions_from_structured(structured_data: Any) -> list[str]:
    """Return stable, compact action records from persisted ``structured_data``.

    The records intentionally say *requested*: Python sees the model command,
    but does not know whether Unity resolved or executed it.
    """
    return [record["text"] for record in requested_action_records(structured_data)]


def requested_action_records_from_messages(messages: list[dict[str, Any]]) -> list[dict]:
    records: list[dict] = []
    for message in messages or []:
        if isinstance(message, dict) and message.get("role") == "assistant":
            records.extend(requested_action_records(
                message.get("structured_data"),
                turn_uid=str(message.get("task_uid") or ""),
            ))
    return records


def requested_actions_from_messages(messages: list[dict[str, Any]]) -> list[str]:
    return [record["text"] for record in requested_action_records_from_messages(messages)]


def _resolve_status(ref: str, receipts: Mapping | Callable | None) -> str:
    if not ref or receipts is None:
        return ""
    if callable(receipts):
        value = receipts(ref)
        return str(value or "")
    return str(receipts.get(ref) or "")


def _format_record(record: Any, receipts: Mapping | Callable | None = None) -> str:
    if isinstance(record, dict):
        text = str(record.get("text") or "").strip()
        status = _resolve_status(str(record.get("ref") or ""), receipts)
    else:
        text = str(record or "").strip()
        status = ""
    if status:
        text += f" [{short_label(status)}]"
    return text


def render_requested_actions(
    records: Iterable[Any],
    receipts: Mapping | Callable | None = None,
) -> str:
    clean = [_format_record(record, receipts) for record in records or []]
    clean = [record for record in clean if record]
    if not clean:
        return ""
    return (
        "[RECENT ACTIONS BEFORE SUMMARY BOUNDARY]\n"
        "Structured action requests from earlier assistant turns now absorbed by the history summary, "
        "in chronological order (oldest to newest). A status in square brackets is what the game "
        "runtime reported; actions without one were only requested. Later requests can supersede "
        "earlier ones.\n"
        + "\n".join(f"- {record}" for record in clean)
        + "\n[/RECENT ACTIONS BEFORE SUMMARY BOUNDARY]"
    )


def append_requested_actions(
    content: Any,
    records: Iterable[Any],
    receipts: Mapping | Callable | None = None,
) -> Any:
    """Project one assistant turn's structured actions into its LLM-facing text.

    This is deliberately a prompt-only projection: the persisted message keeps
    its original content and ``structured_data`` remains the source of truth.
    """
    clean = [_format_record(record, receipts) for record in records or []]
    clean = [record for record in clean if record]
    if not clean:
        return content
    block = (
        "[REQUESTED ACTIONS THIS TURN]\n"
        "Requested structured actions for this reply. A status in square brackets is what "
        "the game runtime reported; without one the action was requested but not confirmed.\n"
        + "\n".join(f"- {record}" for record in clean)
        + "\n[/REQUESTED ACTIONS THIS TURN]"
    )
    separator = "\n\n" if MessageContentCodec.has_visible_content(content) else ""
    return MessageContentCodec.append_text(content, separator + block)


def cap_requested_actions(
    records: Iterable[Any],
    *,
    max_records: int,
    max_chars: int,
) -> tuple[list[Any], bool]:
    """Emergency-only cap that preserves the newest chronological suffix.

    Normal retention is intentionally controlled by history summarization. This
    guard only prevents unlimited prompt growth when compression is disabled or
    unable to commit for a long time.
    """
    items = list(records or [])
    max_records = max(1, int(max_records or 1))
    max_chars = max(200, int(max_chars or 200))
    capped = len(items) > max_records
    if capped:
        items = items[-max_records:]

    selected: list[Any] = []
    used_chars = 0
    for record in reversed(items):
        record_chars = len(_format_record(record)) + 3  # bullet and newline in rendered form
        if used_chars + record_chars <= max_chars:
            selected.append(record)
            used_chars += record_chars
            continue

        capped = True
        if not selected:
            suffix = "\u2026 [truncated]"
            text = _format_record(record)
            selected.append(text[: max(1, max_chars - len(suffix))].rstrip() + suffix)
        break

    selected.reverse()
    return selected, capped
