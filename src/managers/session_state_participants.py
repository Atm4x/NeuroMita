from __future__ import annotations

from contextlib import nullcontext, contextmanager
from dataclasses import asdict

from domain.timeline import InvalidTimelineOperation, JsonDocument
from managers.reminder_manager import ReminderManager
from managers.mini_game_session_registry import mini_game_sessions, MiniGamePublicSession
from modules.session_snapshot import validate_game_state


class CharacterRuntimeSnapshot:
    key = "character_runtime"
    version = 1

    def __init__(self, manager, conversation):
        self.manager = manager
        self.conversation = conversation

    def paused(self):
        return nullcontext()

    def capture(self) -> JsonDocument:
        characters = {}
        for identity in sorted(self.manager.get_all_characters()):
            character = self.manager.get_loaded_character(identity)
            characters[identity] = {
                "app_vars": dict(character.app_vars) if character else {},
                "materialized": character is not None,
                "working_state": self.manager.resources.working_state_for(identity).snapshot(),
                "reminders": self.manager.resources.reminders_for(identity).snapshot(),
            }
        return JsonDocument({"characters": characters})

    def validate(self, state: JsonDocument):
        data = state.to_dict()
        characters = data.get("characters")
        if set(data) != {"characters"} or not isinstance(characters, dict) or set(characters) != set(self.manager.get_all_characters()):
            raise InvalidTimelineOperation("Runtime character roster differs from the snapshot")
        for character in characters.values():
            if (not isinstance(character, dict) or set(character) != {"app_vars", "materialized", "working_state", "reminders"}
                    or not isinstance(character["app_vars"], dict) or type(character["materialized"]) is not bool):
                raise InvalidTimelineOperation("Invalid character runtime snapshot")
            ReminderManager.validate_snapshot(character["reminders"])
            from managers.working_state_manager import WorkingStateManager
            WorkingStateManager.validate_snapshot(character["working_state"])

    def apply(self, state: JsonDocument, *, branch_id: str):
        self.validate(state)
        resources = self.manager.resources
        for identity, snapshot in state.to_dict()["characters"].items():
            messages = self.conversation.history_queries.messages(branch_id, identity)
            resources.history_manager.bind(identity).replace_timeline_cache(list(messages))
            resources.working_state_for(identity).restore_snapshot(snapshot["working_state"])
            resources.reminders_for(identity).restore_snapshot(snapshot["reminders"])
            resources.memory_for(identity).invalidate_snapshot_cache()
            from managers.rag.pipeline.retrievers.faiss_index import invalidate_character
            invalidate_character(identity)
            character = self.manager.get_loaded_character(identity)
            if character is not None:
                character.restore_session_runtime(resources.history_for(identity).load_variables(), snapshot["app_vars"],
                    initialize_defaults=not snapshot["materialized"])


class ModelContextSnapshot:
    key = "model_context"
    version = 1

    def __init__(self, model):
        self.model = model

    def paused(self):
        return nullcontext()

    def capture(self) -> JsonDocument:
        return JsonDocument(self.model.snapshot_session_context())

    def validate(self, state: JsonDocument):
        self.model.validate_session_context(state.to_dict())

    def apply(self, state: JsonDocument, *, branch_id: str):
        self.model.restore_session_context(state.to_dict())


class GamesSnapshot:
    key = "games"
    version = 1

    def __init__(self, manager, runtime):
        self.manager = manager
        self.runtime = runtime

    @contextmanager
    def paused(self):
        try:
            for character in self.manager.get_loaded_characters():
                game = character.game_manager.active_game
                if game is not None:
                    if game.process_alive:
                        game.pause_for_snapshot()
                    else:
                        game.cleanup()
            yield
        finally:
            failures = []
            for character in self.manager.get_loaded_characters():
                game = character.game_manager.active_game
                if game is not None and game.snapshot_paused and not self.runtime.state.poisoned:
                    try:
                        game.timeline_selection = self.runtime.selection
                        game.resume_from_snapshot()
                    except Exception as exc:
                        failures.append(exc)
            if failures:
                raise RuntimeError("A game process did not resume after the session transition") from failures[0]

    def capture(self) -> JsonDocument:
        games = {}
        for identity in self.manager.get_all_characters():
            character = self.manager.get_loaded_character(identity)
            game = character.game_manager.active_game if character else None
            games[identity] = game.capture_paused_snapshot() if game else None
        public = [asdict(session) for session in mini_game_sessions().snapshot() if session.owner_character_id in games]
        return JsonDocument({"games": games, "public_sessions": public})

    def validate(self, state: JsonDocument):
        data = state.to_dict()
        games = data.get("games")
        if (set(data) != {"games", "public_sessions"} or not isinstance(games, dict)
                or set(games) != set(self.manager.get_all_characters()) or not isinstance(data.get("public_sessions"), list)):
            raise InvalidTimelineOperation("Game snapshot roster differs from this application")
        for game in games.values():
            if game is not None:
                if (not isinstance(game, dict) or set(game) != {"game_id", "instance_id", "state"}
                        or not isinstance(game["instance_id"], str) or not game["instance_id"]):
                    raise InvalidTimelineOperation("Invalid game snapshot identity")
                validate_game_state(game["game_id"], game["state"])
        owners = set()
        for item in data["public_sessions"]:
            if (not isinstance(item, dict) or set(item) != set(MiniGamePublicSession.__dataclass_fields__)
                    or not all(isinstance(value, str) for value in item.values())):
                raise InvalidTimelineOperation("Invalid public game session")
            session = MiniGamePublicSession(**item)
            if session.owner_character_id in owners or games.get(session.owner_character_id) is None or games[session.owner_character_id]["game_id"] != session.game_id:
                raise InvalidTimelineOperation("Public game session differs from its owner")
            owners.add(session.owner_character_id)

    def apply(self, state: JsonDocument, *, branch_id: str):
        self.validate(state)
        data = state.to_dict()
        for identity, snapshot in data["games"].items():
            character = self.manager.get_loaded_character(identity)
            if character is None and snapshot is None:
                continue
            character = character or self.manager.get_character(identity)
            manager = character.game_manager
            manager.restore_paused_snapshot(snapshot, selection=self.runtime.selection)
        for identity in data["games"]:
            mini_game_sessions().stop(identity)
        for session in data["public_sessions"]:
            mini_game_sessions().restore_snapshot(MiniGamePublicSession(**session))


class CatalogSnapshotParticipant:
    """Bind each character-state owner to the same durable virtual roster."""

    def __init__(self, participant, manager):
        self.participant, self.manager = participant, manager
        self.key, self.version = participant.key, participant.version

    def paused(self):
        return self.participant.paused()

    def capture(self):
        data = self.participant.capture().to_dict()
        data["_cartridges"] = self.manager.capture_cartridge_definitions()
        return JsonDocument(data)

    def validation_dependencies(self, state):
        self._unpack(state)
        return {"character_catalog": state.to_dict().get("_cartridges", [])}

    def _unpack(self, state):
        data = state.to_dict()
        try:
            definitions = self.manager.validate_cartridge_definitions(data.pop("_cartridges", []))
        except (ValueError, KeyError, TypeError) as exc:
            raise InvalidTimelineOperation("Invalid snapshot cartridge definitions") from exc
        return definitions, JsonDocument(data)

    def validate(self, state):
        definitions, data = self._unpack(state)
        with self.manager.snapshot_roster_scope(definitions):
            self.participant.validate(data)

    def apply(self, state, *, branch_id):
        self.validate(state)
        definitions, data = self._unpack(state)
        self.manager.restore_cartridge_definitions(definitions)
        self.participant.apply(data, branch_id=branch_id)
