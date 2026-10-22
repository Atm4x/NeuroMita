from __future__ import annotations

from contextlib import closing, nullcontext
import json
import math

from domain.timeline import InvalidTimelineOperation, JsonDocument


class SQLiteCharacterState:
    """Snapshot semantic character records; embeddings and physical row IDs are derived."""

    key = "character_store"
    version = 1
    _MEMORY_FIELDS = frozenset({"eternal_id", "content", "priority", "type", "date_created", "is_deleted",
                               "is_forgotten", "tags", "participants", "entities", "access_count", "last_accessed"})
    _ENTITY_FIELDS = frozenset({"name", "entity_type", "mention_count", "first_seen", "last_seen", "is_protected", "access_count"})
    _RELATION_FIELDS = frozenset({"predicate", "confidence", "created_at", "is_protected", "subject", "object"})

    def __init__(self, connection_factory, character_ids, live_variables=lambda _identity: None):
        self._factory = connection_factory
        self._character_ids = character_ids
        self._live_variables = live_variables

    def paused(self):
        return nullcontext()

    @staticmethod
    def _tables(connection):
        return {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}

    @staticmethod
    def _rows(connection, sql, arguments=()):
        cursor = connection.execute(sql, arguments)
        fields = [column[0] for column in cursor.description]
        return [dict(zip(fields, row)) for row in cursor.fetchall()]

    @staticmethod
    def _variable(value):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return value

    @staticmethod
    def _fields(record, *, text=(), counts=(), flags=()):
        for key in text:
            if record.get(key) is not None and not isinstance(record[key], str):
                raise InvalidTimelineOperation(f"Invalid snapshot text field: {key}")
        for key in counts:
            if record.get(key) is not None and (type(record[key]) is not int or record[key] < 0):
                raise InvalidTimelineOperation(f"Invalid snapshot counter: {key}")
        for key in flags:
            if record.get(key) is not None and (type(record[key]) is not int or record[key] not in {0, 1}):
                raise InvalidTimelineOperation(f"Invalid snapshot flag: {key}")

    def capture(self) -> JsonDocument:
        characters = {}
        with closing(self._factory()) as connection:
            connection.execute("BEGIN")
            tables = self._tables(connection)
            for identity in sorted(self._character_ids()):
                variables = {key: self._variable(value) for key, value in connection.execute(
                    "SELECT key, value FROM variables WHERE character_id=?", (identity,))}
                live = self._live_variables(identity)
                if live is not None:
                    variables = dict(live)
                memories = [{key: value for key, value in row.items() if key in self._MEMORY_FIELDS}
                            for row in self._rows(connection, "SELECT * FROM memories WHERE character_id=? ORDER BY eternal_id, id", (identity,))]
                graph = {"entities": [], "relations": [], "aliases": []}
                if "graph_entities" in tables:
                    entities = self._rows(connection, "SELECT * FROM graph_entities WHERE character_id=? ORDER BY id", (identity,))
                    names = {row["id"]: row["name"] for row in entities}
                    graph["entities"] = [{key: value for key, value in row.items() if key in self._ENTITY_FIELDS} for row in entities]
                    graph["relations"] = [{**{key: value for key, value in row.items() if key in self._RELATION_FIELDS},
                                            "subject": names[row["subject_id"]], "object": names[row["object_id"]]}
                                           for row in self._rows(connection, "SELECT * FROM graph_relations WHERE character_id=? ORDER BY id", (identity,))]
                    if "graph_entity_aliases" in tables:
                        graph["aliases"] = self._rows(connection, """SELECT e.name AS entity, a.surface, a.language
                            FROM graph_entity_aliases a JOIN graph_entities e ON e.id=a.entity_id WHERE e.character_id=?
                            ORDER BY e.name, a.surface""", (identity,))
                characters[identity] = {"variables": variables, "memories": memories, "graph": graph}
        return JsonDocument({"characters": characters})

    def validate(self, state: JsonDocument):
        data = state.to_dict()
        characters = data.get("characters")
        if set(data) != {"characters"} or not isinstance(characters, dict) or set(characters) != set(self._character_ids()):
            raise InvalidTimelineOperation("Character snapshot roster differs from this application")
        with closing(self._factory()) as connection:
            tables = self._tables(connection)
            memory_columns = {row[1] for row in connection.execute("PRAGMA table_info(memories)")}
            for identity, character in characters.items():
                if (not isinstance(character, dict) or set(character) != {"variables", "memories", "graph"}
                        or not isinstance(character.get("variables"), dict)):
                    raise InvalidTimelineOperation(f"Invalid variable snapshot for {identity}")
                memories = character.get("memories")
                if not isinstance(memories, list):
                    raise InvalidTimelineOperation("Memory snapshot must be a list")
                ids = set()
                for memory in memories:
                    if (not isinstance(memory, dict) or not {"eternal_id", "content"} <= memory.keys()
                            or not memory.keys() <= self._MEMORY_FIELDS & memory_columns
                            or type(memory["eternal_id"]) is not int or memory["eternal_id"] < 1
                            or memory["eternal_id"] in ids or not isinstance(memory["content"], str)):
                        raise InvalidTimelineOperation("Invalid or conflicting semantic memory identity")
                    ids.add(memory["eternal_id"])
                    self._fields(memory, text=("priority", "type", "date_created", "tags", "participants", "entities", "last_accessed"),
                                 counts=("access_count",), flags=("is_deleted", "is_forgotten"))
                graph = character.get("graph")
                if not isinstance(graph, dict) or set(graph) != {"entities", "relations", "aliases"}:
                    raise InvalidTimelineOperation("Invalid graph snapshot")
                if not all(isinstance(value, list) for value in graph.values()):
                    raise InvalidTimelineOperation("Graph components must be lists")
                if any(graph.values()) and not {"graph_entities", "graph_relations", "graph_entity_aliases"} <= tables:
                    raise InvalidTimelineOperation("Graph storage is unavailable for this snapshot")
                names = set()
                for entity in graph["entities"]:
                    if (not isinstance(entity, dict) or not entity.keys() <= self._ENTITY_FIELDS
                            or not isinstance(entity.get("name"), str) or not entity["name"] or entity["name"] in names):
                        raise InvalidTimelineOperation("Invalid graph entity identity")
                    names.add(entity["name"])
                    self._fields(entity, text=("entity_type", "first_seen", "last_seen"), counts=("mention_count", "access_count"), flags=("is_protected",))
                for relation in graph["relations"]:
                    if (not isinstance(relation, dict) or not relation.keys() <= self._RELATION_FIELDS
                            or not isinstance(relation.get("subject"), str) or not isinstance(relation.get("object"), str)
                            or relation.get("subject") not in names or relation.get("object") not in names
                            or not isinstance(relation.get("predicate"), str) or not relation["predicate"]):
                        raise InvalidTimelineOperation("Graph relation references an absent entity")
                    self._fields(relation, text=("created_at",), flags=("is_protected",))
                    confidence = relation.get("confidence")
                    if confidence is not None and (type(confidence) not in {int, float} or not math.isfinite(confidence) or not 0 <= confidence <= 1):
                        raise InvalidTimelineOperation("Invalid graph confidence")
                aliases = set()
                for alias in graph["aliases"]:
                    if (not isinstance(alias, dict) or set(alias) != {"entity", "surface", "language"}
                            or not isinstance(alias["entity"], str)
                            or alias["entity"] not in names or not isinstance(alias["surface"], str)
                            or (alias["language"] is not None and not isinstance(alias["language"], str))
                            or (alias["entity"], alias["surface"]) in aliases):
                        raise InvalidTimelineOperation("Invalid graph alias")
                    aliases.add((alias["entity"], alias["surface"]))

    @staticmethod
    def _insert(connection, table, values):
        columns = tuple(values)
        return connection.execute(f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
                                  tuple(values[column] for column in columns)).lastrowid

    def apply(self, state: JsonDocument, *, branch_id: str | None = None):
        self.validate(state)
        with closing(self._factory()) as connection:
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("BEGIN IMMEDIATE")
            try:
                tables = self._tables(connection)
                for identity, character in state.to_dict()["characters"].items():
                    for table in ("variables", "memories", "embeddings", "sentence_embeddings", "graph_processed_messages", "graph_relations"):
                        if table in tables:
                            connection.execute(f"DELETE FROM {table} WHERE character_id=?", (identity,))
                    connection.executemany("INSERT INTO variables VALUES (?, ?, ?)",
                                           [(identity, key, json.dumps(value, ensure_ascii=False)) for key, value in character["variables"].items()])
                    for memory in character["memories"]:
                        self._insert(connection, "memories", dict(memory, character_id=identity))
                    graph = character["graph"]
                    if "graph_entities" in tables:
                        for table in ("graph_entity_aliases", "graph_entity_embeddings"):
                            if table in tables:
                                connection.execute(f"DELETE FROM {table} WHERE entity_id IN (SELECT id FROM graph_entities WHERE character_id=?)", (identity,))
                        connection.execute("DELETE FROM graph_entities WHERE character_id=?", (identity,))
                        names = {entity["name"]: self._insert(connection, "graph_entities", dict(entity, character_id=identity))
                                 for entity in graph["entities"]}
                        for relation in graph["relations"]:
                            values = {key: value for key, value in relation.items() if key not in {"subject", "object"}}
                            self._insert(connection, "graph_relations", dict(values, character_id=identity,
                                         subject_id=names[relation["subject"]], object_id=names[relation["object"]]))
                        for alias in graph["aliases"]:
                            self._insert(connection, "graph_entity_aliases", {"entity_id": names[alias["entity"]],
                                         "surface": alias["surface"], "language": alias["language"]})
                connection.commit()
            except BaseException:
                connection.rollback()
                raise
