"""Bounded notes about unfinished business in the current story.

Working state is a handoff between turns: the current focus, the situation it
belongs to, tentative assumptions, open loops and next steps. It is not a
memory store and not a world-state copy, so every field is deliberately small
and the whole note has a hard character budget.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

DEFAULT_MAX_CHARS = 1000
MIN_MAX_CHARS = 400
MAX_MAX_CHARS = 2000

FOCUS_MAX_CHARS = 200
ITEM_MAX_CHARS = 120
MAX_SITUATION_ITEMS = 3
MAX_ASSUMPTION_ITEMS = 3
MAX_OPEN_LOOPS = 3
MAX_NEXT_STEPS = 2

_LIST_FIELDS = (
    ("situation", MAX_SITUATION_ITEMS),
    ("assumptions", MAX_ASSUMPTION_ITEMS),
    ("open_loops", MAX_OPEN_LOOPS),
    ("next_steps", MAX_NEXT_STEPS),
)
_FIELD_ORDER = ("focus",) + tuple(name for name, _limit in _LIST_FIELDS)
# Least valuable parts are dropped first when the note exceeds its budget.
_DROP_ORDER = ("assumptions", "situation", "next_steps", "open_loops")


def _clean_text(value: Any, limit: int) -> str:
    if value is None or isinstance(value, (dict, list, tuple, set)):
        return ""
    text = " ".join(str(value).split())
    if len(text) > limit:
        text = text[:limit].rstrip()
    return text


def _clean_items(value: Any, *, limit_count: int) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_items: List[Any] = [value]
    elif isinstance(value, (list, tuple)):
        raw_items = list(value)
    else:
        return []

    items: List[str] = []
    for raw in raw_items:
        text = _clean_text(raw, ITEM_MAX_CHARS)
        if not text:
            continue
        items.append(text)
        if len(items) >= limit_count:
            break
    return items


def normalize_working_state_update(
    update: Any,
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> Optional[Dict[str, Any]]:
    """Return a bounded state dict, or ``None`` when nothing usable is left."""
    if hasattr(update, "model_dump"):
        update = update.model_dump(exclude_none=True)
    if isinstance(update, Mapping):
        data: Mapping[str, Any] = update
    elif isinstance(update, str):
        data = {"focus": update}
    else:
        return None

    state: Dict[str, Any] = {}
    focus = _clean_text(data.get("focus"), FOCUS_MAX_CHARS)
    if focus:
        state["focus"] = focus
    for name, limit in _LIST_FIELDS:
        items = _clean_items(data.get(name), limit_count=limit)
        if items:
            state[name] = items

    if not state:
        return None

    budget = max(MIN_MAX_CHARS, min(MAX_MAX_CHARS, int(max_chars or DEFAULT_MAX_CHARS)))
    for name in _DROP_ORDER:
        if content_length(state) <= budget:
            break
        state.pop(name, None)
    if content_length(state) > budget:
        room = budget - content_length({**state, "focus": ""})
        state["focus"] = str(state.get("focus") or "")[:max(0, room)].rstrip()
    if not any(state.values()):
        return None
    return state


def content_length(state: Mapping[str, Any]) -> int:
    total = len(str(state.get("focus") or ""))
    for name, _limit in _LIST_FIELDS:
        items = state.get(name) or []
        if isinstance(items, list):
            total += sum(len(str(item)) for item in items)
            total += max(0, len(items) - 1) * 2
    return total


def render_prompt_block(
    state: Mapping[str, Any],
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> Optional[str]:
    normalized = normalize_working_state_update(state, max_chars=max_chars)
    return render_normalized_prompt_block(normalized) if normalized else None


def render_normalized_prompt_block(state: Mapping[str, Any]) -> Optional[str]:
    """Render an already bounded state without compressing it again."""
    if not isinstance(state, Mapping) or not state:
        return None

    lines = [
        "[WORKING STATE]",
        "Temporary interpretation from the previous completed turn. This is not "
        "established fact; history, current observations and game state take precedence.",
    ]
    labels = {
        "focus": "Focus",
        "situation": "Current understanding",
        "assumptions": "Tentative assumptions",
        "open_loops": "Open loops",
        "next_steps": "Immediate next steps",
    }
    for name in _FIELD_ORDER:
        value = state.get(name)
        if isinstance(value, str) and value:
            lines.append(f"{labels[name]}: {value}")
        elif isinstance(value, list) and value:
            lines.append(f"{labels[name]}:")
            lines.extend(f"- {item}" for item in value)
    lines.append("[/WORKING STATE]")
    return "\n".join(lines)
