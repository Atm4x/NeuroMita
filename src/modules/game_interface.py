from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Protocol


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
