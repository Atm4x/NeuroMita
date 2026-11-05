"""Per-character cache of the skill catalog supplied by the game runtime."""
from __future__ import annotations

import threading
from typing import Any

from managers.character_scoped_service import CharacterScopedService


class SkillCatalogRegistry(CharacterScopedService):
    """Hold the last catalog the runtime sent for this character.

    The prompt and the load_skill tool must agree on what exists; the tool has
    no request payload, so the catalog is cached when the turn starts.
    """

    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.RLock()
        self._catalogs: dict[str, Any] = {}

    def set(self, catalog: Any) -> None:
        with self._lock:
            if catalog is None:
                self._catalogs.pop(self.storage_key, None)
            else:
                self._catalogs[self.storage_key] = catalog

    def get(self) -> Any:
        with self._lock:
            return self._catalogs.get(self.storage_key)

    def clear(self, **_: object) -> None:
        with self._lock:
            self._catalogs.pop(self.storage_key, None)
