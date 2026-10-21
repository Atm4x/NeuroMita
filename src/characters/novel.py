from characters.character import Character
from domain.character_runtime_profile import CharacterRuntimeProfile


class TwoDMita(Character):
    DISPLAY_NAME = "2D Mita"
    STORAGE_NAME = "2D Mita"
    runtime_profile = CharacterRuntimeProfile(
        rag_enabled=False, core_memory_enabled=False, tools_enabled=False,
        background_memory_enabled=False, requires_structured_output=True,
        scene_context_key="novel",
        scene_context_fields=("player_room", "mita_room", "pose", "transform", "appearance"),
        history_message_limit=40,
    )

    def __init__(self):
        super().__init__(char_id="TwoD", display_name=self.DISPLAY_NAME, storage_name=self.STORAGE_NAME,
                         silero_command="", short_name="TwoDMita", silero_turn_off_video=True)

    def to_voice_profile(self):
        return {**super().to_voice_profile(), "voice_enabled": False}

    def process_structured_response(self, structured, save_as_missed=False):
        from domain.novel import sanitize_response
        return sanitize_response(structured)

    def process_response_nlp_commands(self, response, save_as_missed=False):
        return response
