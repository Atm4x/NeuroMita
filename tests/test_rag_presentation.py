import datetime as dt
import sqlite3
from types import SimpleNamespace

from services.rag_presentation import render_evidence, result_dates


NOW = dt.datetime(2026, 11, 16, 12, 0, 30, tzinfo=dt.timezone.utc)


def database():
    conn = sqlite3.connect(":memory:")
    conn.executescript("CREATE TABLE memories(character_id,eternal_id,lore_age_days);"
                       "CREATE TABLE variables(character_id,key,value);")
    conn.execute("INSERT INTO variables VALUES('_system','lore_world_anchor_utc_v1',?)", (NOW.isoformat(),))
    conn.execute("INSERT INTO memories VALUES('A',1,7)")
    conn.commit()
    return conn, SimpleNamespace(connection=lambda: conn)


def records():
    return [dict(source="memory", id=1, type="seed_lore", content="At the Core.", score=0.8,
                 date_created="2026-11-16 12:00:00"),
            dict(source="history", id=2, speaker="Mila", target="A", content="I read the logs.",
                 date="2026-11-15T10:20:59+00:00", score=0.7, retained=True),
            dict(source="memory", id=3, type="fact", content="A new promise.",
                 date_created="2026-11-16T12:00:15+00:00", score=0.6, retained=True)]


def test_date_modes_use_event_time_for_lore_and_seconds_only_today():
    conn, db = database()
    try:
        items = records()
        relative = result_dates(db, "A", items, SimpleNamespace(get={}.get), {1: "около 7 дней назад"}, now=NOW)
        assert relative[("memory", 1)] == "около 7 дней назад"
        assert relative[("memory", 3)] == "15 seconds ago"
        mixed = result_dates(db, "A", items, SimpleNamespace(get={"RAG_CONTEXT_DATE_MODE": "mixed"}.get),
                             {1: "около 7 дней назад"}, now=NOW)
        assert mixed[("history", 2)] == "2026-11-15 10:20"
        assert mixed[("memory", 3)] == "2026-11-16 12:00:15"
        absolute = result_dates(db, "A", items, SimpleNamespace(get={"RAG_CONTEXT_DATE_MODE": "absolute"}.get),
                                {}, now=NOW)
        assert absolute[("memory", 1)] == "approx. 2026-11-09"
        conn.execute("UPDATE memories SET lore_age_days=NULL")
        unknown = result_dates(db, "A", items, SimpleNamespace(get={"RAG_CONTEXT_DATE_MODE": "absolute"}.get),
                               {}, now=NOW)
        assert unknown[("memory", 1)] == "event time unknown"
    finally:
        conn.close()


def test_grouped_retention_keeps_ids_dates_and_speaker_without_repeated_diagnostics():
    dates = {("memory", 1): "a week ago", ("memory", 3): "today", ("history", 2): "yesterday"}
    text = render_evidence(records(), dates, SimpleNamespace(get={"RAG_CONTEXT_SHOW_SCORES": False}.get))
    assert text.count("Earlier retrieval retained") == 1
    assert "turns remaining" not in text
    assert "N:1" in text and "H:2" in text and "N:3" in text
    assert "date=yesterday; speaker=Mila; target=A" in text
    assert "<retrieved_dialogue>" in text and "<past_context>" not in text
    assert "relevance=" not in text
    assert text.count("I read the logs.") == 1


def test_empty_sources_are_omitted_and_scores_can_be_shown():
    text = render_evidence(records()[:1], {}, SimpleNamespace(get={}.get))
    assert "relevance=0.800" in text
    assert "<retrieved_dialogue>" not in text
    assert "Earlier retrieval" not in text
