from uuid import uuid4, uuid5


_SESSION_NAMESPACE = uuid4()


def session_id(character_id: str = "", character_name: str = "") -> str:
    """Keep Go routing stable per character during this application run."""
    return str(uuid5(_SESSION_NAMESPACE, character_id or character_name or "default"))
