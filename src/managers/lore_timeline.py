"""Stable, shared relative chronology for SEED_RAG_MEMORY world events.

AGE_BEFORE_START is intentionally *metadata*, not part of memory.content.
Imported lore never receives a normal RAG recency bonus.
"""
from __future__ import annotations

import datetime as dt
import re
from typing import Any, Iterable

_ANCHOR_OWNER = "_system"
_ANCHOR_KEY = "lore_world_anchor_utc_v1"
_AGE_SUFFIX = re.compile(
    r"\s+AGE_BEFORE_START\s+(\d{1,4})(mo|d|w|y)\s*$", re.IGNORECASE
)
_UNIT_DAYS = {"d": 1, "w": 7, "mo": 30, "y": 365}


def strip_age_before_start(raw_args: str) -> tuple[str, int | None]:
    """Parse the optional DSL suffix: AGE_BEFORE_START 6mo (before ENTITIES).

    Months and years are approximate on purpose. Invalid annotations fail
    loudly rather than leaking syntax into the Mita's personal memory.
    """
    match = _AGE_SUFFIX.search(raw_args)
    if match is None:
        if re.search(r"\bAGE_BEFORE_START\b", raw_args, re.IGNORECASE):
            raise ValueError("AGE_BEFORE_START expects a positive value such as 10d, 6mo, 2y")
        return raw_args, None
    number = int(match.group(1))
    days = number * _UNIT_DAYS[match.group(2).lower()]
    if number <= 0 or days > 36500:
        raise ValueError("AGE_BEFORE_START must be between 1 day and 100 years")
    return raw_args[:match.start()].rstrip(), days


def _utc(value: dt.datetime | None) -> dt.datetime:
    value = value or dt.datetime.now(dt.timezone.utc)
    # Existing history without an offset was written in machine-local time.
    return value.astimezone(dt.timezone.utc)


def _parse_history_timestamp(value: Any) -> dt.datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return _utc(dt.datetime.fromisoformat(raw.replace("Z", "+00:00")))
    except ValueError:
        pass
    for pattern in ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M"):
        try:
            return _utc(dt.datetime.strptime(raw, pattern))
        except ValueError:
            pass
    return None


def read_world_anchor(cursor) -> dt.datetime | None:
    try:
        row = cursor.execute(
            "SELECT value FROM variables WHERE character_id=? AND key=?",
            (_ANCHOR_OWNER, _ANCHOR_KEY),
        ).fetchone()
    except Exception:
        return None
    return _parse_history_timestamp(row[0]) if row else None


def ensure_world_anchor(cursor, *, now: dt.datetime | None = None) -> dt.datetime:
    """Persist the anchor once per world.db; not once per character or query.

    Migration of existing installations uses the earliest recorded dialogue
    as a *proxy* for first launch. Clean DBs use current time at DB setup.
    An already stored anchor is never recomputed, even if history is cleared.
    """
    current = _utc(now)
    saved = read_world_anchor(cursor)
    if saved:
        return saved

    earliest = None
    try:
        # Old and migrated history formats coexist; read a small distinct set
        # of oldest timestamps rather than modifying the existing records.
        rows = cursor.execute(
            "SELECT timestamp FROM history WHERE timestamp IS NOT NULL "
            "AND TRIM(timestamp) <> '' AND role IN ('user','assistant') "
            "ORDER BY timestamp ASC LIMIT 32"
        ).fetchall()
        parsed = [_parse_history_timestamp(row[0]) for row in rows]
        plausible = [v for v in parsed if v is not None and v <= current]
        earliest = min(plausible) if plausible else None
    except Exception:
        pass

    proposed = min(current, earliest) if earliest else current
    cursor.execute(
        "INSERT OR IGNORE INTO variables(character_id, key, value) VALUES (?, ?, ?)",
        (_ANCHOR_OWNER, _ANCHOR_KEY, proposed.isoformat(timespec="seconds")),
    )
    return read_world_anchor(cursor) or proposed


def describe_event_age(days_before_start: int, *, anchor: dt.datetime, now: dt.datetime | None = None) -> str:
    """Human-readable approximate time. No real calendar dates reach the LLM."""
    elapsed_days = max(0.0, (_utc(now) - _utc(anchor)).total_seconds() / 86400.0)
    days = max(0, int(days_before_start + elapsed_days + 0.5))
    if days < 2:
        return "совсем недавно"
    if days < 21:
        return f"около {days} дней назад"
    if days < 50:
        count = max(1, round(days / 7))
        return "около недели назад" if count == 1 else f"около {count} недель назад"
    if days < 540:
        months = max(1, round(days / 30))
        return "около месяца назад" if months == 1 else f"около {months} месяцев назад"
    if days < 650:
        return "около полутора лет назад"
    years = max(2, round(days / 365))
    return f"около {years} лет назад"


def lore_dates_for_results(
    db: Any, character_id: str, results: Iterable[dict],
    *, now: dt.datetime | None = None,
) -> dict[int, str]:
    """Look up relative dates only for retrieved seed_lore IDs.

    All Mitas in this world.db share the same anchor, but their memories may
    represent different perspectives and times of *learning* about an event.
    Return an empty mapping on old schemas so callers can show 'unknown'.
    """
    ids = set()
    for item in results:
        if not isinstance(item, dict):
            continue
        if item.get("source") != "memory" or str(item.get("type") or "").lower() != "seed_lore":
            continue
        try:
            mid = int(item.get("id") or 0)
            if mid > 0:
                ids.add(mid)
        except (TypeError, ValueError):
            continue
    if not ids:
        return {}

    with db.connection() as conn:
        cursor = conn.cursor()
        cols = {row[1] for row in cursor.execute("PRAGMA table_info(memories)")}
        if "lore_age_days" not in cols:
            return {}
        anchor = read_world_anchor(cursor)
        if anchor is None:
            # A DB without the migration still must never display date_created.
            return {}
        placeholders = ", ".join("?" for _ in ids)
        rows = cursor.execute(
            f"SELECT eternal_id, lore_age_days FROM memories "
            f"WHERE character_id=? AND type='seed_lore' AND is_deleted=0 "
            f"AND eternal_id IN ({placeholders})",
            (character_id, *sorted(ids)),
        ).fetchall()
    return {
        int(mid): describe_event_age(int(days), anchor=anchor, now=now)
        for mid, days in rows if days is not None and int(days) >= 0
    }
