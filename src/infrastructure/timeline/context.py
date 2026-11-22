from __future__ import annotations

from contextlib import closing

from services.timeline_context import ContextSummary


class SQLiteContextSummaries:
    def __init__(self, connection_factory):
        self._factory = connection_factory
        with closing(self._factory()) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS timeline_context_summaries (
                branch_id TEXT NOT NULL, character_id TEXT NOT NULL,
                through_sequence INTEGER NOT NULL, digest TEXT NOT NULL, summary TEXT NOT NULL,
                source_head INTEGER NOT NULL,
                PRIMARY KEY(branch_id, character_id))""")
            columns = {row[1] for row in conn.execute("PRAGMA table_info(timeline_context_summaries)")}
            if "source_head" not in columns:
                conn.execute("ALTER TABLE timeline_context_summaries ADD COLUMN source_head INTEGER NOT NULL DEFAULT 0")
            conn.commit()

    def load(self, branch_id: str, character_id: str) -> ContextSummary | None:
        with closing(self._factory()) as conn:
            row = conn.execute("""SELECT through_sequence, digest, summary, source_head
                FROM timeline_context_summaries WHERE branch_id=? AND character_id=?""",
                (branch_id, character_id)).fetchone()
            return ContextSummary(*row) if row else None

    def save(self, branch_id: str, character_id: str, summary: ContextSummary) -> None:
        with closing(self._factory()) as conn:
            conn.execute("""INSERT INTO timeline_context_summaries VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(branch_id, character_id) DO UPDATE SET
                through_sequence=excluded.through_sequence, digest=excluded.digest, summary=excluded.summary,
                source_head=excluded.source_head""",
                (branch_id, character_id, summary.through, summary.digest, summary.text, summary.source_head))
            conn.commit()
