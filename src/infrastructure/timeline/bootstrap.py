from __future__ import annotations

from services.conversation_timeline import ConversationTimeline
from services.timeline_runtime import SessionTimelineRuntime
from domain.timeline.time import message_timestamp
from .sqlite import SQLiteTimelineRepository
from .assets import SQLiteTimelineAssets


def bootstrap_timeline(database, character_resources, character_ids, *, state=None) -> ConversationTimeline:
    """Resume one conservative, restartable import before admitting runtime requests."""
    repository = SQLiteTimelineRepository(connection_factory=database.get_connection)
    runtime = SessionTimelineRuntime(repository, repository, state=state)
    conversation = ConversationTimeline(runtime, SQLiteTimelineAssets(database.get_connection))
    with database.connection() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS timeline_migrations (name TEXT PRIMARY KEY)")
        complete = conn.execute("SELECT 1 FROM timeline_migrations WHERE name=?",
                                ("character-histories-v1",)).fetchone()
        conn.commit()
    if complete:
        return conversation
    records = []
    for character_id in character_ids:
        history = character_resources.history_for(character_id)
        export = getattr(history, "export_timeline_history", None)
        messages = export() if callable(export) else history.load_history().get("messages", ())
        for message in messages:
            if message.get("role") in {"user", "assistant", "system", "event"}:
                records.append((character_id, message))
    records.sort(key=lambda item: (message_timestamp(item[1].get("time")) or "",
                                   int(item[1].get("_history_row_id") or 0), item[0]))
    for character_id, message in records:
        conversation.import_history(character_id, (message,))
    with database.connection() as conn:
        conn.execute("INSERT OR IGNORE INTO timeline_migrations VALUES (?)", ("character-histories-v1",))
        conn.commit()
    return conversation
