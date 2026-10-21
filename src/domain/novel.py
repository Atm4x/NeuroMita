from __future__ import annotations

import math

ROOMS = frozenset({"corridor", "hall", "kitchen", "bedroom"})
POSES = frozenset({"neutral", "happy", "sad", "angry", "surprised", "ring"})


def known_id(value, choices):
    return isinstance(value, str) and value in choices


TRANSFORM_LIMITS = {"x": (-0.35, 0.35), "y": (-0.2, 0.2), "scale": (0.6, 1.5), "duration": (0.0, 3.0)}


def sanitize_transform(payload):
    if not isinstance(payload, dict) or not any(key in payload for key in ("x", "y", "scale")):
        return None
    result = {}
    for key, (low, high) in TRANSFORM_LIMITS.items():
        if key not in payload:
            continue
        value = payload[key]
        if type(value) not in (int, float):
            return None
        try:
            if not math.isfinite(value):
                return None
        except OverflowError:
            return None
        result[key] = max(low, min(high, value))
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
        segments.append(ResponseSegment(text=segment.text[:4000], emotions=[e for e in segment.emotions if e in POSES], intents=intents))
    return StructuredResponse(segments=segments)
