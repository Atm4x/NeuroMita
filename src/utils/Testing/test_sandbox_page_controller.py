import unittest
from unittest.mock import patch

from controllers.gui.sandbox_page_controller import SandboxPageController


class SandboxPageControllerTest(unittest.TestCase):
    def _controller(self, settings_values, current_id=11):
        class Settings:
            def get(self, key, default=None):
                return settings_values.get(key, default)

        class Presets:
            def current_id(self):
                return current_id

            def list_meta(self):
                return {"custom": [], "builtin": []}

        controller = SandboxPageController()
        patches = (
            patch.object(controller, "current_character_id", return_value="Crazy"),
            patch("controllers.gui.sandbox_page_controller.services", return_value=type("Services", (), {"get_optional": lambda _self, _service: Presets()})()),
            patch("controllers.gui.sandbox_page_controller.use", return_value=Settings()),
        )
        return controller, patches

    def test_model_snapshot_uses_character_provider_override(self):
        controller, patches = self._controller({"CHAR_PROVIDER_Crazy": 42})
        with patches[0], patches[1], patches[2]:
            _meta, preset_id = controller.model_snapshot("Crazy")
        self.assertEqual(preset_id, 42)

    def test_model_snapshot_inherits_current_preset(self):
        controller, patches = self._controller(
            {"CHAR_PROVIDER_Crazy": -1, "LAST_API_PRESET_ID": 17},
            current_id=11,
        )
        with patches[0], patches[1], patches[2]:
            _meta, preset_id = controller.model_snapshot("Crazy")
        self.assertEqual(preset_id, 17)

    def test_model_snapshot_does_not_fall_back_to_service_startup_value(self):
        controller, patches = self._controller(
            {"CHAR_PROVIDER_Crazy": -1, "LAST_API_PRESET_ID": 42},
            current_id=None,
        )
        with patches[0], patches[1], patches[2]:
            _meta, preset_id = controller.model_snapshot("Crazy")
        self.assertEqual(preset_id, 42)


if __name__ == "__main__":
    unittest.main()
