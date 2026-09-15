from __future__ import annotations

import sys
import unittest
from concurrent.futures import Future
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


PROJECT_SRC = Path(__file__).resolve().parents[2]
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from controllers.local_voice_controller import LocalVoiceController
from core.events import Event, Events


class LocalVoiceControllerLifecycleTests(unittest.TestCase):
    def test_constructing_proxy_does_not_start_tts_worker(self):
        with patch.object(LocalVoiceController, "_subscribe_to_events"), patch.object(
            LocalVoiceController,
            "_get_engine",
            side_effect=AssertionError("constructor must not acquire the AI engine"),
        ):
            LocalVoiceController()

    def test_regular_initialized_check_reads_cache_without_tts_rpc(self):
        controller = LocalVoiceController.__new__(LocalVoiceController)
        controller._initialized_cache = {"medium+": True}
        controller._get_engine = lambda: self.fail(
            "a read-only initialized check must not start the TTS worker"
        )

        self.assertTrue(controller.check_initialized("medium+"))
        self.assertFalse(controller.check_initialized("high"))

    def test_selecting_initialized_model_preserves_confirmed_cache_state(self):
        controller = LocalVoiceController.__new__(LocalVoiceController)
        controller._initialized_cache = {"high_clf5": True}
        controller._save_setting = lambda *_args: None

        selected = controller._on_select_voice_model(
            Event(Events.Audio.SELECT_VOICE_MODEL, {"model_id": "high_clf5"})
        )

        self.assertTrue(selected)
        self.assertTrue(controller._initialized_cache["high_clf5"])


class _EventBusStub:
    def __init__(self) -> None:
        self.emitted = []

    def emit(self, name, data=None):
        self.emitted.append((name, data))


class LocalVoiceControllerReinitializeTests(unittest.IsolatedAsyncioTestCase):
    async def test_reinitialize_restarts_tts_before_model_init(self):
        controller = LocalVoiceController.__new__(LocalVoiceController)
        controller.event_bus = _EventBusStub()
        controller._model_configs_cache = [object()]
        controller._initialized_cache = {"high": True, "other": True}
        controller._triton_status_cache = {"cached": True}
        order = []

        class Engine:
            def restart_service(self, service, timeout=0):
                order.append(("restart", service, timeout))
                return True

        controller._get_engine = lambda: Engine()

        async def ensure(model_id, *, initialize=False):
            order.append(("init", model_id, initialize))

        controller._ensure_model_environment = ensure

        await controller._async_reinit_model("high")

        self.assertEqual(order, [("restart", "tts", 20.0), ("init", "high", True)])
        self.assertIsNone(controller._model_configs_cache)
        self.assertEqual(controller._triton_status_cache, None)
        self.assertEqual(controller._initialized_cache, {"high": True})
        self.assertIn((Events.Audio.FINISH_MODEL_LOADING, {"model_id": "high"}), controller.event_bus.emitted)

    async def test_reinitialize_stops_if_tts_restart_fails(self):
        controller = LocalVoiceController.__new__(LocalVoiceController)
        controller.event_bus = _EventBusStub()
        controller._model_configs_cache = None
        controller._initialized_cache = {"high": True}
        controller._triton_status_cache = None
        controller._get_engine = lambda: SimpleNamespace(
            restart_service=lambda *_args, **_kwargs: False
        )
        init_calls = []

        async def ensure(*_args, **_kwargs):
            init_calls.append(True)

        controller._ensure_model_environment = ensure

        await controller._async_reinit_model("high")

        self.assertEqual(init_calls, [])
        self.assertFalse(controller._initialized_cache["high"])
        self.assertTrue(any(name == Events.Audio.CANCEL_MODEL_LOADING for name, _ in controller.event_bus.emitted))


class LocalVoiceControllerSynthesisTests(unittest.IsolatedAsyncioTestCase):
    async def test_engine_timeout_has_actionable_message(self):
        controller = LocalVoiceController.__new__(LocalVoiceController)
        pending = Future()
        controller._get_engine = lambda: SimpleNamespace(
            call=lambda *_args, **_kwargs: pending
        )

        with self.assertRaisesRegex(
            TimeoutError,
            "Local TTS request 'synthesize' timed out after 0.01 seconds",
        ):
            await controller._engine_call_async("synthesize", timeout=0.01)

    async def test_uninitialized_model_does_not_start_on_demand_initialization(self):
        controller = LocalVoiceController.__new__(LocalVoiceController)
        controller._initialized_cache = {}
        controller._get_setting = lambda key, default=None: {
            "NM_CURRENT_VOICEOVER": "medium+",
        }.get(key, default)
        environment_calls = []

        async def ensure_environment(model_id, *, initialize=False):
            environment_calls.append((model_id, initialize))

        controller._ensure_model_environment = ensure_environment

        with self.assertRaisesRegex(RuntimeError, "Initialize it explicitly"):
            await controller.synthesize("hello")

        self.assertEqual(environment_calls, [])

    async def test_enabled_on_demand_initialization_runs_before_synthesis(self):
        controller = LocalVoiceController.__new__(LocalVoiceController)
        controller._initialized_cache = {}
        controller._get_setting = lambda key, default=None: {
            "NM_CURRENT_VOICEOVER": "medium+",
            "LOCAL_VOICE_INIT_ON_REQUEST": True,
        }.get(key, default)
        controller.event_bus = _EventBusStub()
        environment_calls = []

        async def ensure_environment(model_id, *, initialize=False):
            environment_calls.append((model_id, initialize))

        async def engine_call(_method, _payload=None, *, timeout=None):
            return "voice.wav"

        controller._ensure_model_environment = ensure_environment
        controller._engine_call_async = engine_call
        registry = SimpleNamespace(current_profile=lambda: None, get=lambda _id: None)

        with patch("controllers.local_voice_controller.use", return_value=registry):
            result = await controller.synthesize("hello")

        self.assertEqual(result, "voice.wav")
        self.assertEqual(environment_calls, [("medium+", True), ("medium+", False)])
        self.assertTrue(controller._initialized_cache["medium+"])


async def _completed(value):
    return value


if __name__ == "__main__":
    unittest.main()
