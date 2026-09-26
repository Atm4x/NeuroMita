from __future__ import annotations

import base64
import json
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from main_logger import logger


class UnityRetryStore:
    """Bounded, per-character outbox for Unity-originated player turns."""

    VERSION = 1
    MAX_RECORDS = 100
    MAX_BYTES = 64 * 1024 * 1024
    MAX_AGE_SECONDS = 30 * 24 * 60 * 60
    _lock = threading.RLock()

    @classmethod
    def _path(cls, character_id: str) -> Path:
        safe_character = "".join(
            ch if ch.isalnum() or ch in "-_" else "_"
            for ch in str(character_id or "").strip()
        ).strip("-_") or "unknown"
        histories = Path(
            os.environ.get("NEUROMITA_HISTORIES_DIR")
            or Path.cwd() / "Histories"
        )
        return histories / safe_character / "unity_retry_outbox.json"

    @classmethod
    def _read(cls, character_id: str) -> list[dict[str, Any]]:
        path = cls._path(character_id)
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("version") != cls.VERSION or not isinstance(payload.get("records"), list):
                raise ValueError("Unsupported Unity retry outbox format")
            return [item for item in payload["records"] if isinstance(item, dict)]
        except Exception as exc:
            logger.warning("Unable to load Unity retry outbox %s: %s", path, exc)
            return []

    @classmethod
    def _write(cls, character_id: str, records: list[dict[str, Any]]) -> bool:
        path = cls._path(character_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(
            {"version": cls.VERSION, "records": records},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        if len(content.encode("utf-8")) > cls.MAX_BYTES:
            return False
        fd, temp_path = tempfile.mkstemp(prefix=".unity-retry-", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as target:
                target.write(content)
                target.flush()
                os.fsync(target.fileno())
            os.replace(temp_path, path)
            return True
        except Exception:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise

    @classmethod
    def _prune(cls, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        cutoff = time.time() - cls.MAX_AGE_SECONDS
        return [
            item for item in records
            if float(item.get("created_at", 0) or 0) >= cutoff
        ]

    @classmethod
    def _json_safe(cls, value: Any) -> Any:
        if isinstance(value, bytes):
            return {"__unity_retry_bytes__": base64.b64encode(value).decode("ascii")}
        if isinstance(value, dict):
            return {str(key): cls._json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._json_safe(item) for item in value]
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        return str(value)

    @classmethod
    def _restore_bytes(cls, value: Any) -> Any:
        if isinstance(value, dict):
            if set(value) == {"__unity_retry_bytes__"}:
                try:
                    return base64.b64decode(value["__unity_retry_bytes__"])
                except Exception:
                    return b""
            return {key: cls._restore_bytes(item) for key, item in value.items()}
        if isinstance(value, list):
            return [cls._restore_bytes(item) for item in value]
        return value

    @classmethod
    def add(cls, character_id: str, record: dict[str, Any]) -> bool:
        with cls._lock:
            records = cls._prune(cls._read(character_id))
            message_id = str(record.get("message_id") or "")
            if message_id and any(str(item.get("message_id") or "") == message_id for item in records):
                return True
            if len(records) >= cls.MAX_RECORDS:
                logger.warning("Unity retry outbox is full for character %s", character_id)
                return False
            stored = cls._json_safe(dict(record))
            stored.setdefault("created_at", time.time())
            stored["status"] = "pending"
            stored.setdefault("active_task_uid", "")
            saved = cls._write(character_id, [*records, stored])
            if not saved:
                logger.warning("Unity retry outbox size limit reached for character %s", character_id)
            return saved

    @classmethod
    def list_for_character(cls, character_id: str) -> list[dict[str, Any]]:
        with cls._lock:
            source = cls._read(character_id)
            records = cls._prune(source)
            changed = len(records) != len(source)
            for item in records:
                if item.get("status") == "retrying":
                    item["status"] = "pending"
                    item["error"] = "Приложение перезапустилось до завершения повтора."
                    changed = True
            restored = [cls._restore_bytes(item) for item in records]
            if changed:
                cls._write(character_id, records)
            return restored

    @classmethod
    def get(cls, character_id: str, message_id: str) -> dict[str, Any] | None:
        target = str(message_id or "")
        return next(
            (item for item in cls.list_for_character(character_id) if str(item.get("message_id") or "") == target),
            None,
        )

    @classmethod
    def update(cls, character_id: str, message_id: str, **changes: Any) -> bool:
        with cls._lock:
            records = cls._prune(cls._read(character_id))
            target = str(message_id or "")
            for item in records:
                if str(item.get("message_id") or "") == target:
                    item.update(cls._json_safe(changes))
                    return cls._write(character_id, records)
            return False

    @classmethod
    def claim(cls, character_id: str, message_id: str) -> dict[str, Any] | None:
        """Atomically reserve one retry so rapid clicks cannot enqueue duplicates."""
        with cls._lock:
            records = cls._prune(cls._read(character_id))
            target = str(message_id or "")
            for item in records:
                if str(item.get("message_id") or "") != target:
                    continue
                if item.get("status") == "retrying":
                    return None
                item["status"] = "retrying"
                item["error"] = ""
                item["active_task_uid"] = ""
                if not cls._write(character_id, records):
                    item["status"] = "pending"
                    return None
                return cls._restore_bytes(item)
            return None

    @classmethod
    def set_active_task(
        cls,
        character_id: str,
        message_id: str,
        task_uid: str,
    ) -> bool:
        with cls._lock:
            records = cls._prune(cls._read(character_id))
            for item in records:
                if (
                    str(item.get("message_id") or "") == str(message_id or "")
                    and item.get("status") == "retrying"
                ):
                    item["active_task_uid"] = str(task_uid or "")
                    return cls._write(character_id, records)
            return False

    @classmethod
    def finish_failed_attempt(
        cls,
        character_id: str,
        message_id: str,
        task_uid: str,
        error: str,
    ) -> bool:
        with cls._lock:
            records = cls._prune(cls._read(character_id))
            for item in records:
                if (
                    str(item.get("message_id") or "") == str(message_id or "")
                    and str(item.get("active_task_uid") or "") == str(task_uid or "")
                ):
                    item["status"] = "pending"
                    item["error"] = str(error or "Не удалось получить ответ.")
                    return cls._write(character_id, records)
            return False

    @classmethod
    def complete_delivery(
        cls,
        character_id: str,
        message_id: str,
        task_uid: str,
    ) -> bool:
        with cls._lock:
            records = cls._prune(cls._read(character_id))
            remaining = [
                item for item in records
                if not (
                    str(item.get("message_id") or "") == str(message_id or "")
                    and str(item.get("active_task_uid") or "") == str(task_uid or "")
                )
            ]
            if len(remaining) == len(records):
                return False
            return cls._write(character_id, remaining)

    @classmethod
    def remove(cls, character_id: str, message_id: str) -> bool:
        with cls._lock:
            records = cls._prune(cls._read(character_id))
            target = str(message_id or "")
            remaining = [item for item in records if str(item.get("message_id") or "") != target]
            if len(remaining) == len(records):
                return False
            return cls._write(character_id, remaining)
