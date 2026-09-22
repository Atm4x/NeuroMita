from __future__ import annotations
from core.error_utils import format_exception

from importlib import import_module
from typing import List, Optional

from main_logger import logger
from handlers.llm_providers.base import BaseProvider, LLMRequest, LLMResponse
from handlers.llm_providers.message_preprocessor import preprocess_messages_for_provider
from handlers.llm_providers.message_transforms import apply_transforms
from handlers.llm_providers.http_transport import LLMHttpClient


_PROVIDER_TYPES = {
    "openai": ("handlers.llm_providers.openai_provider", "OpenAIProvider"),
    "gemini": ("handlers.llm_providers.gemini_provider", "GeminiProvider"),
    "common": ("handlers.llm_providers.common_provider", "CommonProvider"),
    "g4f": ("handlers.llm_providers.g4f_provider", "G4FProvider"),
}


class ProviderManager:
    def __init__(
        self,
        provider_names: tuple[str, ...] | None = None,
        *,
        lazy: bool = False,
    ):
        self._providers: List[BaseProvider] = []
        self._unavailable: dict[str, str] = {}
        self.http_transport = LLMHttpClient(enable_http2=True)
        self._provider_names = provider_names
        self._lazy = bool(lazy)
        if not self._lazy:
            self._register_providers(provider_names)

    @property
    def provider_names(self) -> tuple[str, ...]:
        return tuple(str(provider.name) for provider in self._providers)

    def _register_providers(self, provider_names: tuple[str, ...] | None = None):
        providers: list[BaseProvider] = []
        unavailable: dict[str, str] = {}

        selected = tuple(_PROVIDER_TYPES) if provider_names is None else tuple(provider_names)
        for name in selected:
            target = _PROVIDER_TYPES.get(name)
            if target is None:
                unavailable[str(name)] = "Unknown provider"
                continue
            module_name, class_name = target
            try:
                provider_type = getattr(import_module(module_name), class_name)
                providers.append(provider_type(http_transport=self.http_transport))
            except Exception as exc:
                unavailable[class_name] = format_exception(exc)
                logger.warning(f"LLM provider {class_name} unavailable: {format_exception(exc)}")

        providers.sort(key=lambda provider: provider.priority)
        self._providers = providers
        self._unavailable = unavailable
        logger.info(
            f"Registered {len(self._providers)} providers: "
            f"{[provider.name for provider in self._providers]}"
        )

    def _find_by_name(self, name: str) -> Optional[BaseProvider]:
        if not name:
            return None
        for provider in self._providers:
            if getattr(provider, "name", None) == name:
                return provider
        if self._lazy:
            target = _PROVIDER_TYPES.get(str(name))
            if target is None or (self._provider_names is not None and name not in self._provider_names):
                return None
            module_name, class_name = target
            try:
                provider_type = getattr(import_module(module_name), class_name)
                provider = provider_type(http_transport=self.http_transport)
                self._providers.append(provider)
                self._providers.sort(key=lambda item: item.priority)
                return provider
            except Exception as exc:
                self._unavailable[class_name] = format_exception(exc)
                logger.warning("LLM provider %s unavailable: %s", class_name, format_exception(exc))
        return None

    def _enforce_capabilities(self, req: LLMRequest) -> None:
        caps = req.capabilities or {}

        if "streaming" in caps and not bool(caps.get("streaming")):
            req.stream = False

        if req.tools_on and req.tools_mode == "native":
            if "tools_native" in caps and not bool(caps.get("tools_native")):
                req.tools_on = False

            if req.stream and ("streaming_with_tools" in caps) and not bool(caps.get("streaming_with_tools")):
                req.stream = False

    def generate(self, req: LLMRequest) -> LLMResponse:
        if not req.provider_name:
            logger.error("Protocol-driven routing requires provider_name in request")
            raise RuntimeError("No provider can handle this request")

        provider = self._find_by_name(req.provider_name)
        if not provider:
            details = "; ".join(f"{name}: {format_exception(error)}" for name, error in self._unavailable.items())
            logger.error(f"No provider registered with name '{req.provider_name}'. {details}")
            raise RuntimeError(f"Provider '{req.provider_name}' is unavailable")

        self._enforce_capabilities(req)

        trace = {
            "protocol_id": req.protocol_id,
            "dialect_id": req.dialect_id,
            "provider_name": req.provider_name,
            "provider_display_name": req.provider_display_name,
            "transforms": req.transforms or [],
            "transform_trace": [],
        }

        req.extra["_protocol_trace"] = trace

        logger.info(
            f"Using provider: {req.provider_display_name or provider.name} "
            f"| transport={provider.name} | protocol={req.protocol_id} | dialect={req.dialect_id}"
        )

        preprocess_messages_for_provider(req, provider)

        if req.transforms:
            req.messages, transform_trace = apply_transforms(req.messages, req.transforms)
            trace["transform_trace"] = transform_trace

        logger.debug(f"Protocol trace: {trace}")
        return provider.generate(req)

    def close(self) -> None:
        providers = tuple(self._providers)
        self._providers.clear()
        for provider in providers:
            try:
                provider.close()
            except Exception:
                logger.debug("Failed to close LLM provider %s", provider.name, exc_info=True)
        self.http_transport.close()
