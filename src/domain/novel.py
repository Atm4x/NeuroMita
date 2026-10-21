from __future__ import annotations

ROOMS = frozenset({"corridor", "hall", "kitchen", "bedroom"})
POSES = frozenset({"neutral", "happy", "sad", "angry", "surprised", "ring"})


def known_id(value, choices):
    return isinstance(value, str) and value in choices


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
    return {key: value[key] for key in ("version", "session", "player_room", "mita_room", "pose")}


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
        segments.append(ResponseSegment(text=segment.text[:4000], emotions=[e for e in segment.emotions if e in POSES], intents=intents))
    return StructuredResponse(segments=segments)
