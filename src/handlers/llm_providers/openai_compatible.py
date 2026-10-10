# src/handlers/llm_providers/openai_compatible.py
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from main_logger import logger
from .base import (
    BaseProvider,
    LLMRequest,
    LLMResponse,
    check_request_cancelled,
    record_response_body_started,
    register_cancellable_resource,
)
from .errors import build_provider_error, coerce_provider_error
from .message_transforms import trailing_system_to_user_prefix
from utils.openrouter_routing import (
    annotate_openrouter_prompt_cache,
    normalize_openrouter_routing,
)
from .protocols.chat_completions import ChatCompletionsAdapter
from .protocols.chat_completions.response import extract_usage, reasoning_text, sdk_payload


class OpenAICompatibleProvider(BaseProvider, ABC):
    supports_tools_native = True
    supports_streaming = True
    supports_streaming_with_tools = False

    tools_dialect_id: str = "openai"

    @abstractmethod
    def _get_client(self, req: LLMRequest) -> Any:
        pass

    def _get_model_to_use(self, req: LLMRequest) -> str:
        return req.model

    def _release_client(self, client: Any) -> None:
        close = getattr(client, "close", None)
        if callable(close):
            close()

    @staticmethod
    def _stringify_error(value: Any, limit: int = 400) -> str:
        try:
            if isinstance(value, str):
                text = value
            else:
                text = json.dumps(value, ensure_ascii=False)
        except Exception:
            text = str(value)

        text = (text or "").strip()
        return text[:limit]

    def generate(self, req: LLMRequest) -> LLMResponse:
        return self._generate(req)

    @staticmethod
    def _extract_sdk_reasoning(message: Any) -> str:
        return reasoning_text(sdk_payload(message))

    def _generate(self, req: LLMRequest) -> LLMResponse:
        if req.depth > 3:
            logger.error(f"Слишком много рекурсивных tool-вызовов ({self.name}).")
            return LLMResponse(
                text=None,
                provider_name=req.provider_name or self.name,
                provider_display_name=req.provider_display_name or req.provider_name or self.name,
                error_message="Too deep tool recursion.",
            )

        model_to_use = self._get_model_to_use(req)
        client = self._get_client(req)
        if not client:
            raise build_provider_error(
                self.name,
                provider_message="API client initialization returned no client.",
                url=req.api_url,
            )

        try:
            check_request_cancelled(req)
            adapter = self._protocol_adapter(model_to_use)
            params = adapter.encode(req, wire_stream=req.stream)

            check_request_cancelled(req)
            completion = client.chat.completions.create(**params)
            completion = register_cancellable_resource(req, completion)

            if req.stream:
                return self._handle_stream(completion, req, req.stream_cb)

            return adapter.decode(req, sdk_payload(completion) if completion is not None else {})

        except Exception as e:
            provider_error = coerce_provider_error(self.name, e, url=req.api_url)
            logger.debug(
                "[%s] Provider failure delegated to request runner: %s",
                self.name,
                provider_error.to_console_summary(),
            )
            raise provider_error from e
        finally:
            try:
                self._release_client(client)
            except Exception:
                logger.debug(f"[{self.name}] Failed to release provider client", exc_info=True)

    def _build_payload(self, req: LLMRequest, model_to_use: str) -> dict:
        cleaned_messages = [{k: v for k, v in m.items() if k != "time"} for m in (req.messages or [])]
        if req.protocol_id == "openrouter_default":
            if bool((req.extra or {}).get("openrouter_tail_system_to_user", True)):
                cleaned_messages = trailing_system_to_user_prefix(cleaned_messages, tag="[SYSTEM INFO]")
            cleaned_messages = annotate_openrouter_prompt_cache(cleaned_messages, model_to_use)

        params: Dict[str, Any] = {"model": model_to_use, "messages": cleaned_messages}
        if req.stream and self.should_request_stream_usage(req):
            params["stream_options"] = {"include_usage": True}
        if req.native_parameters is None:
            params.update(self._map_unified_params(req.extra or {}, model_to_use))
        else:
            from copy import deepcopy
            if req.dialect_id == "g4f":
                params.update(deepcopy(req.native_parameters))
            else:
                params["extra_body"] = deepcopy(req.native_parameters)
        if req.protocol_id == "openrouter_default":
            extra_body = dict(params.get("extra_body") or {})
            routing = normalize_openrouter_routing((req.extra or {}).get("openrouter_routing"))
            if routing:
                extra_body["provider"] = routing
            session_id = str((req.extra or {}).get("openrouter_session_id") or "").strip()
            if session_id:
                extra_body["session_id"] = session_id
            if extra_body:
                params["extra_body"] = extra_body

        return params

    def _protocol_adapter(self, model: Optional[str] = None) -> ChatCompletionsAdapter:
        return ChatCompletionsAdapter(
            provider_name=self.name,
            payload_builder=lambda req: self._build_payload(req, model or self._get_model_to_use(req)),
            supports_stream_usage=self.supports_stream_usage,
        )

    def _map_unified_params(self, unified: Dict[str, Any], model_to_use: str) -> Dict[str, Any]:
        u = unified or {}
        m = (model_to_use or "").lower()
        out: Dict[str, Any] = {}

        for k in ("temperature", "max_tokens", "presence_penalty", "frequency_penalty", "top_p"):
            if k in u:
                out[k] = u[k]

        if "top_k" in u and "deepseek" in m:
            out["top_k"] = u["top_k"]

        if "enable_thinking" in u:
            out["enable_thinking"] = bool(u["enable_thinking"])

        if "logprobs" in u:
            lp = u["logprobs"]
            out["logprobs"] = lp if isinstance(lp, bool) else bool(lp)

        return out

    def _handle_stream(self, completion, req: LLMRequest, stream_callback=None) -> LLMResponse:
        def chunks():
            for chunk in completion:
                record_response_body_started(req)
                check_request_cancelled(req)
                yield self._stream_chunk_payload(chunk)
        try:
            return self._protocol_adapter().consume_stream(req, chunks())
        except Exception as e:
            raise coerce_provider_error(self.name, e, url=req.api_url) from e
        finally:
            close = getattr(completion, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    logger.debug(f"[{self.name}] Failed to close provider stream", exc_info=True)

    @staticmethod
    def _stream_chunk_payload(chunk: Any) -> dict[str, Any]:
        return sdk_payload(chunk)

    def _extract_usage(self, usage_obj: Any):
        return extract_usage(LLMRequest(model="", messages=[]), {"usage": sdk_payload(usage_obj)})
