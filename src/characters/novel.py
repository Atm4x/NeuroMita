from characters.character import Character


class TwoDMita(Character):
    DISPLAY_NAME = "2D Mita"
    STORAGE_NAME = "2D Mita"
    is_novel = True

    def __init__(self):
        super().__init__(char_id="TwoD", display_name=self.DISPLAY_NAME, storage_name=self.STORAGE_NAME,
                         silero_command="", short_name="TwoDMita", silero_turn_off_video=True)

    def _resolve_prompt_set_name(self):
        return "Builtin"

    def _log_prompt_set_problems_if_any(self):
        return None

    def load_config(self):
        self.custom_params = []

    def to_voice_profile(self):
        return {**super().to_voice_profile(), "voice_enabled": False}

    def save_character_state_to_history(self, messages):
        super().save_character_state_to_history(messages[-40:])

    def process_structured_response(self, structured, save_as_missed=False):
        from domain.novel import sanitize_response
        return sanitize_response(structured)

    def process_response_nlp_commands(self, response, save_as_missed=False):
        return response
