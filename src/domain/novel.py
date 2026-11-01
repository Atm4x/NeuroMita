from __future__ import annotations

import math
import re

ROOMS = frozenset({"corridor", "hall", "kitchen", "bedroom"})
POSES = frozenset({"neutral", "happy", "sad", "angry", "surprised", "ring"})


def known_id(value, choices):
    return isinstance(value, str) and value in choices


TRANSFORM_LIMITS = {"x": (-0.35, 0.35), "y": (-0.2, 0.2), "scale": (0.6, 1.5), "duration": (0.0, 3.0)}


def sanitize_transform(payload):
    if not isinstance(payload, dict) or not any(key in payload for key in ("x", "y", "scale")):
        return None
    try:
        return {key: _bounded(payload, key, low, high, 0)
                for key, (low, high) in TRANSFORM_LIMITS.items() if key in payload}
    except ValueError:
        return None



def _bounded(payload, key, low, high, default):
    value = payload.get(key, default)
    if type(value) not in (int, float):
        raise ValueError("Expected number")
    try:
        if not math.isfinite(value):
            raise ValueError("Nonfinite number")
    except OverflowError as exc:
        raise ValueError("Number too large") from exc
    return max(low, min(high, value))


def sanitize_tint(payload):
    if not isinstance(payload, dict) or not any(key in payload for key in ("color", "opacity")):
        return None
    result = {}
    if "color" in payload:
        color = payload["color"]
        if not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            return None
        result["color"] = color.upper()
    try:
        if "opacity" in payload:
            result["opacity"] = _bounded(payload, "opacity", 0.15, 1, 1)
        if "duration" in payload:
            result["duration"] = _bounded(payload, "duration", 0, 3, 0.35)
    except ValueError:
        return None
    return result


def sanitize_visual(intent_type, payload):
    if not isinstance(payload, dict):
        return None
    shake = intent_type == "novel.shake"
    result = {}
    if not shake:
        if not known_id(payload.get("effect"), ("flash", "pulse", "tilt", "reset")):
            return None
        result["effect"] = payload["effect"]
    try:
        result["strength"] = _bounded(payload, "strength", 0, 0.03 if shake else 1, 0.012 if shake else 0.5)
        result["duration"] = _bounded(payload, "duration", 0, 2, 0.5)
    except ValueError:
        return None
    return result


def validate_novel(value):
    if not isinstance(value, dict) or type(value.get("version")) is not int or value["version"] != 1:
        raise ValueError("Unsupported 2D novel protocol")
    session = value.get("session")
    if not isinstance(session, str) or not 1 <= len(session) <= 128:
        raise ValueError("Missing novel session")
    if not known_id(value.get("player_room"), ROOMS) or not known_id(value.get("mita_room"), ROOMS):
        raise ValueError("Unknown novel room")
    if not known_id(value.get("pose"), POSES):
        raise ValueError("Unknown novel pose")
    result = {key: value[key] for key in ("version", "session", "player_room", "mita_room", "pose")}
    if "transform" in value:
        transform = sanitize_transform(value["transform"])
        if transform is None or not all(key in transform for key in ("x", "y", "scale")):
            raise ValueError("Invalid novel transform")
        result["transform"] = {key: transform[key] for key in ("x", "y", "scale")}
    if "appearance" in value:
        appearance = sanitize_tint(value["appearance"])
        if appearance is None or not all(key in appearance for key in ("color", "opacity")):
            raise ValueError("Invalid novel appearance")
        result["appearance"] = {key: appearance[key] for key in ("color", "opacity")}
    return result


def sanitize_response(structured):
    from schemas.structured_response import ResponseSegment, StructuredResponse

    segments = []
    for segment in structured.segments[:24]:
        intents = []
        for intent in segment.intents:
            if intent.type == "novel.pose" and known_id(intent.payload.get("pose"), POSES):
                intents.append({"type": intent.type, "payload": {"pose": intent.payload["pose"]}})
            elif intent.type == "novel.move" and known_id(intent.payload.get("room"), ROOMS):
                intents.append({"type": intent.type, "payload": {"room": intent.payload["room"]}})
            elif intent.type == "novel.transform":
                transform = sanitize_transform(intent.payload)
                if transform is not None:
                    intents.append({"type": intent.type, "payload": transform})
            elif intent.type == "novel.tint":
                tint = sanitize_tint(intent.payload)
                if tint is not None:
                    intents.append({"type": intent.type, "payload": tint})
            elif intent.type in ("novel.shake", "novel.effect"):
                visual = sanitize_visual(intent.type, intent.payload)
                if visual is not None:
                    intents.append({"type": intent.type, "payload": visual})
        segments.append(ResponseSegment(text=segment.text[:4000], emotions=[e for e in segment.emotions if e in POSES], intents=intents))
    return StructuredResponse(segments=segments)
