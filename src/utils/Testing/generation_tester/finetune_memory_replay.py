"""Replay only ordinary memory_add proposals on a disposable copy of a SQLite snapshot.

A saved response is not a transaction log: updates/deletes/merges, islands
and eviction are excluded. Output contains counts only.
"""
from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
import tempfile
from collections import Counter
from contextlib import closing
from datetime import datetime
from pathlib import Path

SRC = Path(__file__).resolve().parents[3]
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from characters.character import Character
from managers.database_manager import DatabaseManager
from managers.memory_manager import MemoryManager
from schemas.structured_response import StructuredResponse
from utils.structured_response_parser import StructuredResponseParseError, parse_structured_response_with_meta


class ReplayCharacter(Character):
    def __init__(self, character_id):
        self.char_id = character_id
        self._memory = MemoryManager(character_id)
        self._memory.rag = None
        self._memory._schedule_embed = lambda *_: None
        self._memory._dedup_enabled = lambda: True
        self._memory._maintenance_enabled = lambda: True
        self._memory._forget_over_limit_memories = lambda: None
        self._write = self._memory.add_memory
        self._memory.add_memory = self._add

    @property
    def memory_system(self):
        return self._memory

    def _add(self, *, priority, content, entities):
        eid = self._write(content, date=self._date, priority=priority, entities=entities)
        self.applied += eid is not None
        return eid

    def apply_additions(self, date, operations):
        self._date = date
        self.applied = 0
        self._apply_structured_memory_ops(StructuredResponse(
            segments=[{"text": "Replay."}], memory_add=operations,
        ))
        return self.applied


def rows(database):
    with database.connection() as conn:
        return {(cid, eid): (content, date, deleted, forgotten)
                for cid, eid, content, date, deleted, forgotten in conn.execute(
                    "SELECT character_id, eternal_id, content, date_created, is_deleted, is_forgotten FROM memories"
                )}


def replay_additions(path, database):
    before = rows(database)
    counts = Counter()
    characters = {}
    with path.open(encoding="utf-8-sig") as source:
        for line in source:
            if not line.strip():
                continue
            try:
                sample = json.loads(line)
                character_id = sample.get("character_id") if isinstance(sample, dict) else None
                if not isinstance(character_id, str) or not character_id or character_id == "unknown":
                    continue
                response = parse_structured_response_with_meta(sample.get("response", "")).response
                operations = [op for op in response.memory_add or [] if not op.strip().startswith("island:")]
                if not operations:
                    continue
                date = datetime.fromisoformat(sample["timestamp"]).strftime("%d.%m.%Y %H:%M:%S")
            except (ValueError, KeyError, TypeError, StructuredResponseParseError):
                counts["skipped_invalid_records"] += 1
                continue
            if character_id not in characters:
                characters[character_id] = ReplayCharacter(character_id)
            counts["ordinary_additions_proposed"] += len(operations)
            counts["ordinary_additions_applied"] += characters[character_id].apply_additions(date, operations)

    after_adds = rows(database)
    counts["existing_content_changes_after_adds"] = sum(row[0] != after_adds[key][0] for key, row in before.items())
    counts["existing_date_changes_after_adds"] = sum(row[1] != after_adds[key][1] for key, row in before.items())
    counts["maintenance_merges"] = sum(char.memory_system.run_maintenance()["merged"]
                                      for char in characters.values())
    after = rows(database)
    counts["preexisting_soft_deletes_from_maintenance"] = sum(not row[2] and after[key][2]
                                                           for key, row in before.items())
    counts["active_new_rows_after_maintenance"] = sum(key not in before and not row[2] and not row[3]
                                                     for key, row in after.items())
    return dict(counts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("samples", type=Path)
    parser.add_argument("--snapshot", type=Path, required=True)
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)

    with tempfile.TemporaryDirectory(prefix="nm_memory_replay_") as folder:
        path = Path(folder) / "world.db"
        # The sqlite connection context commits but does not close these handles.
        with closing(sqlite3.connect(args.snapshot.resolve().as_uri() + "?mode=ro", uri=True)) as original:
            with closing(sqlite3.connect(path)) as copy:
                original.backup(copy)
        DatabaseManager._path_override = str(path)
        print(json.dumps(replay_additions(args.samples, DatabaseManager()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
