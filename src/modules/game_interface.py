from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Protocol
import threading
import queue
from time import monotonic
from core.state_barrier import bind_state_job
from modules.session_snapshot import snapshot_request, validate_game_state


class GameHost(Protocol):
    def publish_event(self, game: "GameInterface", name: str, payload: Dict[str, Any]) -> str | None: ...

    def request_character_reaction(
        self,
        game: "GameInterface",
        instruction: str,
        *,
        visible: bool = True,
        event_id: str | None = None,
    ) -> bool: ...


class GameInterface(ABC):
    """Абстрактный базовый класс для всех игр."""

    def __init__(self, character, game_id: str, host: Optional[GameHost] = None):
        self.character = character
        self.game_id = game_id
        self.host = host
        from domain.timeline import new_id
        self.instance_id = new_id()
        self.timeline_selection = None
        self.snapshot_queue = None
        self._session_snapshot = None
        self._session_generation = 0

    def accepts_state(self, state):
        return not isinstance(state, dict) or state.get("_session_generation", 0) == self._session_generation

    @property
    def snapshot_paused(self):
        return self._session_snapshot is not None

    @property
    def process_alive(self):
        process = getattr(self, "gui_process", None) or getattr(self, "gui_thread", None)
        return process is not None and process.is_alive()

    def start_notification_listener(self):
        target = (getattr(self, "_listen_for_player_move_reactions", None)
                  or getattr(self, "_listen_for_player_target_reactions"))
        self._reaction_stop_event.clear()
        self._reaction_listener = threading.Thread(target=bind_state_job(target),
            name=f"GameNotifications-{self.character.char_id}", daemon=True)
        self._reaction_listener.start()

    def pause_for_snapshot(self):
        self._reaction_stop_event.set()
        listener = self._reaction_listener
        if listener is not None and listener is not threading.current_thread():
            listener.join(timeout=2)
            if listener.is_alive():
                raise TimeoutError("Game notification listener did not pause")
        try:
            identity, response = snapshot_request(self.command_queue, self.snapshot_queue, "session_pause", details=True)
            state = response["state"]
            self._session_generation = response["generation"]
            deadline = monotonic() + 15
            while True:
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise TimeoutError("Game notification barrier did not arrive")
                event = self.reaction_queue.get(timeout=remaining)
                if event.get("event") == "session_barrier" and event.get("request_id") == identity:
                    break
                if event.get("event") != "session_barrier":
                    self._handle_reaction_event(dict(event, react=False))
            validate_game_state(self.game_id, state)
            self._session_snapshot = state
        except BaseException:
            try:
                snapshot_request(self.command_queue, self.snapshot_queue, "session_resume", timeout=2)
            finally:
                self.start_notification_listener()
            raise

    def resume_from_snapshot(self):
        snapshot_request(self.command_queue, self.snapshot_queue, "session_resume")
        self._session_snapshot = None
        self.start_notification_listener()

    def capture_paused_snapshot(self):
        if self._session_snapshot is None:
            raise RuntimeError("Exact game snapshots require an acknowledged process pause")
        return {"game_id": self.game_id, "instance_id": self.instance_id, "state": self._session_snapshot}

    def apply_paused_snapshot(self, state):
        validate_game_state(self.game_id, state)
        _identity, response = snapshot_request(self.command_queue, self.snapshot_queue, "session_restore", state=state, details=True)
        restored = response["state"]
        if restored != state:
            raise RuntimeError("The game process did not restore the exact requested snapshot")
        self._session_snapshot = restored
        self._session_generation = response["generation"]
        for attribute in ("_last_state", "_last_state_data"):
            if hasattr(self, attribute):
                setattr(self, attribute, None)
        if self.game_id == "chess":
            self.current_elo, self.is_auto, self.is_cheat = state["elo"], state["is_auto"], state["is_cheat"]
        if self.state_queue is not None:
            while True:
                try:
                    self.state_queue.get_nowait()
                except queue.Empty:
                    break
        self.command_queue.put({"action": "get_state"})

    def publish_event(self, name: str, payload: Dict[str, Any] | None = None) -> str | None:
        publisher = getattr(self.host, "publish_event", None)
        return publisher(self, name, payload or {}) if callable(publisher) else None

    def request_character_reaction(self, instruction: str, *, visible: bool = True, event_id: str | None = None) -> bool:
        """Ask the owning game host to initiate a character reaction."""
        if self.host is None:
            return False
        options = {"visible": visible}
        if event_id is not None:
            options["event_id"] = event_id
        return bool(self.host.request_character_reaction(self, instruction, **options))

    @abstractmethod
    def start(self, params: Dict[str, Any]):
        """Запускает игру с заданными параметрами."""
        pass

    @abstractmethod
    def stop(self, params: Dict[str, Any]):
        """Останавливает игру."""
        pass

    @abstractmethod
    def process_llm_tags(self, response: str) -> str:
        """Обрабатывает специфичные для игры теги из ответа LLM."""
        pass

    @abstractmethod
    def cleanup(self):
        """Очищает все ресурсы, связанные с игрой."""
        pass

    @abstractmethod
    def get_state_prompt(self) -> Optional[str]:
        """Формирует системный промпт с текущим состоянием игры."""
        pass

    def process_structured_commands(self, commands: List[str]):
        """Обрабатывает команды из structured response. По умолчанию — no-op."""
        pass
