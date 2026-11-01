from __future__ import annotations
from core.error_utils import format_exception
from core.state_barrier import state_operation

import threading
from dataclasses import dataclass, asdict
from typing import Callable, Dict, List, Optional

from characters import (
    Cappie,
    CrazyMita,
    CreepyMita,
    GameMaster,
    GhostMita,
    KindMita,
    MilaMita,
    ShortHairMita,
    SleepyMita,
)
from characters.character import Character
from characters.novel import TwoDMita
from main_logger import logger
from managers.character_resource_manager import (
    CharacterResourceManager,
    get_character_resource_manager,
)


@dataclass(frozen=True)
class CharacterDefinition:
    character_id: str
    factory: Callable[[], Character]
    title: str = ""
    storage: str = ""

    @property
    def display_name(self) -> str:
        return self.title or str(getattr(self.factory, "DISPLAY_NAME", self.character_id) or self.character_id)

    @property
    def storage_name(self) -> str:
        return self.storage or str(getattr(self.factory, "STORAGE_NAME", self.character_id) or self.character_id)


_CHARACTER_DEFINITIONS: tuple[CharacterDefinition, ...] = (
    CharacterDefinition("Crazy", CrazyMita),
    CharacterDefinition("Kind", KindMita),
    CharacterDefinition("Cappie", Cappie),
    CharacterDefinition("ShortHair", ShortHairMita),
    CharacterDefinition("Mila", MilaMita),
    CharacterDefinition("Sleepy", SleepyMita),
    CharacterDefinition("Creepy", CreepyMita),
    CharacterDefinition("Ghost", GhostMita),
    CharacterDefinition("GameMaster", GameMaster),
    CharacterDefinition("TwoD", TwoDMita),
)


class CharacterManager:
    """Owns lightweight definitions and lazily materialized Character runtimes."""

    def __init__(
        self,
        initial_character_id: Optional[str] = None,
        resources: Optional[CharacterResourceManager] = None,
    ):
        self._lock = threading.RLock()
        self._definitions = {
            definition.character_id: definition
            for definition in _CHARACTER_DEFINITIONS
        }
        self.characters: Dict[str, Character] = {}
        self.current_character: Optional[Character] = None
        self.current_character_to_change = str(initial_character_id or "")
        self.resources = resources or get_character_resource_manager()

        for definition in _CHARACTER_DEFINITIONS:
            self.resources.register_character(
                definition.character_id,
                definition.storage_name,
            )

        initial_id = (
            self.current_character_to_change
            if self.current_character_to_change in self._definitions
            else "Crazy"
        )
        self.current_character_to_change = ""
        self.current_character = self.get_character(initial_id)

        if self.current_character:
            logger.info(
                f"[CharacterManager] Current character: {self.current_character.char_id}; "
                f"loaded={list(self.characters)} available={list(self._definitions)}"
            )
        else:
            logger.error("[CharacterManager] No characters initialized!")

    @property
    def crazy_mita_character(self) -> Optional[Character]:
        return self.get_loaded_character("Crazy") or (
            self.get_character("Crazy") if self.current_character is None else None
        )

    @property
    def GameMaster(self) -> Optional[Character]:
        return self.get_loaded_character("GameMaster")

    def _create_character(self, definition: CharacterDefinition) -> Character:
        character = definition.factory()
        character.bind_resource_manager(self.resources)
        self.characters[definition.character_id] = character
        logger.info(
            f"[CharacterManager] Materialized {definition.character_id}; "
            f"loaded={list(self.characters)}"
        )
        return character

    def get_all_characters(self) -> List[str]:
        override = getattr(self, "_snapshot_roster", None)
        return list(override.get() if override is not None and override.get() is not None else self._definitions)

    @state_operation(wait=True)
    def register_cartridges(self, definitions) -> None:
        from characters.cartridge import CartridgeCharacter

        definitions = self.validate_cartridge_definitions([asdict(item) for item in definitions])
        with self._lock:
            if not hasattr(self, "_cartridge_definitions"):
                self._cartridge_definitions = {}
            for item in definitions:
                self._cartridge_definitions[item.character_id] = item
                current = self.characters.get(item.character_id)
                if current is not None:
                    if not isinstance(current, CartridgeCharacter):
                        raise ValueError("Cartridge cannot replace an ordinary character")
                    current.cartridge_definition = item
                    current.display_name = item.title
                self._definitions[item.character_id] = CharacterDefinition(
                    item.character_id, lambda definition=item: CartridgeCharacter(definition),
                    item.title, item.character_id,
                )
                self.resources.register_character(item.character_id, item.character_id)

    def capture_cartridge_definitions(self):
        from dataclasses import asdict
        return [asdict(item) for item in getattr(self, "_cartridge_definitions", {}).values()]

    @staticmethod
    def validate_cartridge_definitions(rows):
        from domain.cartridge_catalog import parse_catalog
        if not isinstance(rows, list):
            raise ValueError("Invalid snapshot cartridge catalog")
        if any(not isinstance(row, dict) or not isinstance(row.get("character_id"), str) for row in rows):
            raise ValueError("Invalid snapshot cartridge record")
        parsed = parse_catalog({"version": 1, "cartridges": [
            {"id": row["id"], "legacyCharacter": row["character_id"] if row["character_id"].startswith("Cart_") else None,
             "title": row["title"], "record": "Snapshot catalog", "prompt": row["prompt"], "historyMessages": row["history_messages"],
             "contextCharacters": row["context_characters"], "effects": [], "itemNames": []} for row in rows]})
        from dataclasses import asdict
        if [asdict(item) for item in parsed] != rows:
            raise ValueError("Snapshot cartridge identities differ from their definitions")
        return parsed

    def snapshot_roster_scope(self, definitions):
        from contextlib import contextmanager
        from contextvars import ContextVar
        if not hasattr(self, "_snapshot_roster"):
            self._snapshot_roster = ContextVar("character_snapshot_roster", default=None)
        @contextmanager
        def scope():
            token = self._snapshot_roster.set([item.character_id for item in _CHARACTER_DEFINITIONS] +
                                              [item.character_id for item in definitions])
            try:
                yield
            finally:
                self._snapshot_roster.reset(token)
        return scope()

    @state_operation(wait=True)
    def restore_cartridge_definitions(self, definitions):
        with self._lock:
            incoming = {item.character_id for item in definitions}
            retired = set(getattr(self, "_cartridge_definitions", {})) - incoming
            self._retired_cartridges = (set(getattr(self, "_retired_cartridges", set())) | retired) - incoming
            for identity in retired:
                character = self.characters.get(identity)
                if character is not None:
                    character.game_manager.restore_paused_snapshot(None, selection=None)
                    if self.current_character is character:
                        self.current_character = self.characters.get("Crazy")
                self._definitions.pop(identity, None)
                self.characters.pop(identity, None)
                from managers.mini_game_session_registry import mini_game_sessions
                mini_game_sessions().stop(identity)
                self.resources.working_state_for(identity).restore_snapshot({})
                self.resources.reminders_for(identity).restore_snapshot({"reminders": [], "next_number": 1, "timer_remaining": {}})
                self.resources.history_manager.bind(identity).replace_timeline_cache([])
                self.resources.memory_for(identity).invalidate_snapshot_cache()
            self._cartridge_definitions = {}
            self.register_cartridges(definitions)

    def retired_cartridge_ids(self):
        return tuple(getattr(self, "_retired_cartridges", ()))

    def get_character_stats(self, char_id: str) -> dict[str, float]:
        """Read runtime values if loaded, otherwise only the persisted statistics."""
        defaults = {"attitude": 60.0, "boredom": 10.0, "stress": 5.0}
        key = str(char_id or "").strip()
        with self._lock:
            character = self.characters.get(key)
            if character is not None:
                return character.get_stats_dict()
            definition = self._definitions.get(key)
        if definition is None:
            return defaults
        values = self.resources.history_for(key, definition.storage_name).load_variables(defaults)
        result = dict(defaults)
        for name, default in defaults.items():
            try:
                result[name] = float(values.get(name, default))
            except (TypeError, ValueError):
                pass
        return result

    def get_display_name(self, char_id: str) -> str:
        definition = self._definitions.get(str(char_id or "").strip())
        return definition.display_name if definition is not None else str(char_id or "")

    def get_loaded_characters(self) -> List[Character]:
        with self._lock:
            return list(self.characters.values())

    def get_loaded_character(self, char_id: str) -> Optional[Character]:
        with self._lock:
            return self.characters.get(str(char_id or ""))

    @state_operation(wait=True)
    def get_character(self, char_id: str) -> Optional[Character]:
        key = str(char_id or "").strip()
        if not key:
            return None
        definition = self._definitions.get(key)
        if definition is None:
            return None

        with self._lock:
            character = self.characters.get(key)
            if character is None:
                character = self._create_character(definition)

        character.ensure_runtime_loaded()
        return character

    def set_character_to_change(self, char_id: str) -> None:
        self.current_character_to_change = str(char_id or "")

    def check_change_current_character(self) -> None:
        if not self.current_character_to_change:
            return

        target = self.current_character_to_change
        self.current_character_to_change = ""

        current_id = str(getattr(self.current_character, "char_id", "") or "")
        if current_id == target:
            return

        if target not in self._definitions:
            logger.warning(
                f"[CharacterManager] Attempted to change to unknown character: {target}"
            )
            return

        was_loaded = self.get_loaded_character(target) is not None
        character = self.get_character(target)
        if character is None:
            return
        self.current_character = character
        logger.info(f"[CharacterManager] Changing character to {target}")
        if not was_loaded:
            return
        try:
            character.reload_character_data()
        except Exception as exc:
            logger.error(
                f"[CharacterManager] Failed to reload character data for {target}: {format_exception(exc)}",
                exc_info=True,
            )

    def clear_all_histories(self) -> None:
        loaded_ids = set(self.characters)
        for character in self.get_loaded_characters():
            character.clear_history()

        for character_id in self._definitions:
            if character_id in loaded_ids:
                continue
            try:
                self.resources.history_for(character_id).clear_history()
                self.resources.memory_for(character_id).clear_memories()
                self.resources.working_state_for(character_id).clear()
            except Exception as exc:
                logger.error(
                    f"[CharacterManager] Failed to clear resources for {character_id}: {format_exception(exc)}",
                    exc_info=True,
                )
            try:
                from managers.database_manager import DatabaseManager
                from managers.rag.graph.graph_store import GraphStore

                GraphStore(DatabaseManager(), character_id).clear_for_character()
            except Exception as exc:
                logger.warning(
                    f"[{character_id}] Graph clear failed (ignored): {format_exception(exc)}",
                    exc_info=True,
                )

    def shutdown(self) -> None:
        self.resources.shutdown()
