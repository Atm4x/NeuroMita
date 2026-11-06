"""Bounded set of skills that stay loaded for the next turns."""
from __future__ import annotations

import threading
from collections import OrderedDict

from managers.character_scoped_service import CharacterScopedService

MAX_LOADED_SKILLS = 2
MAX_LOADED_SKILL_TOKENS = 2000


class SkillSessionManager(CharacterScopedService):
    """Per-character retention for on-demand skill instructions.

    The model may load a skill once and keep using it while the scene needs
    it; the set is rebuilt every turn from this small ordered cache.
    """

    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.RLock()
        self._loaded: dict[str, OrderedDict[str, int]] = {}

    def remember(
        self,
        skill_id: str,
        *,
        tokens: int,
        max_skills: int = MAX_LOADED_SKILLS,
        max_tokens: int = MAX_LOADED_SKILL_TOKENS,
    ) -> bool:
        """Remember one loaded skill, evicting the least recently used ones."""
        key = str(skill_id or "").strip()
        if not key:
            return False
        cost = max(0, int(tokens or 0))
        limit_skills = max(1, int(max_skills or MAX_LOADED_SKILLS))
        limit_tokens = max(200, int(max_tokens or MAX_LOADED_SKILL_TOKENS))
        with self._lock:
            loaded = self._loaded.setdefault(self.storage_key, OrderedDict())
            loaded.pop(key, None)
            loaded[key] = cost
            while len(loaded) > 1 and (
                len(loaded) > limit_skills
                or sum(loaded.values()) > limit_tokens
            ):
                loaded.popitem(last=False)
            return key in loaded

    def loaded(self) -> list[str]:
        with self._lock:
            return list(self._loaded.get(self.storage_key, ()))

    def clear(self, **_: object) -> None:
        with self._lock:
            self._loaded.pop(self.storage_key, None)
