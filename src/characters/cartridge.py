from __future__ import annotations

from characters.character import Character
from domain.cartridge_catalog import CartridgeDefinition
from domain.character_runtime_profile import CharacterRuntimeProfile


class CartridgeCharacter(Character):
    """Virtual character using the standard model pipeline and character-scoped history."""

    runtime_profile = CharacterRuntimeProfile(
        rag_enabled=False, core_memory_enabled=False, tools_enabled=False,
        background_memory_enabled=False,
    )

    def __init__(self, definition: CartridgeDefinition):
        self.cartridge_definition = definition
        super().__init__(
            char_id=definition.character_id,
            display_name=definition.title,
            storage_name=definition.character_id,
            silero_command="",
            short_name=definition.title,
            is_cartridge=True,
            silero_turn_off_video=True,
        )

    def _resolve_prompt_set_name(self) -> str:
        return "Catalog"

    def _log_prompt_set_problems_if_any(self):
        return None

    def load_config(self):
        self.custom_params = []

    def to_voice_profile(self):
        return {**super().to_voice_profile(), "voice_enabled": False, "is_cartridge": True}

    def save_character_state_to_history(self, messages):
        super().save_character_state_to_history(messages[-self.cartridge_definition.history_messages:])

    def process_structured_response(self, structured, save_as_missed=False):
        from schemas.structured_response import ResponseSegment, StructuredResponse
        return StructuredResponse(segments=[ResponseSegment(text=segment.text, target=segment.target)
                                            for segment in structured.segments])

    def process_response_nlp_commands(self, response, save_as_missed=False):
        return response
