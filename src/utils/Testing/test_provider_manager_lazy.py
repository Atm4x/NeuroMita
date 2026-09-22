from __future__ import annotations

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from managers.provider_manager import ProviderManager


class LazyProviderManagerTests(TestCase):
    def test_lazy_manager_registers_only_provider_selected_for_first_request(self):
        manager = ProviderManager.__new__(ProviderManager)
        manager._providers = []
        manager._unavailable = {}
        manager._provider_names = ("common", "gemini")
        manager._lazy = True
        manager.http_transport = object()
        common = SimpleNamespace(name="common", priority=1)
        provider_type = type("CommonProvider", (), {"__init__": lambda self, http_transport: None})
        provider_type.name = "common"
        provider_type.priority = 1

        with patch("managers.provider_manager.import_module") as load:
            load.return_value = SimpleNamespace(CommonProvider=provider_type)
            selected = manager._find_by_name("common")
            self.assertEqual(selected.name, "common")
            self.assertEqual(manager.provider_names, ("common",))
            self.assertEqual(load.call_count, 1)
            self.assertIsNone(manager._find_by_name("openai"))
            self.assertEqual(load.call_count, 1)


if __name__ == "__main__":
    import unittest

    unittest.main()
