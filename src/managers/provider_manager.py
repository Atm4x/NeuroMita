from __future__ import annotations

from importlib import import_module
from typing import List, Optional

from main_logger import logger
from handlers.llm_providers.base import BaseProvider, LLMRequest, LLMResponse
from handlers.llm_providers.message_preprocessor import preprocess_messages_for_provider
from handlers.llm_providers.message_transforms import apply_transforms
from handlers.llm_providers.http_transport import LLMHttpTransport


_PROVIDER_TYPES = (
    ("handlers.llm_providers.openai_provider", "OpenAIProvider"),
    ("handlers.llm_providers.gemini_provider", "GeminiProvider"),
    ("handlers.llm_providers.common_provider", "CommonProvider"),
    ("handlers.llm_providers.g4f_provider", "G4FProvider"),
)


class ProviderManager:
    def __init__(self):
        self._providers: List[BaseProvider] = []
        self._unavailable: dict[str, str] = {}
        self.http_transport = LLMHttpTransport(enable_http2=True)
        self._register_providers()

    def _register_providers(self):
        providers: list[BaseProvider] = []
        unavailable: dict[str, str] = {}

        for module_name, class_name in _PROVIDER_TYPES:
            try:
                provider_type = getattr(import_module(module_name), class_name)
                providers.append(provider_type(http_transport=self.http_transport))
            except Exception as exc:
                unavailable[class_name] = f"{type(exc).__name__}: {exc}"
                logger.warning(f"LLM provider {class_name} unavailable: {exc}")

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
        return None

    def _prepare_native_tools(self, req: LLMRequest, provider: BaseProvider) -> None:
        extra = req.extra or {}
        if extra.get("event_type") == "mcp_completion":
            req.tools_on = False
            req.tools_payload = None
            req.tools_dialect = None
            return
        if not bool(extra.get("tools_requested")):
            return
        if not req.tools_on or req.tools_mode != "native":
            req.tools_payload = None
            req.tools_dialect = None
            return

        tool_manager = req.tool_manager
        dialect_id = str(getattr(provider, "tools_dialect_id", "") or "").strip()
        if tool_manager is None or not dialect_id:
            logger.warning("Provider '%s' has no native tool dialect; disabling tools.", provider.name)
            req.tools_on = False
            req.tools_payload = None
            req.tools_dialect = None
            return

        try:
            req.tools_payload = tool_manager.get_tools_payload(
                dialect_id,
                enabled_names=extra.get("enabled_tool_names"),
            )
        except Exception as exc:
            logger.warning("Failed to build tools for provider '%s': %s", provider.name, exc)
            req.tools_on = False
            req.tools_payload = None
            req.tools_dialect = None
            return
        req.tools_dialect = dialect_id
        req.tools_on = bool(req.tools_payload)

    def _enforce_capabilities(self, req: LLMRequest, provider: BaseProvider) -> None:
        caps = req.capabilities or {}

        if "streaming" in caps and not bool(caps.get("streaming")):
            req.stream = False

        if req.tools_on and req.tools_mode == "native":
            if not bool(getattr(provider, "supports_tools_native", False)):
                req.tools_on = False
            elif "tools_native" in caps and not bool(caps.get("tools_native")):
                req.tools_on = False

            if req.stream and not bool(getattr(provider, "supports_streaming_with_tools", False)):
                req.stream = False
            elif req.stream and ("streaming_with_tools" in caps) and not bool(caps.get("streaming_with_tools")):
                req.stream = False

    def generate(self, req: LLMRequest) -> LLMResponse:
        if not req.provider_name:
            logger.error("Protocol-driven routing requires provider_name in request")
            raise RuntimeError("No provider can handle this request")

        provider = self._find_by_name(req.provider_name)
        if not provider:
            details = "; ".join(f"{name}: {error}" for name, error in self._unavailable.items())
            logger.error(f"No provider registered with name '{req.provider_name}'. {details}")
            raise RuntimeError(f"Provider '{req.provider_name}' is unavailable")

        self._enforce_capabilities(req, provider)
        self._prepare_native_tools(req, provider)

        trace = {
            "protocol_id": req.protocol_id,
            "dialect_id": req.dialect_id,
            "provider_name": req.provider_name,
            "transforms": req.transforms or [],
            "transform_trace": [],
        }

        req.extra["_protocol_trace"] = trace

        logger.info(
            f"Using provider: {provider.name} | protocol={req.protocol_id} | dialect={req.dialect_id}"
        )

        if not bool((req.extra or {}).get("_tool_loop_prepared", False)):
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
