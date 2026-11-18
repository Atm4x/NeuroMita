"""Render retrieved evidence separately from retrieval diagnostics."""
from __future__ import annotations

import datetime as dt

from managers.lore_timeline import _parse_history_timestamp, read_world_anchor


def result_dates(db, character_id, results, settings, lore_dates, *, now=None):
    now = now or dt.datetime.now().astimezone()
    mode = settings.get("RAG_CONTEXT_DATE_MODE", "relative")
    seconds = bool(settings.get("RAG_CONTEXT_SECONDS_TODAY", True))
    seeds = [r["id"] for r in results if r.get("type") == "seed_lore"]
    events = {}
    if seeds:
        with db.connection() as conn:
            cur = conn.cursor()
            anchor = read_world_anchor(cur)
            cols = {r[1] for r in cur.execute("PRAGMA table_info(memories)")}
            if anchor and "lore_age_days" in cols:
                for identity, days in cur.execute(
                    "SELECT eternal_id,lore_age_days FROM memories WHERE character_id=? "
                    f"AND eternal_id IN ({','.join('?' for _ in seeds)})", (character_id, *seeds),
                ):
                    if days is not None:
                        events[identity] = anchor - dt.timedelta(days=days)
    dates = {}
    for row in results:
        key = row["source"], row["id"]
        seed = row.get("type") == "seed_lore"
        stamp = events.get(row["id"]) if seed else _parse_history_timestamp(row.get("date_created") or row.get("date"))
        if seed and mode != "absolute":
            dates[key] = lore_dates.get(row["id"], "event time unknown")
            continue
        if stamp is None:
            dates[key] = "event time unknown" if seed else "time unknown"
            continue
        stamp = stamp.astimezone(now.tzinfo)
        today = stamp.date() == now.date()
        if mode == "relative":
            delta = (now - stamp).total_seconds()
            if delta < 0:
                value = "in the future"
            elif today and delta < 60 and seconds:
                value = f"{int(delta)} seconds ago"
            elif delta < 3600:
                value = f"{max(1, int(delta / 60))} minutes ago"
            elif delta < 86400:
                value = f"{int(delta / 3600)} hours ago"
            else:
                value = f"{int(delta / 86400)} days ago"
        else:
            value = stamp.strftime("%Y-%m-%d" if seed else
                                   ("%Y-%m-%d %H:%M:%S" if today and seconds else "%Y-%m-%d %H:%M"))
        dates[key] = ("approx. " if seed else "") + value
    return dates


def render_evidence(results, dates, settings):
    scores = bool(settings.get("RAG_CONTEXT_SHOW_SCORES", True))
    grouped = bool(settings.get("RAG_CONTEXT_GROUP_RETAINED", True))
    clip = max(1, int(settings.get("RAG_CLIP_MAX_CHARS", 700)))
    parts = ["[Retrieved evidence]\nUse these records as sources, not as current events. "
             "Retrieval relevance is not factual certainty. Preserve the recorded speaker and source. "
             "A past player is not the current player unless explicitly established. "
             "A proposal or a quoted claim is not proof that an event occurred. "
             "seed_lore records are read-only; never update, delete or merge them."]
    for retained in (False, True) if grouped else (None,):
        rows = [r for r in results if retained is None or bool(r.get("retained")) == retained]
        if not rows:
            continue
        if retained:
            parts.append("[Earlier retrieval retained for this conversation]\nThese records were retrieved on an earlier turn; they are not new events.")
        for source, tag, title in (("memory", "relevant_memories", "Memory records"),
                                   ("history", "retrieved_dialogue", "Retrieved dialogue excerpts"),
                                   ("graph", "entity_knowledge", "Recorded relationships")):
            lines = []
            for row in rows:
                if row["source"] != source:
                    continue
                score = f"[relevance={float(row.get('score', 0)):.3f}] " if scores else ""
                identity = {"memory": "N", "history": "H", "graph": "G"}[source]
                meta = f"{identity}:{row['id']}"
                if source == "memory":
                    meta += f" ({row.get('type', 'fact')}, date={dates.get((source, row['id']), 'time unknown')})"
                elif source == "history":
                    meta += f" (date={dates.get((source, row['id']), 'time unknown')}; "
                    meta += f"speaker={row.get('speaker') or 'unknown'}; target={row.get('target') or 'unspecified'})"
                else:
                    meta += f" (date={dates.get((source, row['id']), 'time unknown')})"
                text = str(row.get("content") or "").strip()
                text = text[:clip] + ("…" if len(text) > clip else "")
                text = f'Quote: {text}' if source == "history" else text
                status = " [earlier retrieval]" if row.get("retained") and not grouped else ""
                lines.append(f"{score}{meta}{status} {text}")
            if lines:
                note = "\nQuoted past dialogue; not independent evidence of the described events." if source == "history" else ""
                parts.append(f"<{tag}>\n{title}{note}\n" + "\n".join(lines) + f"\n</{tag}>")
    return "\n\n".join(parts) if len(parts) > 1 else ""
