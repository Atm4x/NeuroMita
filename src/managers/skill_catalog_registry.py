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
        # Not "_scopes": the base class owns that name for character scopes.
        self._catalog_scopes: dict[str, str] = {}

    def set(self, catalog: Any, scope: str = "") -> bool:
        """Store the catalog and report whether the gameplay scope changed."""
        normalized = str(scope or "").strip()
        with self._lock:
            previous = self._catalog_scopes.get(self.storage_key, "")
            changed = bool(normalized) and normalized != previous
            if catalog is None:
                self._catalogs.pop(self.storage_key, None)
                self._catalog_scopes.pop(self.storage_key, None)
            else:
                self._catalogs[self.storage_key] = catalog
                if normalized:
                    self._catalog_scopes[self.storage_key] = normalized
            return changed

    def scope(self) -> str:
        with self._lock:
            return self._catalog_scopes.get(self.storage_key, "")

    def get(self) -> Any:
        with self._lock:
            return self._catalogs.get(self.storage_key)

    def clear(self, **_: object) -> None:
        with self._lock:
            self._catalogs.pop(self.storage_key, None)
            self._catalog_scopes.pop(self.storage_key, None)
