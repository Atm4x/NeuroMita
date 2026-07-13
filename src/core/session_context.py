"""Ambient «активная сессия» (сейв) для всех character-scoped менеджеров.

Идея: session_id — это глобальное состояние приложения (какой сейв сейчас открыт),
ортогональное персонажу. Хранить его в CharacterScope нельзя: scope кешируются по
character_id и переиспользуются, а сессия меняется целиком. Поэтому сессия живёт здесь:

- глобальная «активная сессия» (get/set_active_session_id) — что открыто прямо сейчас;
- ContextVar-override (session_scope) — для «заморозки» сессии в фоновых задачах и для
  межсессионных операций (копирование сейва), чтобы переключение активной сессии посреди
  фоновой работы не записало данные в чужой сейв.

Менеджеры читают current_session_id() и добавляют его в WHERE/INSERT своих запросов.
"""
from __future__ import annotations

import threading
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

DEFAULT_SESSION_ID = "default"

_active_session_id: str = DEFAULT_SESSION_ID
_active_lock = threading.RLock()
_session_override: ContextVar[str | None] = ContextVar("session_override", default=None)


def normalize_session_id(session_id: object) -> str:
    """Приводит идентификатор сессии к непустой строке (fallback — 'default')."""
    value = str(session_id or "").strip()
    return value or DEFAULT_SESSION_ID


def get_active_session_id() -> str:
    """Глобально активная сессия (без учёта override)."""
    with _active_lock:
        return _active_session_id


def set_active_session_id(session_id: object) -> str:
    """Меняет глобально активную сессию. Возвращает нормализованный id."""
    global _active_session_id
    sid = normalize_session_id(session_id)
    with _active_lock:
        _active_session_id = sid
    return sid


def current_session_id() -> str:
    """Сессия, действующая в текущем контексте: override (если задан) иначе активная."""
    override = _session_override.get()
    if override:
        return override
    return get_active_session_id()


@contextmanager
def session_scope(session_id: object) -> Iterator[str]:
    """Временно переопределяет сессию для текущего потока/таски.

    Используется для заморозки сессии в фоновых задачах (сжатие истории, эмбеддинги)
    и для межсессионных операций (копирование сейва)."""
    sid = normalize_session_id(session_id)
    token = _session_override.set(sid)
    try:
        yield sid
    finally:
        _session_override.reset(token)
