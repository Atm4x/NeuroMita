from __future__ import annotations

from datetime import datetime, timezone


def message_timestamp(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        value = datetime.fromisoformat(str(raw))
    except ValueError:
        try:
            value = datetime.strptime(str(raw), "%d.%m.%Y %H:%M:%S")
        except ValueError:
            return None
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds")


def display_timestamp(raw: str) -> str:
    return datetime.fromisoformat(raw).astimezone().strftime("%Y-%m-%d %H:%M:%S")
