import re
from enum import StrEnum


ROLEPLAY_MODE_SETTING = "ROLEPLAY_MODE"


class RoleplayMode(StrEnum):
    OFF = "off"
    SUBTLE = "subtle"
    EXPRESSIVE = "expressive"
    FULL = "full"

    @classmethod
    def from_setting(cls, value: object) -> "RoleplayMode":
        try:
            return cls(str(value or "").strip().lower())
        except ValueError:
            return cls.OFF


_ACTION_BEAT = re.compile(r"(?<![\\*])\*(?=[^\s*])[^*\r\n]+(?<!\s)\*(?!\*)")


def roleplay_spoken_text(text: str) -> str:
    return _ACTION_BEAT.sub(" ", text).strip()
