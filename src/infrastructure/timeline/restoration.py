from __future__ import annotations

from contextlib import closing

from domain.timeline import JsonDocument, TimelineConflict
from domain.timeline.restoration import PendingRestore


class SQLiteRestorationJournal:
    def __init__(self, connection_factory):
        self._factory = connection_factory
        with closing(self._factory()) as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS timeline_pending_restores (
                operation_id TEXT PRIMARY KEY, workspace TEXT NOT NULL UNIQUE,
                source_branch_id TEXT NOT NULL, target_branch_id TEXT NOT NULL,
                before_snapshot TEXT NOT NULL, desired_snapshot TEXT NOT NULL)""")
            connection.commit()

    def pending(self, workspace: str) -> PendingRestore | None:
        with closing(self._factory()) as connection:
            row = connection.execute("SELECT * FROM timeline_pending_restores WHERE workspace=?", (workspace,)).fetchone()
            return PendingRestore(*row[:4], JsonDocument.parse(row[4]), JsonDocument.parse(row[5])) if row else None

    def begin(self, operation: PendingRestore):
        with closing(self._factory()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            values = (operation.operation_id, operation.workspace, operation.source_branch_id,
                      operation.target_branch_id, operation.before.canonical, operation.desired.canonical)
            existing = connection.execute("SELECT * FROM timeline_pending_restores WHERE workspace=?", (operation.workspace,)).fetchone()
            if existing is not None:
                if tuple(existing) != values:
                    raise TimelineConflict("A different restore already owns the workspace journal")
            else:
                connection.execute("INSERT INTO timeline_pending_restores VALUES (?, ?, ?, ?, ?, ?)", values)
            connection.commit()

    def complete(self, operation_id: str):
        with closing(self._factory()) as connection:
            connection.execute("DELETE FROM timeline_pending_restores WHERE operation_id=?", (operation_id,))
            connection.commit()
