from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from domain.timeline import EventKind, new_id
from services.conversation_timeline import ConversationTimeline


class TimelineHistoryView:
    """Character-bound history projection; the previous store is a disposable cache.

    Variables, image codecs and embedding infrastructure stay with their existing
    owners. Conversation reads and presentation changes use the session timeline.
    """

    def __init__(self, character_id: str, cache: Any, conversation: ConversationTimeline):
        self.character_id = character_id
        self.cache = cache
        self.conversation = conversation

    def __getattr__(self, name: str) -> Any:
        return getattr(self.cache, name)

    def _messages(self) -> list[dict]:
        return list(self.conversation.messages(self.character_id, before_turn=False))

    def load_history(self) -> dict:
        load_variables = getattr(self.cache, "load_variables", None)
        result = ({"fixed_parts": [], "temp_context": [], "variables": load_variables()}
                  if callable(load_variables) else self.cache.load_history())
        result["messages"] = list(self.conversation.content.materialize(self._messages()))
        return result

    def get_total_messages_count(self) -> int:
        return self.conversation.history_queries.count(self.conversation.runtime.timeline.branch_id, self.character_id)

    def get_recent_messages(self, limit: int = 50, offset: int = 0) -> list[dict]:
        if limit <= 0 or offset < 0:
            return []
        return list(self.conversation.content.materialize(self.conversation.history_queries.page(
            self.conversation.runtime.timeline.branch_id, self.character_id, limit=limit, offset=offset,
        )))

    def contains_message_id(self, message_id: str) -> bool:
        return self.conversation.history_queries.contains(
            self.conversation.runtime.timeline.branch_id, self.character_id, message_id,
        )

    def add_messages(self, messages: list[dict]) -> list[int]:
        if messages and all(message.get("timeline_event_id") or message.get("_history_is_deleted") for message in messages):
            committed = []
            timeline = self.conversation.runtime.timeline
            for message in messages:
                if message.get("_history_is_deleted"):
                    committed.append(timeline.branch.head_sequence)
                    continue
                event = timeline.event(message["timeline_event_id"])
                if (event.payload.to_dict().get("content") != message.get("content", "")
                        or not timeline.knows(self.character_id, event.event_id)):
                    raise ValueError("History cache materialization differs from the timeline fact")
                committed.append(event.sequence)
        else:
            committed = self.conversation.append_history(self.character_id, messages)
        try:
            self.cache.add_messages(messages)
        except Exception:
            from main_logger import logger
            logger.warning("Timeline committed; history cache update failed for %s", self.character_id, exc_info=True)
        return committed

    def add_message(self, message: dict):
        rows = self.add_messages([message])
        return rows[0] if rows else None

    append_message = add_message

    def _hide(self, messages: list[dict]) -> bool:
        if not messages:
            return False
        with self.conversation.runtime.writing() as timeline:
            timeline.publish(EventKind.MESSAGE_HIDDEN,
                             {"event_ids": [message["timeline_event_id"] for message in messages]},
                             observers=(self.character_id,), key=f"hide:{new_id()}")
        return True

    def delete_message(self, message_id: str) -> bool:
        return self._hide([message for message in self._messages() if message.get("message_id") == message_id])

    def _delete_suffix(self, predicate, *, include_target: bool) -> bool:
        messages = self._messages()
        for index, message in enumerate(messages):
            if predicate(message):
                return self._hide(messages[index if include_target else index + 1:])
        return False

    def delete_messages_from(self, message_id: str) -> bool:
        return self._delete_suffix(lambda message: message.get("message_id") == message_id, include_target=True)

    def delete_messages_after(self, message_id: str) -> bool:
        return self._delete_suffix(lambda message: message.get("message_id") == message_id, include_target=False)

    def delete_messages_from_row(self, row_id: int | None, *, include_target: bool = True) -> bool:
        return self._delete_suffix(lambda message: message.get("_history_row_id") == row_id,
                                   include_target=include_target)

    def clear_history(self) -> None:
        with self.conversation.runtime.writing() as timeline:
            timeline.publish(EventKind.CONTEXT_RESET, observers=(self.character_id,), key=f"reset:{new_id()}")
        self.conversation.runtime.cancel_character(self.character_id)
        self.cache.clear_history()

    def save_history(self, data: dict) -> None:
        desired = [message for message in data.get("messages", ()) if isinstance(message, dict)]
        self.conversation.replace_history(self.character_id, desired)
        self.cache.update_variables_batch(data.get("variables", {}))

    def save_missed_history(self, messages: list) -> None:
        self.cache.save_missed_history(messages)

    def get_messages_for_compression(self, num_messages: int) -> list[dict]:
        return self._messages()[:max(0, num_messages)]

    def add_summarized_history_to_messages(self, message: dict):
        return self.add_message(message)

    def save_history_separate(self) -> str:
        data = self.load_history()
        with self.conversation.runtime.writing() as timeline:
            checkpoint = timeline.checkpoint(
                {"characters": {self.character_id: {"variables": data.get("variables", {})}}},
                key=f"checkpoint:{new_id()}", label=self.character_id,
            )
            data["timeline_checkpoint_id"] = checkpoint.event_id
            data["timeline_branch_id"] = timeline.branch_id
        import os
        directory = Path(os.environ.get("NEUROMITA_HISTORIES_DIR", "Histories")) / self.character_id / "snapshots"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{checkpoint.event_id}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path.resolve())
