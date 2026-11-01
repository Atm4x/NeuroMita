from __future__ import annotations

import math
from typing import Any

APPEARANCES = ("full_body", "portrait")
ACTIVITIES = ("idle", "walking", "sitting", "dragged")


def _number(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return 0.0
    return number if math.isfinite(number) else 0.0


def _text(value: Any, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _edge(anchor_x: float, anchor_y: float) -> str:
    if anchor_x <= 0.25:
        return "left"
    if anchor_x >= 0.75:
        return "right"
    if anchor_y >= 0.9:
        return "bottom"
    if anchor_y <= 0.15:
        return "top"
    return "middle"


def normalize_desktop_context(value: Any) -> dict:
    """Сжатое desktop-состояние, которое Unity присылает из режима -desktop."""
    if not isinstance(value, dict):
        return {}
    if not any(value.get(key) is not None for key in value):
        return {}
    anchor_x = min(1.0, max(0.0, _number(value.get("anchor_x"))))
    anchor_y = min(1.0, max(0.0, _number(value.get("anchor_y"))))
    appearance = _text(value.get("appearance"), 24).lower()
    activity = _text(value.get("activity"), 24).lower()
    return {
        "mode": "desktop",
        "appearance": appearance if appearance in APPEARANCES else "full_body",
        "activity": activity if activity in ACTIVITIES else "idle",
        "seated_on": _text(value.get("seated_on"), 80),
        "edge": _edge(anchor_x, anchor_y),
        "anchor_x": round(anchor_x, 3),
        "anchor_y": round(anchor_y, 3),
        "screen_width": int(max(0, _number(value.get("screen_width")))),
        "screen_height": int(max(0, _number(value.get("screen_height")))),
        "watching_screen": bool(value.get("watching_screen")),
        "cursor_follow": bool(value.get("cursor_follow", True)),
        "last_event": _text(value.get("last_event"), 300),
    }


_ACTIVITY_TEXT = {
    "idle": "You are standing still and idle right now.",
    "walking": "You are walking across the screen right now.",
    "dragged": "The player is dragging you around the screen right now.",
}


def format_desktop_context(value: Any) -> str:
    desktop = normalize_desktop_context(value)
    if not desktop:
        return ""
    frame = (
        "your full body"
        if desktop["appearance"] == "full_body"
        else "your face and shoulders in a close portrait frame"
    )
    lines = [
        "[Desktop mode] You live on the player's Windows desktop; the MiSide house is not around you.",
        f"Your window shows {frame} and stays on top of the other windows.",
    ]
    if desktop["screen_width"] and desktop["screen_height"]:
        place = {
            "left": "near the left edge",
            "right": "near the right edge",
            "top": "near the top edge",
            "bottom": "above the bottom edge",
            "middle": "in the middle",
        }[desktop["edge"]]
        lines.append(
            f"Your window sits {place} of the primary display ({desktop['screen_width']}x{desktop['screen_height']} pixels in total)."
        )
    if desktop["activity"] == "sitting":
        seat = desktop["seated_on"] or "the edge of the screen"
        lines.append(f"You are sitting on {seat} right now.")
    else:
        lines.append(_ACTIVITY_TEXT[desktop["activity"]])
    lines.append(
        "Screen watching: "
        + ("on" if desktop["watching_screen"] else "off")
        + ". Cursor following: "
        + ("on" if desktop["cursor_follow"] else "off")
        + "."
    )
    if desktop["last_event"]:
        lines.append(f"Last desktop event: {desktop['last_event']}")
    lines.append(
        "The attached frames show the player's desktop as it looks right now; your own window is excluded from them."
    )
    lines.append(
        "You cannot open doors, walk into rooms or handle in-game objects here; "
        "react to what is actually visible on the screen and to what the player says."
    )
    return "\n".join(lines) + "\n[/Desktop mode]"


def desktop_context_part(value: Any) -> dict:
    desktop = normalize_desktop_context(value)
    return {"type": "text", "text": format_desktop_context(desktop), "desktop_context": desktop}


def is_desktop_context_only(message: dict) -> bool:
    """Пришел только desktop-контекст: это наблюдение, а не реплика персонажа."""
    desktop = normalize_desktop_context(message.get("desktop_context"))
    if not desktop:
        return False
    content = message.get("content")
    parts = content if isinstance(content, list) else [{"type": "text", "text": str(content or "")}]
    block = format_desktop_context(desktop)
    for part in parts:
        if isinstance(part, dict) and part.get("type") == "text":
            if str(part.get("text") or "").replace(block, "").strip():
                return False
    return True
