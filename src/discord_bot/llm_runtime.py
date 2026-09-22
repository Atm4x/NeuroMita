from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from core.events import get_event_bus

class DiscordLLMRuntime:
    """Minimal owner for the existing NeuroMita preset and provider pipeline."""

    def __init__(self, *, data_dir: Path | None = None) -> None:
        self.data_dir = (data_dir or Path(os.environ.get("NEUROMITA_DISCORD_DATA_DIR", "DiscordData"))).resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._previous_base_dir = os.environ.get("NEUROMITA_BASE_DIR")
        self._previous_event_bus = None
        self._previous_contracts = {}
        self._contracts = ()
        self._registered_contracts = []
        self._previous_settings_manager = None
        self._previous_system_settings = None
        self._closed = False
        os.environ["NEUROMITA_BASE_DIR"] = str(self.data_dir)

        self.event_bus = None
        self.settings_controller = None
        self.presets_controller = None
        self.runner = None
        try:
            from controllers.api_presets_controller import ApiPresetsController
            from controllers.protocols_controller import ProtocolsController
            from core.services import services
            from managers.api_preset_resolver import ApiPresetResolver
            from managers.llm_request_runner import LLMRequestRunner
            from managers.model_config_loader import ModelConfigLoader
            from model_settings.service import ModelSettingsService
            from services.contracts import ApiPresetService, ProtocolBuilderService, SettingsService

            self._contracts = (ApiPresetService, ProtocolBuilderService, SettingsService)
            from core.events import _global_event_bus
            from core.services import services
            from managers.settings_manager import SettingsManager

            self._previous_event_bus = _global_event_bus
            self._previous_contracts = {
                contract: services().get_optional(contract)
                for contract in self._contracts
            }
            self._previous_settings_manager = SettingsManager.instance
            self.event_bus = get_event_bus(dispatcher_lanes=1)
            self.settings_controller = self._create_settings_controller()
            self._registered_contracts.append(SettingsService)
            self.settings = services().get(SettingsService)
            self.protocols_controller = ProtocolsController()
            services().register(ProtocolBuilderService, self.protocols_controller, replace=True)
            self._registered_contracts.append(ProtocolBuilderService)
            self.model_settings = ModelSettingsService(persist_defaults=False)
            self.presets_controller = ApiPresetsController(
                model_settings_service=self.model_settings,
                legacy_generation_settings=self.settings,
                migrate_legacy_settings=False,
            )
            services().register(ApiPresetService, self.presets_controller, replace=True)
            self._registered_contracts.append(ApiPresetService)

            self.preset_resolver = ApiPresetResolver(
                settings=self.settings,
                event_bus=self.event_bus,
                model_settings_service=self.model_settings,
            )
            self.config_loader = ModelConfigLoader(self.settings)
            self.config = self.config_loader.load()
            self.runner = LLMRequestRunner(
                settings=self.settings,
                preset_resolver=self.preset_resolver,
                event_bus=self.event_bus,
                provider_names=("openai", "gemini", "common", "g4f"),
                lazy_providers=True,
            )
        except Exception:
            self.close()
            raise

    def _create_settings_controller(self):
        from controllers.settings_controller import SettingsController

        return SettingsController(
            self.data_dir / "Settings" / "settings.json",
            dispatcher_lanes=1,
        )

    def generate(self, messages: list[dict[str, Any]], preset_id: int | None = None):
        if self._closed:
            raise RuntimeError("Discord LLM runtime is closed")

        chain = self.preset_resolver.resolve_chain(preset_id)
        configured = [
            preset for preset in chain
            if preset.api_key.strip()
            and preset.api_url.strip()
            and preset.api_model.strip()
            and preset.provider_name.strip()
        ]
        if not configured:
            from handlers.llm_providers.base import LLMResponse

            return LLMResponse(
                text=None,
                error_message="No configured API preset. Add an API preset with endpoint, model, and key under DiscordData/Settings/api_presets.json.",
            )

        def build_request(preset, model: str):
            config = self.config_loader.effective_for_preset(self.config, preset, model)
            if preset.native_parameters is not None:
                parameters = {}
            else:
                from handlers.llm_providers.param_mapper import build_unified_generation_params

                parameters = build_unified_generation_params(
                    settings=self.settings,
                    temperature=config.temperature,
                    max_response_tokens=config.max_response_tokens,
                    presence_penalty=config.presence_penalty,
                    frequency_penalty=config.frequency_penalty,
                    log_probability=config.log_probability,
                    top_k=config.top_k,
                    top_p=config.top_p,
                    thinking_budget=config.thinking_budget,
                    enable_thinking=config.enable_thinking,
                    reasoning_effort=config.reasoning_effort,
                    gemini_thinking_budget=config.gemini_thinking_budget,
                    force_params=config.preset_forced_params,
                )

            from handlers.llm_providers.base import LLMRequest

            return LLMRequest(
                model=model,
                messages=messages,
                api_key=preset.api_key,
                api_url=preset.api_url,
                protocol_id=preset.protocol_id,
                dialect_id=preset.dialect_id,
                provider_name=preset.provider_name,
                provider_display_name=preset.provider_display_name,
                headers=dict(preset.headers or {}),
                transforms=list(preset.transforms or []),
                capabilities=dict(preset.capabilities or {}),
                stream=False,
                tools_on=False,
                extra={**parameters, "http_timeout_seconds": float(self.settings.get("DISCORD_LLM_TIMEOUT", 120))},
                native_parameters=preset.native_parameters,
                settings=self.settings,
            )

        return self.runner.run(
            messages=messages,
            preset_id=preset_id,
            stream_callback=None,
            build_request=build_request,
            max_attempts=max(1, int(self.settings.get("DISCORD_LLM_RETRIES", 2))),
            retry_delay=float(self.settings.get("DISCORD_LLM_RETRY_DELAY", 1.0)),
            request_timeout=max(1.0, float(self.settings.get("DISCORD_LLM_TIMEOUT", 120))),
            suppress_failure_events=True,
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self.runner is not None:
            self.runner.close()
        if self.presets_controller is not None:
            self.presets_controller.close()
        if self.event_bus is not None:
            for owner in (self.presets_controller, getattr(self, "protocols_controller", None), self.settings_controller):
                if owner is not None:
                    self.event_bus.unsubscribe_owner(owner)
        if self._contracts:
            import core.events as event_module
            from core.executor_registry import executors
            from core.services import services
            from managers.settings_manager import SettingsManager
            from services.contracts import ApiPresetService, ProtocolBuilderService, SettingsService

            for contract in reversed(self._registered_contracts):
                services().unregister(contract)
            if self._previous_contracts.get(ApiPresetService) is not None:
                services().register(ApiPresetService, self._previous_contracts[ApiPresetService], replace=True)
            if self._previous_contracts.get(ProtocolBuilderService) is not None:
                services().register(ProtocolBuilderService, self._previous_contracts[ProtocolBuilderService], replace=True)
            if self._previous_contracts.get(SettingsService) is not None:
                services().register(SettingsService, self._previous_contracts[SettingsService], replace=True)
            if self.event_bus is not None and self._previous_event_bus is None:
                with event_module._event_bus_lifecycle_lock:
                    if event_module._global_event_bus is self.event_bus:
                        self.event_bus.shutdown()
                        event_module._global_event_bus = self._previous_event_bus
            executors().shutdown_all(wait=False)
        if self.settings_controller is not None:
            self.settings_controller.settings.close()
            from managers.settings_manager import SettingsManager

            if SettingsManager.instance is self.settings_controller.settings:
                SettingsManager.instance = self._previous_settings_manager
        if self._previous_base_dir is None:
            os.environ.pop("NEUROMITA_BASE_DIR", None)
        else:
            os.environ["NEUROMITA_BASE_DIR"] = self._previous_base_dir
