from __future__ import annotations

from contextlib import closing
import json

from domain.timeline import TimelineConflict


class SQLiteUnitySessions:
    def __init__(self, connection_factory):
        self._factory = connection_factory
        with closing(self._factory()) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS timeline_unity_operations (
                    operation_id TEXT PRIMARY KEY, workspace TEXT NOT NULL,
                    pending INTEGER NOT NULL, document TEXT NOT NULL);
                CREATE UNIQUE INDEX IF NOT EXISTS timeline_unity_one_pending
                    ON timeline_unity_operations(workspace) WHERE pending=1;
                CREATE TABLE IF NOT EXISTS timeline_unity_checkpoints (
                    checkpoint_id TEXT PRIMARY KEY, branch_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL, document TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS timeline_unity_names (
                    identity TEXT PRIMARY KEY, name TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS timeline_unity_legacy (
                    save_id TEXT PRIMARY KEY, branch_id TEXT NOT NULL UNIQUE);
            """)
            conn.commit()

    def operation(self, operation_id):
        with closing(self._factory()) as conn:
            row = conn.execute("SELECT document FROM timeline_unity_operations WHERE operation_id=?",
                               (operation_id,)).fetchone()
            return json.loads(row[0]) if row else None

    def pending(self, workspace):
        with closing(self._factory()) as conn:
            row = conn.execute("SELECT document FROM timeline_unity_operations WHERE workspace=? AND pending=1",
                               (workspace,)).fetchone()
            return json.loads(row[0]) if row else None

    def put_operation(self, operation):
        pending = operation["state"] not in {"complete", "aborted"}
        with closing(self._factory()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            other = conn.execute("SELECT operation_id FROM timeline_unity_operations WHERE workspace=? AND pending=1",
                                 (operation["workspace"],)).fetchone()
            if other and other[0] != operation["operation_id"]:
                raise TimelineConflict("Another Unity transition requires recovery")
            conn.execute("INSERT INTO timeline_unity_operations VALUES (?, ?, ?, ?) ON CONFLICT(operation_id) "
                         "DO UPDATE SET pending=excluded.pending, document=excluded.document",
                         (operation["operation_id"], operation["workspace"], int(pending),
                          json.dumps(operation, sort_keys=True)))
            conn.commit()

    def put_checkpoint(self, checkpoint):
        document = json.dumps(checkpoint, sort_keys=True)
        with closing(self._factory()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT document FROM timeline_unity_checkpoints WHERE checkpoint_id=?",
                               (checkpoint["checkpoint_id"],)).fetchone()
            if row and row[0] != document:
                raise TimelineConflict("Checkpoint already binds another Unity snapshot")
            conn.execute("INSERT OR IGNORE INTO timeline_unity_checkpoints VALUES (?, ?, ?, ?)",
                         (checkpoint["checkpoint_id"], checkpoint["branch_id"], checkpoint["sequence"], document))
            conn.commit()

    def checkpoints(self, branch_id):
        with closing(self._factory()) as conn:
            return [json.loads(row[0]) for row in conn.execute(
                "SELECT document FROM timeline_unity_checkpoints WHERE branch_id=? ORDER BY sequence DESC",
                (branch_id,))]

    def names(self):
        with closing(self._factory()) as conn:
            return dict(conn.execute("SELECT identity, name FROM timeline_unity_names"))

    def rename(self, identity, name):
        with closing(self._factory()) as conn:
            conn.execute("INSERT INTO timeline_unity_names VALUES (?, ?) ON CONFLICT(identity) DO UPDATE SET name=excluded.name",
                         (identity, name))
            conn.commit()

    def bind_legacy(self, save_id, branch_id):
        with closing(self._factory()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT branch_id FROM timeline_unity_legacy WHERE save_id=?", (save_id,)).fetchone()
            if row and row[0] != branch_id:
                raise TimelineConflict("Legacy save is already bound to another timeline")
            conn.execute("INSERT OR IGNORE INTO timeline_unity_legacy VALUES (?, ?)", (save_id, branch_id))
            conn.commit()

    def legacy_branch(self, save_id):
        with closing(self._factory()) as conn:
            row = conn.execute("SELECT branch_id FROM timeline_unity_legacy WHERE save_id=?", (save_id,)).fetchone()
            return row[0] if row else None
