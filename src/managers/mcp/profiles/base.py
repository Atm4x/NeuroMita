from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Mapping

from ..manager import MCPManager
from ..models import MCPCallResult


@dataclass(frozen=True)
class TaskExecutorTurn:
    result: MCPCallResult
    thread_id: str


class TaskExecutorProfile:
    """Configurable adapter for a long-running MCP task executor."""

    def __init__(
        self,
        manager: MCPManager,
        *,
        server_id: str,
        start_tool: str,
        continue_tool: str,
    ) -> None:
        self.manager = manager
        self.server_id = server_id
        self.start_tool = start_tool
        self.continue_tool = continue_tool

    def start(self, prompt: str, arguments: Mapping[str, Any] | None = None) -> TaskExecutorTurn:
        payload = {"prompt": str(prompt)}
        payload.update(dict(arguments or {}))
        result = self.manager.call_tool(self.server_id, self.start_tool, payload)
        if result.is_error:
            raise RuntimeError(result.text or "MCP task executor returned an error.")
        thread_id = _extract_thread_id(result)
        if not thread_id:
            raise RuntimeError("MCP task executor did not return a thread id.")
        return TaskExecutorTurn(result=result, thread_id=thread_id)

    def continue_task(self, thread_id: str, prompt: str) -> TaskExecutorTurn:
        result = self.manager.call_tool(
            self.server_id,
            self.continue_tool,
            {"threadId": str(thread_id), "prompt": str(prompt)},
        )
        if result.is_error:
            raise RuntimeError(result.text or "MCP task continuation returned an error.")
        resolved_thread_id = _extract_thread_id(result) or str(thread_id)
        return TaskExecutorTurn(result=result, thread_id=resolved_thread_id)

    async def start_async(
        self,
        prompt: str,
        arguments: Mapping[str, Any] | None = None,
    ) -> TaskExecutorTurn:
        payload = {"prompt": str(prompt)}
        payload.update(dict(arguments or {}))
        result = await _call_tool_async(
            self.manager,
            self.server_id,
            self.start_tool,
            payload,
        )
        if result.is_error:
            raise RuntimeError(result.text or "MCP task executor returned an error.")
        thread_id = _extract_thread_id(result)
        if not thread_id:
            raise RuntimeError("MCP task executor did not return a thread id.")
        return TaskExecutorTurn(result=result, thread_id=thread_id)

    async def continue_task_async(self, thread_id: str, prompt: str) -> TaskExecutorTurn:
        result = await _call_tool_async(
            self.manager,
            self.server_id,
            self.continue_tool,
            {"threadId": str(thread_id), "prompt": str(prompt)},
        )
        if result.is_error:
            raise RuntimeError(result.text or "MCP task continuation returned an error.")
        resolved_thread_id = _extract_thread_id(result) or str(thread_id)
        return TaskExecutorTurn(result=result, thread_id=resolved_thread_id)


async def _call_tool_async(manager: Any, server_id: str, remote_name: str, arguments: dict) -> MCPCallResult:
    call_tool_async = getattr(manager, "call_tool_async", None)
    if callable(call_tool_async):
        return await call_tool_async(server_id, remote_name, arguments)
    return await asyncio.to_thread(manager.call_tool, server_id, remote_name, arguments)


def _extract_thread_id(result: MCPCallResult) -> str:
    structured = result.structured_content
    if isinstance(structured, Mapping):
        for key in ("threadId", "thread_id", "conversationId", "conversation_id"):
            value = str(structured.get(key) or "").strip()
            if value:
                return value
    return ""


__all__ = ["TaskExecutorProfile", "TaskExecutorTurn"]
