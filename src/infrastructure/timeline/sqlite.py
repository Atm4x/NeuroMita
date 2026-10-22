from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator, Sequence

from domain.timeline import (
    Branch, CausalLink, CausalRelation, ConcurrentTimelineWrite, EventDraft,
    EventKind, InvalidTimelineOperation, JsonDocument, TimelineConflict,
    TimelineEvent, TimelineNotFound,
)
from domain.timeline.models import require_id
from domain.timeline.models import AppendReceipt, TimelineSelection
from domain.timeline.rules import HISTORY_KINDS, validate_event
from domain.timeline.archive import OperationArchive, SessionArchive, draft_from_event, validate_archive
from domain.timeline.assets import TimelineAsset, asset_references
from .assets import ASSET_SCHEMA, SQLiteTimelineAssets
from .schema import LINEAGE, SCHEMA, SCHEMA_VERSION


class SQLiteTimelineRepository:
    """Serialized atomic appends with branch-local optimistic concurrency.

    Every call owns its connection. A supplied factory may share a database
    file with other application repositories, but never a live transaction.
    """

    def __init__(
        self, path: str | Path | None = None, *,
        connection_factory: Callable[[], sqlite3.Connection] | None = None,
    ):
        if (path is None) == (connection_factory is None):
            raise ValueError("Provide either a path or a connection factory")
        if path is not None:
            if str(path) == ":memory:":
                raise ValueError("Use a file or a shared-memory connection factory")
            db_path = Path(path).resolve()
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self._factory = lambda: sqlite3.connect(db_path, timeout=10)
        else:
            self._factory = connection_factory
        with self._connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript("BEGIN IMMEDIATE;\n" + SCHEMA)
            conn.execute(ASSET_SCHEMA)
            versions = conn.execute("SELECT version FROM timeline_schema").fetchall()
            if not versions:
                conn.execute("INSERT INTO timeline_schema VALUES (?)", (SCHEMA_VERSION,))
            elif len(versions) != 1 or versions[0][0] != SCHEMA_VERSION:
                raise InvalidTimelineOperation("Unsupported timeline schema version")
            conn.commit()

    @contextmanager
    def _connection(self, *, write: bool = False) -> Iterator[sqlite3.Connection]:
        conn = self._factory()
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=10000")
            if write:
                conn.execute("BEGIN IMMEDIATE")
            yield conn
            if write:
                conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _branch(conn: sqlite3.Connection, branch_id: str) -> Branch:
        row = conn.execute(
            "SELECT * FROM timeline_branches WHERE branch_id=?", (branch_id,),
        ).fetchone()
        if row is None:
            raise TimelineNotFound(f"Unknown branch: {branch_id}")
        return Branch(**dict(row))

    def create_session(self, session_id: str, branch_id: str) -> Branch:
        require_id(session_id, "session_id")
        require_id(branch_id, "branch_id")
        with self._connection(write=True) as conn:
            existing = conn.execute(
                "SELECT root_branch_id FROM timeline_sessions WHERE session_id=?", (session_id,),
            ).fetchone()
            if existing:
                if existing[0] != branch_id:
                    raise TimelineConflict("Session already has a different root branch")
                return self._branch(conn, branch_id)
            try:
                conn.execute("INSERT INTO timeline_sessions VALUES (?, ?)", (session_id, branch_id))
                conn.execute(
                    "INSERT INTO timeline_branches VALUES (?, ?, NULL, 0, 0, NULL)",
                    (branch_id, session_id),
                )
            except sqlite3.IntegrityError as exc:
                raise TimelineConflict("Branch identity already exists") from exc
            return self._branch(conn, branch_id)

    def get_branch(self, branch_id: str) -> Branch:
        with self._connection() as conn:
            return self._branch(conn, branch_id)

    @staticmethod
    def _selection(conn: sqlite3.Connection, workspace: str) -> TimelineSelection | None:
        row = conn.execute("SELECT branch_id, generation FROM timeline_workspace WHERE workspace=?",
                           (workspace,)).fetchone()
        return TimelineSelection(*row) if row else None

    def selection(self, workspace: str) -> TimelineSelection | None:
        with self._connection() as conn:
            return self._selection(conn, workspace)

    def select(
        self, workspace: str, branch_id: str, *, expected: TimelineSelection | None,
    ) -> TimelineSelection:
        require_id(workspace, "workspace")
        with self._connection(write=True) as conn:
            self._branch(conn, branch_id)
            current = self._selection(conn, workspace)
            if current != expected:
                raise ConcurrentTimelineWrite("Active session selection changed")
            selection = TimelineSelection(branch_id, current.generation + 1 if current else 1)
            conn.execute("""INSERT INTO timeline_workspace VALUES (?, ?, ?)
                ON CONFLICT(workspace) DO UPDATE SET branch_id=excluded.branch_id,
                    generation=excluded.generation""", (workspace, branch_id, selection.generation))
            return selection

    @staticmethod
    def _decode(conn: sqlite3.Connection, rows: Sequence[sqlite3.Row]) -> tuple[TimelineEvent, ...]:
        if not rows:
            return ()
        observers: dict[str, set[str]] = {row["event_id"]: set() for row in rows}
        links: dict[str, list[CausalLink]] = {row["event_id"]: [] for row in rows}
        ids = tuple(observers)
        for start in range(0, len(ids), 400):
            batch = ids[start:start + 400]
            placeholders = ",".join("?" for _ in batch)
            for row in conn.execute(
                f"SELECT * FROM timeline_observers WHERE event_id IN ({placeholders})", batch,
            ):
                observers[row["event_id"]].add(row["character_id"])
            for row in conn.execute(
                f"SELECT * FROM timeline_links WHERE event_id IN ({placeholders}) "
                "ORDER BY relation, target_id", batch,
            ):
                links[row["event_id"]].append(CausalLink(CausalRelation(row["relation"]), row["target_id"]))
        return tuple(TimelineEvent(
            event_id=row["event_id"], session_id=row["session_id"], branch_id=row["branch_id"],
            sequence=row["sequence"], kind=EventKind(row["kind"]),
            payload=JsonDocument.parse(row["payload"]), actor_id=row["actor_id"],
            observers=frozenset(observers[row["event_id"]]), links=tuple(links[row["event_id"]]),
            occurred_at=row["occurred_at"], schema_version=row["schema_version"],
        ) for row in rows)

    @staticmethod
    def _scope(branch_id: str, ceiling: int) -> dict:
        return {"branch_id": branch_id, "ceiling": ceiling}

    def _event(
        self, conn: sqlite3.Connection, branch_id: str, event_id: str, ceiling: int,
    ) -> TimelineEvent:
        rows = conn.execute(LINEAGE + """
            SELECT e.* FROM lineage l JOIN timeline_events e ON e.branch_id=l.branch_id
            WHERE e.sequence<=l.ceiling AND e.event_id=:event_id
        """, {**self._scope(branch_id, ceiling), "event_id": event_id}).fetchall()
        if not rows:
            raise TimelineNotFound(f"Event is outside branch history: {event_id}")
        return self._decode(conn, rows)[0]

    def get_event(self, branch_id: str, event_id: str) -> TimelineEvent:
        with self._connection() as conn:
            conn.execute("BEGIN")
            branch = self._branch(conn, branch_id)
            return self._event(conn, branch_id, event_id, branch.head_sequence)

    def find_message(self, branch_id: str, message_id: str) -> TimelineEvent:
        require_id(message_id, "message_id")
        with self._connection() as conn:
            conn.execute("BEGIN")
            branch = self._branch(conn, branch_id)
            rows = conn.execute(LINEAGE + """
                SELECT e.* FROM lineage l
                JOIN timeline_events e ON e.branch_id=l.branch_id AND e.sequence<=l.ceiling
                JOIN timeline_message_keys k ON k.event_id=e.event_id
                WHERE k.message_id=:message_id ORDER BY e.sequence DESC LIMIT 1
            """, {**self._scope(branch_id, branch.head_sequence), "message_id": message_id}).fetchall()
            if not rows:
                raise TimelineNotFound(f"Unknown message on this branch: {message_id}")
            return self._decode(conn, rows)[0]

    def _knows(
        self, conn: sqlite3.Connection, branch: Branch, character_id: str, event_id: str,
    ) -> bool:
        target = self._event(conn, branch.branch_id, event_id, branch.head_sequence)
        reset = self._context_epoch(conn, branch.branch_id, character_id, branch.head_sequence)
        if character_id in target.observers and target.sequence >= reset:
            return True
        row = conn.execute(LINEAGE + """
            SELECT 1 FROM timeline_links link INDEXED BY timeline_links_target
            CROSS JOIN timeline_events e
            CROSS JOIN lineage l
            CROSS JOIN timeline_observers o
            WHERE link.target_id=:target AND link.relation=:relation
                AND e.event_id=link.event_id AND e.kind=:kind AND e.sequence>:reset
                AND e.branch_id=l.branch_id AND e.sequence<=l.ceiling
                AND o.event_id=e.event_id AND o.character_id=:character LIMIT 1
        """, {**self._scope(branch.branch_id, branch.head_sequence),
              "kind": EventKind.EVENT_OBSERVED.value, "relation": CausalRelation.OBSERVES.value,
              "target": event_id, "character": character_id, "reset": reset}).fetchone()
        return row is not None

    def knows(self, branch_id: str, character_id: str, event_id: str, *, through: int | None = None) -> bool:
        require_id(character_id, "character_id")
        with self._connection() as conn:
            conn.execute("BEGIN")
            branch = self._branch(conn, branch_id)
            if through is not None:
                branch = Branch(branch.branch_id, branch.session_id, branch.parent_branch_id,
                                branch.fork_sequence, min(through, branch.head_sequence), branch.checkpoint_id)
            try:
                return self._knows(conn, branch, character_id, event_id)
            except TimelineNotFound:
                return False

    def context_epoch(self, branch_id: str, character_id: str, *, through: int | None = None) -> int:
        require_id(character_id, "character_id")
        with self._connection() as conn:
            branch = self._branch(conn, branch_id)
            ceiling = branch.head_sequence if through is None else min(through, branch.head_sequence)
            return self._context_epoch(conn, branch_id, character_id, ceiling)

    def presentation_epoch(self, branch_id: str, character_id: str, *, through: int | None = None) -> int:
        with self._connection() as conn:
            branch = self._branch(conn, branch_id)
            ceiling = branch.head_sequence if through is None else min(through, branch.head_sequence)
            return conn.execute(LINEAGE + """
                SELECT COALESCE(MAX(e.sequence), 0) FROM lineage l
                CROSS JOIN timeline_events e INDEXED BY timeline_events_kind
                CROSS JOIN timeline_observers o
                WHERE e.branch_id=l.branch_id AND e.sequence<=l.ceiling
                    AND e.kind IN (:reset, :hidden, :revised, :restored)
                    AND o.event_id=e.event_id AND o.character_id=:character
            """, {**self._scope(branch_id, ceiling), "character": character_id,
                  "reset": EventKind.CONTEXT_RESET.value, "hidden": EventKind.MESSAGE_HIDDEN.value,
                  "revised": EventKind.MESSAGE_REVISED.value, "restored": EventKind.MESSAGE_RESTORED.value}).fetchone()[0]

    @classmethod
    def _context_epoch(cls, conn, branch_id: str, character_id: str, ceiling: int) -> int:
        return conn.execute(LINEAGE + """
            SELECT COALESCE(MAX(e.sequence), 0) FROM lineage l
            CROSS JOIN timeline_events e INDEXED BY timeline_events_kind
            CROSS JOIN timeline_observers o
            WHERE e.branch_id=l.branch_id AND e.sequence<=l.ceiling AND e.kind=:kind
                AND o.event_id=e.event_id AND o.character_id=:character
        """, {**cls._scope(branch_id, ceiling), "kind": EventKind.CONTEXT_RESET.value,
              "character": character_id}).fetchone()[0]

    def present(self, branch_id: str, *, through: int | None = None) -> frozenset[str]:
        with self._connection() as conn:
            branch = self._branch(conn, branch_id)
            ceiling = branch.head_sequence if through is None else min(through, branch.head_sequence)
            rows = conn.execute(LINEAGE + """, presence AS (
                SELECT e.actor_id, e.kind,
                    ROW_NUMBER() OVER (PARTITION BY e.actor_id ORDER BY e.sequence DESC) AS position
                FROM lineage l JOIN timeline_events e ON e.branch_id=l.branch_id AND e.sequence<=l.ceiling
                WHERE e.kind IN (:joined, :left)
            ) SELECT actor_id FROM presence WHERE position=1 AND kind=:joined
            """, {**self._scope(branch_id, ceiling), "joined": EventKind.CHARACTER_JOINED.value,
                  "left": EventKind.CHARACTER_LEFT.value}).fetchall()
            return frozenset(row[0] for row in rows)

    @staticmethod
    def _insert(conn: sqlite3.Connection, branch: Branch, draft: EventDraft, sequence: int) -> None:
        message_id = draft.payload.to_dict().get("message_id") if draft.kind in HISTORY_KINDS else None
        if message_id:
            require_id(message_id, "message_id")
            duplicate = conn.execute(LINEAGE + """
                SELECT 1 FROM timeline_message_keys k INDEXED BY timeline_message_keys_lookup
                CROSS JOIN timeline_events e CROSS JOIN lineage l
                WHERE k.message_id=:message_id AND e.event_id=k.event_id
                    AND e.branch_id=l.branch_id AND e.sequence<=l.ceiling LIMIT 1
            """, {"branch_id": branch.branch_id, "ceiling": sequence - 1, "message_id": message_id}).fetchone()
            if duplicate:
                raise TimelineConflict("An external message identity already names a retained fact")
        conn.execute("INSERT INTO timeline_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (
            draft.event_id, branch.session_id, branch.branch_id, sequence, draft.kind.value,
            draft.actor_id, draft.payload.canonical, draft.occurred_at, draft.schema_version,
        ))
        conn.executemany("INSERT INTO timeline_observers VALUES (?, ?)", (
            (draft.event_id, character_id) for character_id in sorted(draft.observers)
        ))
        conn.executemany("INSERT INTO timeline_links VALUES (?, ?, ?)", (
            (draft.event_id, link.relation.value, link.event_id) for link in draft.links
        ))
        if message_id:
            conn.execute("INSERT INTO timeline_message_keys VALUES (?, ?)", (draft.event_id, message_id))

    def append(
        self, branch_id: str, events: Sequence[EventDraft], *,
        expected_head: int, idempotency_key: str,
        command: JsonDocument | None = None,
    ) -> tuple[TimelineEvent, ...]:
        require_id(idempotency_key, "idempotency_key")
        drafts = tuple(events)
        if type(expected_head) is not int or expected_head < 0:
            raise InvalidTimelineOperation("expected_head must be a non-negative sequence")
        intent = JsonDocument({"events": [draft.intent() for draft in drafts],
                               "command": (command or JsonDocument()).to_dict()}).canonical
        with self._connection(write=True) as conn:
            branch = self._branch(conn, branch_id)
            retry = conn.execute(
                "SELECT intent, event_ids FROM timeline_operations WHERE branch_id=? AND idempotency_key=?",
                (branch_id, idempotency_key),
            ).fetchone()
            if retry:
                if retry["intent"] != intent:
                    raise TimelineConflict("Idempotency key was reused for a different append")
                return tuple(self._event(conn, branch_id, event_id, branch.head_sequence)
                             for event_id in json.loads(retry["event_ids"]))
            if expected_head != branch.head_sequence:
                raise ConcurrentTimelineWrite(f"Expected head {expected_head}, found {branch.head_sequence}")
            try:
                for offset, draft in enumerate(drafts, 1):
                    prefix_head = branch.head_sequence + offset - 1
                    prefix = Branch(branch.branch_id, branch.session_id, branch.parent_branch_id,
                                    branch.fork_sequence, prefix_head, branch.checkpoint_id)
                    validate_event(
                        draft, lambda event_id: self._event(conn, branch_id, event_id, prefix_head),
                        lambda character, event_id: self._knows(conn, prefix, character, event_id),
                    )
                    for reference in asset_references(draft.payload.to_dict()).values():
                        asset = conn.execute("SELECT media_type, byte_size FROM timeline_assets WHERE asset_id=?",
                                             (reference["asset_id"],)).fetchone()
                        if asset is None or tuple(asset) != (reference["media_type"], reference["byte_size"]):
                            raise InvalidTimelineOperation("An event references unavailable attachment content")
                    self._insert(conn, branch, draft, prefix_head + 1)
                    conn.execute("UPDATE timeline_branches SET head_sequence=? WHERE branch_id=?",
                                 (prefix_head + 1, branch_id))
                ids = [draft.event_id for draft in drafts]
                conn.execute("INSERT INTO timeline_operations VALUES (?, ?, ?, ?)",
                             (branch_id, idempotency_key, intent, json.dumps(ids)))
            except sqlite3.IntegrityError as exc:
                raise TimelineConflict("Event identity already exists") from exc
            rows = conn.execute("""SELECT * FROM timeline_events
                WHERE branch_id=? AND sequence>? AND sequence<=? ORDER BY sequence""",
                (branch_id, branch.head_sequence, branch.head_sequence + len(drafts))).fetchall()
            return self._decode(conn, rows)

    def receipt(self, branch_id: str, key: str) -> AppendReceipt | None:
        with self._connection() as conn:
            conn.execute("BEGIN")
            branch = self._branch(conn, branch_id)
            row = conn.execute("SELECT intent, event_ids FROM timeline_operations WHERE branch_id=? AND idempotency_key=?",
                               (branch_id, key)).fetchone()
            if row is None:
                return None
            command = JsonDocument.parse(row["intent"]).to_dict().get("command", {})
            events = tuple(self._event(conn, branch_id, event_id, branch.head_sequence)
                           for event_id in json.loads(row["event_ids"]))
            return AppendReceipt(JsonDocument(command), events)

    def read(
        self, branch_id: str, *, after: int = 0, through: int | None = None,
        limit: int = 500, observer: str | None = None,
    ) -> tuple[TimelineEvent, ...]:
        if type(after) is not int or after < 0 or type(limit) is not int or not 1 <= limit <= 10000:
            raise InvalidTimelineOperation("Invalid timeline page bounds")
        if through is not None and (type(through) is not int or through < 0):
            raise InvalidTimelineOperation("Invalid timeline upper bound")
        if observer is not None:
            require_id(observer, "observer")
        with self._connection() as conn:
            conn.execute("BEGIN")
            branch = self._branch(conn, branch_id)
            ceiling = branch.head_sequence if through is None else min(through, branch.head_sequence)
            rows = conn.execute(LINEAGE + """
                SELECT e.* FROM lineage l JOIN timeline_events e ON e.branch_id=l.branch_id
                WHERE e.sequence<=l.ceiling AND e.sequence>:after
                    AND (:observer IS NULL OR EXISTS (
                        SELECT 1 FROM timeline_observers o
                        WHERE o.event_id=e.event_id AND o.character_id=:observer))
                ORDER BY e.sequence LIMIT :limit
            """, {**self._scope(branch_id, ceiling), "after": after, "observer": observer, "limit": limit}).fetchall()
            return self._decode(conn, rows)

    def fork(self, branch_id: str, checkpoint_id: str, new_branch_id: str) -> Branch:
        require_id(new_branch_id, "new_branch_id")
        with self._connection(write=True) as conn:
            parent = self._branch(conn, branch_id)
            checkpoint = self._event(conn, branch_id, checkpoint_id, parent.head_sequence)
            if checkpoint.kind is not EventKind.CHECKPOINT:
                raise InvalidTimelineOperation("A branch must fork from a checkpoint")
            existing = conn.execute("SELECT * FROM timeline_branches WHERE branch_id=?", (new_branch_id,)).fetchone()
            if existing:
                branch = Branch(**dict(existing))
                if branch.parent_branch_id != branch_id or branch.checkpoint_id != checkpoint_id:
                    raise TimelineConflict("Branch identity was reused for a different fork")
                return branch
            branch = Branch(new_branch_id, parent.session_id, branch_id,
                            checkpoint.sequence, checkpoint.sequence + 1, checkpoint_id)
            conn.execute("INSERT INTO timeline_branches VALUES (?, ?, ?, ?, ?, ?)", (
                branch.branch_id, branch.session_id, branch.parent_branch_id,
                branch.fork_sequence, branch.head_sequence, branch.checkpoint_id,
            ))
            marker = EventDraft(
                kind=EventKind.BRANCH_CREATED, payload=JsonDocument({"checkpoint_id": checkpoint_id}),
                links=(CausalLink(CausalRelation.CAUSED_BY, checkpoint_id),),
            )
            self._insert(conn, branch, marker, branch.head_sequence)
            return branch

    def export_session(self, session_id: str) -> SessionArchive:
        with self._connection() as conn:
            conn.execute("BEGIN")
            row = conn.execute("SELECT root_branch_id FROM timeline_sessions WHERE session_id=?",
                               (session_id,)).fetchone()
            if row is None:
                raise TimelineNotFound(f"Unknown session: {session_id}")
            branches = tuple(Branch(**dict(branch)) for branch in conn.execute(
                "SELECT * FROM timeline_branches WHERE session_id=? ORDER BY branch_id", (session_id,),
            ))
            rows = conn.execute("SELECT * FROM timeline_events WHERE session_id=? ORDER BY branch_id, sequence",
                                (session_id,)).fetchall()
            events = self._decode(conn, rows)
            operations = tuple(OperationArchive(
                operation["branch_id"], operation["idempotency_key"], JsonDocument.parse(operation["intent"]),
                tuple(json.loads(operation["event_ids"])),
            ) for operation in conn.execute("""SELECT op.* FROM timeline_operations op
                JOIN timeline_branches b ON b.branch_id=op.branch_id WHERE b.session_id=?
                ORDER BY op.branch_id, op.idempotency_key""", (session_id,)))
            references = {}
            for event in events:
                references.update(asset_references(event.payload.to_dict()))
            assets = []
            for asset_id in sorted(references):
                asset_row = conn.execute("SELECT media_type, content FROM timeline_assets WHERE asset_id=?", (asset_id,)).fetchone()
                if asset_row is None:
                    raise InvalidTimelineOperation("Session export is missing an attachment")
                asset = TimelineAsset(asset_id, asset_row[0], bytes(asset_row[1]))
                asset.validate()
                assets.append(asset)
            return SessionArchive(session_id, row[0], branches, events, operations, tuple(assets))

    def import_session(self, archive: SessionArchive) -> Branch:
        ordered = validate_archive(archive)
        local = {branch.branch_id: [] for branch in ordered}
        for event in archive.events:
            local[event.branch_id].append(event)
        with self._connection(write=True) as conn:
            try:
                conn.execute("INSERT INTO timeline_sessions VALUES (?, ?)", (archive.session_id, archive.root_branch_id))
                for asset in archive.assets:
                    SQLiteTimelineAssets.insert(conn, asset)
                for branch in ordered:
                    conn.execute("INSERT INTO timeline_branches VALUES (?, ?, ?, ?, ?, ?)", (
                        branch.branch_id, branch.session_id, branch.parent_branch_id,
                        branch.fork_sequence, branch.head_sequence, branch.checkpoint_id,
                    ))
                    for event in sorted(local[branch.branch_id], key=lambda item: item.sequence):
                        self._insert(conn, branch, draft_from_event(event), event.sequence)
                for operation in archive.operations:
                    conn.execute("INSERT INTO timeline_operations VALUES (?, ?, ?, ?)", (
                        operation.branch_id, operation.key, operation.intent.canonical,
                        json.dumps(operation.event_ids),
                    ))
            except sqlite3.IntegrityError as exc:
                raise TimelineConflict("Session import collides with retained identities") from exc
            return self._branch(conn, archive.root_branch_id)
