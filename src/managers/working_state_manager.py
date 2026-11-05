"""Ephemeral per-character cognitive context for the next model turn.

This is deliberately separate from dialogue history, long-term memory and the
objective Unity ``GameState``.  It is an in-process session cache: clearing a
chat clears it, and restarting the application starts a fresh session.
"""
from __future__ import annotations

import threading
from copy import deepcopy
from typing import Any

from domain.working_state import (
    DEFAULT_MAX_CHARS,
    normalize_working_state_update,
    render_normalized_prompt_block,
)
from managers.character_scoped_service import CharacterScopedService


class WorkingStateManager(CharacterScopedService):
    """Own compact, per-character working state without persisting it as history."""

    _FIELDS = (
        ("focus", "Focus"),
        ("situation", "Current understanding"),
        ("assumptions", "Tentative assumptions"),
        ("open_loops", "Open loops"),
        ("next_steps", "Immediate next steps"),
    )

    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.RLock()
        self._states: dict[str, dict[str, Any]] = {}
        self._epochs: dict[str, int] = {}

    def update(
        self,
        value: Any,
        *,
        epoch: int | None = None,
        max_chars: int = DEFAULT_MAX_CHARS,
    ) -> bool:
        """Replace the state with a bounded model-produced snapshot.

        An empty or malformed update is ignored: the last valid note stays in
        place instead of being destroyed by a bad turn. A snapshot produced
        before the last history reset is stale and is dropped as well.
        """
        key = self.storage_key
        with self._lock:
            if epoch is not None:
                known = self._epochs.get(key)
                if known is None:
                    self._epochs[key] = int(epoch)
                elif int(epoch) != known:
                    return False

            cleaned = normalize_working_state_update(value, max_chars=max_chars)
            if cleaned is None:
                return False
            self._states[key] = cleaned
            return True

    def clear(self, *, epoch: int | None = None) -> None:
        with self._lock:
            key = self.storage_key
            self._states.pop(key, None)
            if epoch is not None:
                self._epochs[key] = int(epoch)

    def snapshot(self) -> dict:
        with self._lock:
            return deepcopy(self._states.get(self.storage_key, {}))

    @classmethod
    def validate_snapshot(cls, state: dict) -> None:
        allowed = {field for field, _label in cls._FIELDS}
        if not isinstance(state, dict) or not state.keys() <= allowed:
            raise ValueError("Invalid working-state fields")
        for field, value in state.items():
            if ((field == "focus" and not isinstance(value, str))
                    or (field != "focus" and (not isinstance(value, list) or not all(isinstance(item, str) for item in value)))):
                raise ValueError("Invalid working-state value")

    def restore_snapshot(self, state: dict) -> None:
        self.validate_snapshot(state)
        with self._lock:
            if state:
                self._states[self.storage_key] = deepcopy(state)
            else:
                self._states.pop(self.storage_key, None)

    def format_for_prompt(self) -> str:
        with self._lock:
            state = dict(self._states.get(self.storage_key, {}))
        if not state:
            return ""
        return render_normalized_prompt_block(state) or ""
