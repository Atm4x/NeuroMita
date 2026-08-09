from __future__ import annotations

import uuid
from typing import Any, Callable

from handlers.llm_providers.base import LLMRequest, LLMResponse, ToolCall
from main_logger import logger

from .models import ToolExecutionContext


class ToolCallExecutor:
    """Run provider tool calls until the provider returns a final response."""

    def __init__(self, *, max_depth: int = 4) -> None:
        self.max_depth = max(1, int(max_depth))

    def execute_until_final(
        self,
        generate_fn: Callable[[LLMRequest], LLMResponse],
        req: LLMRequest,
        *,
        context: ToolExecutionContext | None = None,
    ) -> LLMResponse:
        context = context or ToolExecutionContext.from_request(req)
        req.messages = list(req.messages or [])
        response = generate_fn(req)
        total_usage = response.usage if response is not None else None
        round_index = 0

        while response is not None and response.tool_calls:
            if round_index >= self.max_depth:
                return LLMResponse(
                    text=None,
                    usage=total_usage,
                    model=response.model or req.model,
                    provider_name=response.provider_name or req.provider_name,
                    finish_reason=response.finish_reason,
                    error_message="Maximum tool-call depth reached.",
                )

            manager = req.tool_manager
            if manager is None:
                return LLMResponse(
                    text=None,
                    usage=total_usage,
                    model=response.model or req.model,
                    provider_name=response.provider_name or req.provider_name,
                    error_message="Tool call requested but no tool manager is attached.",
                )

            dialect_id = req.tools_dialect or "openai"
            normalized_calls = _normalize_tool_calls(response.tool_calls)
            call_results = []
            for call in normalized_calls:
                if not req.tools_on:
                    result = f"[Tool-Error] Tool calling is disabled for this request: {call.name}"
                elif req.allowed_tool_names is not None and call.name not in req.allowed_tool_names:
                    result = f"[Tool-Error] Tool is not enabled for this request: {call.name}"
                else:
                    result = self._execute_one(manager, call.name, call.arguments, context)
                call_results.append((call, result))

            calls_payload = [
                {
                    "name": call.name,
                    "arguments": call.arguments,
                    "tool_call_id": call.id,
                }
                for call, _result in call_results
            ]
            mk_tool_calls = getattr(manager, "mk_tool_calls_msg", None)
            if callable(mk_tool_calls):
                req.messages.append(mk_tool_calls(dialect_id, calls_payload))
            else:
                for call, _result in call_results:
                    req.messages.append(
                        manager.mk_tool_call_msg(
                            dialect_id,
                            call.name,
                            call.arguments,
                            tool_call_id=call.id,
                        )
                    )
            for call, result in call_results:
                req.messages.append(
                    manager.mk_tool_resp_msg(
                        dialect_id,
                        call.name,
                        result,
                        tool_call_id=call.id,
                    )
                )

            round_index += 1
            req.depth = round_index
            req.extra = dict(req.extra or {})
            req.extra["_tool_loop_prepared"] = True
            response = generate_fn(req)
            if response is not None and response.usage is not None:
                total_usage = total_usage.merged_with(response.usage) if total_usage else response.usage
                response.usage = total_usage

        return response

    @staticmethod
    def _execute_one(manager: Any, name: str, arguments: dict, context: ToolExecutionContext) -> Any:
        try:
            return manager.run(name, arguments, context=context)
        except TypeError as exc:
            logger.debug("Tool manager does not accept execution context; retrying legacy call: %s", exc)
            return manager.run(name, arguments)
        except Exception as exc:
            logger.exception("Tool call failed: %s", name)
            return f"[Tool-Error] {name} raised {exc}"


def _normalize_tool_calls(calls: list[ToolCall]) -> list[ToolCall]:
    normalized: list[ToolCall] = []
    used_ids: set[str] = set()
    for call in calls:
        base_id = str(call.id or "").strip() or f"call_{uuid.uuid4().hex[:8]}"
        call_id = base_id
        suffix = 1
        while call_id in used_ids:
            suffix += 1
            call_id = f"{base_id}_{suffix}"
        used_ids.add(call_id)
        normalized.append(
            ToolCall(
                id=call_id,
                name=call.name,
                arguments=dict(call.arguments or {}),
            )
        )
    return normalized


__all__ = ["ToolCallExecutor"]
