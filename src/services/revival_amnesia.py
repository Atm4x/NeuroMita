"""Non-destructive revival amnesia contract carried by Unity runtime_events.

The control marker is emitted per CharacterType only when Unity has exactly one
eligible MitaActor for that type. Never mutate stored history, memories, or RAG.
"""
from __future__ import annotations

import re
from typing import Any

_MARKER = re.compile(r"NM_AMNESIA_V1\|mode=(none|recent|identity)\|actor=([A-Za-z0-9_-]{1,128})\Z", re.ASCII)
_RECENT_TURNS = 8


def is_amnesia_marker(value: Any) -> bool:
    return bool(_MARKER.fullmatch(str(value or "").strip()))


def get_revival_amnesia_mode(game_state: Any) -> str:
    """Resolve only the newest exact Unity marker. Absent -> completely off."""
    if not isinstance(game_state, dict):
        return "none"
    events = game_state.get("runtime_events") or ()
    if not isinstance(events, (tuple, list)):
        events = [events]
    result = "none"
    for raw in events:
        match = _MARKER.fullmatch(str(raw or "").strip())
        if match:
            result = match.group(1)
    return result


def visible_history(messages: list, mode: str) -> list:
    """Returns a new prompt-only list; the persisted list is left untouched."""
    if mode == "identity":
        return []
    if mode == "recent":
        return list(messages[:-_RECENT_TURNS])
    return list(messages)


def amnesia_prompt_message(mode: str) -> dict[str, str] | None:
    if mode == "recent":
        instruction = (
            "You have just been revived with a temporary gap in your recent memory. "
            "The last several dialogue exchanges are not accessible to you. "
            "Older memories and your identity remain. Do not pretend to remember "
            "the missing interval unless you learn it again in the current dialogue."
        )
    elif mode == "identity":
        instruction = (
            "You have just been revived with a severe autobiographical memory gap. "
            "Your previous chats, personal memories, relationship with the player and "
            "the player's identity are not accessible to you. You may learn them again "
            "from new experiences. Do not invent details of missing relationships."
        )
    else:
        return None
    return {"role": "system", "content": "[Revival Amnesia]\n" + instruction + "\n[/Revival Amnesia]"}
