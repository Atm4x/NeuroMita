from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import httpx
from unittest.mock import patch
import json

from core.events import get_event_bus, reset_event_bus


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))


class DiscordLlmSmokeTests(unittest.TestCase):
    def test_runtime_uses_existing_resolver_runner_and_non_streaming_requests(self):
        from discord_bot.llm_runtime import DiscordLLMRuntime

        with tempfile.TemporaryDirectory() as data_dir:
            Path(data_dir, "settings.json").write_text("{}", encoding="utf-8")
            prior_base = os.environ.get("NEUROMITA_BASE_DIR")
            configured_preset = type("Preset", (), {
                "api_key": "secret",
                "api_url": "https://example.invalid/v1/chat/completions",
                "api_model": "test-model",
                "provider_name": "common",
            })()
            with (
                patch.dict(os.environ, {"NEUROMITA_BASE_DIR": str(Path(data_dir) / "unrelated")}),
                patch("managers.llm_request_runner.LLMRequestRunner.run") as run,
                patch("managers.api_preset_resolver.ApiPresetResolver.resolve_chain", return_value=[configured_preset]),
            ):
                run.return_value = type("Response", (), {"text": "pong"})()
                runtime = DiscordLLMRuntime(data_dir=Path(data_dir))
                try:
                    self.assertEqual(os.environ["NEUROMITA_BASE_DIR"], str(Path(data_dir).resolve()))
                    response = runtime.generate([
                        {"role": "system", "content": "You are a bot."},
                        {"role": "user", "content": "ping"},
                    ])
                finally:
                    runtime.close()
                self.assertEqual(os.environ["NEUROMITA_BASE_DIR"], str(Path(data_dir) / "unrelated"))
                self.assertTrue(get_event_bus().is_running)
            if prior_base is None:
                os.environ.pop("NEUROMITA_BASE_DIR", None)
            else:
                os.environ["NEUROMITA_BASE_DIR"] = prior_base

        self.assertEqual(response.text, "pong")
        kwargs = run.call_args.kwargs
        self.assertEqual(kwargs["messages"][-1]["content"], "ping")
        request = kwargs["build_request"](type("Preset", (), {
            "native_parameters": None,
            "generation_overrides": {},
            "capabilities": {},
            "api_key": "secret",
            "api_url": "https://example.invalid/v1/chat/completions",
            "protocol_id": "openai_compatible_default",
            "dialect_id": "openai_chat_completions",
            "provider_name": "common",
            "provider_display_name": "Common API",
            "headers": {},
            "transforms": [],
        })(), "test-model")
        self.assertFalse(request.stream)
        self.assertFalse(request.tools_on)
        self.assertEqual(request.model, "test-model")

    def test_cli_runtime_rejects_unconfigured_presets_without_starting_provider(self):
        from discord_bot.llm_runtime import DiscordLLMRuntime
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as data_dir:
            with patch("managers.llm_request_runner.LLMRequestRunner.run") as run:
                runtime = DiscordLLMRuntime(data_dir=Path(data_dir))
                try:
                    result = runtime.generate([{"role": "user", "content": "ping"}])
                finally:
                    runtime.close()

        self.assertIsNone(result.text)
        self.assertIn("No configured API preset", result.error_message)
        run.assert_not_called()

    def test_import_does_not_load_heavy_desktop_or_media_modules(self):
        script = (
            "import sys; from discord_bot.llm_runtime import DiscordLLMRuntime; "
            "forbidden = {'PyQt6', 'torch', 'transformers', 'cv2', 'pygame', 'pyaudio'}; "
            "loaded = forbidden.intersection(sys.modules); "
            "assert not loaded, sorted(loaded)"
        )
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(SRC_ROOT)
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=PROJECT_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_runtime_creates_only_the_selected_provider_and_closes_owned_workers(self):
        from discord_bot.llm_runtime import DiscordLLMRuntime
        from core.services import services
        from core.services import ServiceNotRegistered
        from core.events import get_event_bus
        from core.executor_registry import executors
        from managers.settings_manager import SettingsManager
        from services.contracts import ApiPresetService, SettingsService
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as data_dir:
            with patch("managers.provider_manager.ProviderManager._register_providers"):
                runtime = DiscordLLMRuntime(data_dir=Path(data_dir))
            try:
                self.assertTrue(runtime.runner.provider_manager._lazy)
                self.assertEqual(runtime.runner.provider_manager.provider_names, ())
                self.assertFalse((Path(data_dir) / "Settings" / "APIModelSchemas").exists())
                self.assertTrue(get_event_bus().is_running)
            finally:
                runtime.close()
            self.assertEqual(executors()._pools, {})
            self.assertIsNone(SettingsManager.instance)
            self.assertRaises(ServiceNotRegistered, services().get, ApiPresetService)
            self.assertRaises(ServiceNotRegistered, services().get, SettingsService)

    def test_cli_module_exists_without_connecting_to_discord(self):
        from discord_bot import test_llm as module

        self.assertTrue(callable(module.main))

    def test_runtime_reuses_existing_retry_key_rotation_and_fallback_pipeline(self):
        from discord_bot.llm_runtime import DiscordLLMRuntime
        from managers.api_preset_resolver import PresetSettings
        from managers.provider_manager import ProviderManager
        from handlers.llm_providers.http_transport import LLMHttpClient

        requested_keys = []

        def respond(request):
            authorization = request.headers.get("Authorization", "")
            requested_keys.append(authorization.removeprefix("Bearer "))
            if len(requested_keys) <= 2:
                return httpx.Response(429, json={"error": {"message": "rate limited"}}, headers={"Retry-After": "0"})
            return httpx.Response(200, json={
                "model": "fallback-model",
                "choices": [{"message": {"content": "fallback response"}, "finish_reason": "stop"}],
            })

        client = httpx.Client(transport=httpx.MockTransport(respond))
        transport = LLMHttpClient(
            enable_http2=False,
            client_factory=lambda _service_id, _http2: client,
        )
        primary = PresetSettings(
            protocol_id="openai_compatible_default",
            dialect_id="openai_chat_completions",
            provider_name="common",
            provider_display_name="Primary",
            headers={},
            transforms=[],
            capabilities={"streaming": True},
            api_key="primary-key",
            api_url="https://primary.test/v1/chat/completions",
            api_model="primary-model",
            preset_name="Primary",
            reserve_keys=["reserve-key"],
        )
        fallback = PresetSettings(
            protocol_id="openai_compatible_default",
            dialect_id="openai_chat_completions",
            provider_name="common",
            provider_display_name="Fallback",
            headers={},
            transforms=[],
            capabilities={"streaming": True},
            api_key="fallback-key",
            api_url="https://fallback.test/v1/chat/completions",
            api_model="fallback-model",
            preset_name="Fallback",
            reserve_keys=[],
        )

        with tempfile.TemporaryDirectory() as data_dir:
            runtime = DiscordLLMRuntime(data_dir=Path(data_dir))
            runtime.runner.provider_manager.close()
            runtime.runner.provider_manager = ProviderManager(
                provider_names=("common",), lazy=True
            )
            runtime.runner.provider_manager.http_transport.close()
            runtime.runner.provider_manager.http_transport = transport
            runtime.preset_resolver.resolve_chain = lambda _preset_id: [primary, fallback]
            runtime.preset_resolver._build_http_request_via_protocols_controller = (
                lambda protocol_id, url, api_key, extra_headers=None: (url, {"Authorization": f"Bearer {api_key}"})
            )
            runtime.settings.set("DISCORD_LLM_RETRIES", 2)
            runtime.settings.set("DISCORD_LLM_RETRY_DELAY", 0)
            runtime.runner._call_with_timeout = lambda func, args=(), kwargs=None, **_options: func(
                *args, **(kwargs or {})
            )
            try:
                response = runtime.generate([{"role": "user", "content": "ping"}])
            finally:
                runtime.close()

        self.assertEqual(response.text, "fallback response")
        self.assertEqual(requested_keys, ["primary-key", "reserve-key", "fallback-key"])

    def test_preset_bootstrap_does_not_migrate_or_delete_desktop_legacy_settings(self):
        from discord_bot.llm_runtime import DiscordLLMRuntime

        with tempfile.TemporaryDirectory() as data_dir:
            settings_dir = Path(data_dir, "Settings")
            settings_dir.mkdir()
            settings_file = settings_dir / "settings.json"
            settings_file.write_text(json.dumps({
                "NM_API_KEY": "desktop-secret",
                "NM_API_URL": "https://desktop.invalid",
            }), encoding="utf-8")
            with patch("core.app_paths.base_dir", return_value=Path(data_dir)):
                runtime = DiscordLLMRuntime(data_dir=Path(data_dir))
                try:
                    self.assertEqual(runtime.settings.get("NM_API_KEY"), "desktop-secret")
                    self.assertEqual(runtime.presets_controller.presets, {})
                    self.assertTrue(runtime.presets_controller.templates)
                    self.assertNotIn("NM_API_KEY", runtime.settings.get("api_presets", {}))
                finally:
                    runtime.close()
            persisted = json.loads(settings_file.read_text(encoding="utf-8"))
            self.assertEqual(persisted["NM_API_KEY"], "desktop-secret")


if __name__ == "__main__":
    unittest.main()
