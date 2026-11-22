SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS timeline_schema (version INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS timeline_sessions (
    session_id TEXT PRIMARY KEY,
    root_branch_id TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS timeline_branches (
    branch_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES timeline_sessions(session_id),
    parent_branch_id TEXT REFERENCES timeline_branches(branch_id),
    fork_sequence INTEGER NOT NULL CHECK(fork_sequence >= 0),
    head_sequence INTEGER NOT NULL CHECK(head_sequence >= fork_sequence),
    checkpoint_id TEXT
);
CREATE TABLE IF NOT EXISTS timeline_events (
    event_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES timeline_sessions(session_id),
    branch_id TEXT NOT NULL REFERENCES timeline_branches(branch_id),
    sequence INTEGER NOT NULL CHECK(sequence > 0),
    kind TEXT NOT NULL,
    actor_id TEXT,
    payload TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    UNIQUE(branch_id, sequence)
);
CREATE TABLE IF NOT EXISTS timeline_observers (
    event_id TEXT NOT NULL REFERENCES timeline_events(event_id),
    character_id TEXT NOT NULL,
    PRIMARY KEY(event_id, character_id)
);
CREATE INDEX IF NOT EXISTS timeline_events_kind
    ON timeline_events(branch_id, kind, sequence);
CREATE TABLE IF NOT EXISTS timeline_message_keys (
    event_id TEXT PRIMARY KEY REFERENCES timeline_events(event_id),
    message_id TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS timeline_message_keys_lookup ON timeline_message_keys(message_id, event_id);
CREATE INDEX IF NOT EXISTS timeline_observers_character
    ON timeline_observers(character_id, event_id);
CREATE TABLE IF NOT EXISTS timeline_links (
    event_id TEXT NOT NULL REFERENCES timeline_events(event_id),
    relation TEXT NOT NULL,
    target_id TEXT NOT NULL REFERENCES timeline_events(event_id),
    PRIMARY KEY(event_id, relation, target_id)
);
CREATE INDEX IF NOT EXISTS timeline_links_target
    ON timeline_links(target_id, relation, event_id);
CREATE TABLE IF NOT EXISTS timeline_operations (
    branch_id TEXT NOT NULL REFERENCES timeline_branches(branch_id),
    idempotency_key TEXT NOT NULL,
    intent TEXT NOT NULL,
    event_ids TEXT NOT NULL,
    PRIMARY KEY(branch_id, idempotency_key)
);
CREATE TABLE IF NOT EXISTS timeline_workspace (
    workspace TEXT PRIMARY KEY,
    branch_id TEXT NOT NULL REFERENCES timeline_branches(branch_id),
    generation INTEGER NOT NULL CHECK(generation > 0)
);
"""

LINEAGE = """
WITH RECURSIVE lineage(branch_id, ceiling) AS (
    SELECT branch_id, MIN(head_sequence, :ceiling)
    FROM timeline_branches WHERE branch_id = :branch_id
    UNION ALL
    SELECT parent.branch_id, MIN(lineage.ceiling, child.fork_sequence)
    FROM lineage
    JOIN timeline_branches child ON child.branch_id = lineage.branch_id
    JOIN timeline_branches parent ON parent.branch_id = child.parent_branch_id
)
"""
