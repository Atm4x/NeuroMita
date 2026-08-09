from __future__ import annotations

import asyncio
import os
from contextlib import AsyncExitStack
from typing import Any, Mapping

from .models import (
    MCPCallResult,
    MCPServerConfig,
    MCPServerState,
    MCPToolDescriptor,
    MCPTransportKind,
    build_public_tool_name,
)


class MCPConnection:
    def __init__(self, config: MCPServerConfig) -> None:
        self.config = config
        self.state = MCPServerState.DISCONNECTED
        self.last_error: str | None = None
        self._stack: AsyncExitStack | None = None
        self._session: Any = None
        self._tools: tuple[MCPToolDescriptor, ...] = ()
        self._lock: asyncio.Lock | None = None

    @property
    def tools(self) -> tuple[MCPToolDescriptor, ...]:
        return self._tools

    async def connect(self) -> None:
        if self.state is MCPServerState.READY:
            return
        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
            if self.state is MCPServerState.READY:
                return
            self.state = MCPServerState.CONNECTING
            stack = AsyncExitStack()
            try:
                transport = await self._open_transport(stack)
                if transport[0] == "client":
                    _tag, client_type, transport_context = transport
                    self._session = await stack.enter_async_context(
                        client_type(transport_context, mode="auto")
                    )
                else:
                    _tag, ClientSession, read_stream, write_stream = transport
                    self._session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
                    await self._session.initialize()
                self._stack = stack
                self._tools = await self._list_tools_unlocked()
                self.last_error = None
                self.state = MCPServerState.READY
            except Exception as exc:
                await stack.aclose()
                self._session = None
                self._stack = None
                self.state = MCPServerState.ERROR
                self.last_error = f"{type(exc).__name__}: {exc}"
                raise

    async def close(self) -> None:
        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
            stack, self._stack = self._stack, None
            self._session = None
            self._tools = ()
            self.state = MCPServerState.DISCONNECTED
            if stack is not None:
                await stack.aclose()

    async def refresh_tools(self) -> tuple[MCPToolDescriptor, ...]:
        await self.connect()
        assert self._lock is not None
        async with self._lock:
            self._tools = await self._list_tools_unlocked()
            return self._tools

    async def call_tool(self, remote_name: str, arguments: Mapping[str, Any]) -> MCPCallResult:
        await self.connect()
        assert self._lock is not None
        async with self._lock:
            if not self.config.allows_tool(remote_name):
                raise PermissionError(f"MCP tool is not allowed: {remote_name}")
            result = await self._session.call_tool(
                str(remote_name),
                arguments=dict(arguments or {}),
            )
            return _decode_call_result(result)

    async def _list_tools_unlocked(self) -> tuple[MCPToolDescriptor, ...]:
        pages: list[Any] = []
        cursor = None
        seen_cursors: set[str] = set()
        for _page_number in range(1000):
            if cursor is None:
                result = await self._session.list_tools()
            else:
                try:
                    result = await self._session.list_tools(cursor=cursor)
                except TypeError:
                    from mcp.types import PaginatedRequestParams
                    result = await self._session.list_tools(
                        params=PaginatedRequestParams(cursor=cursor)
                    )
            pages.extend(getattr(result, "tools", None) or [])
            next_cursor = _object_field(result, "next_cursor", "nextCursor")
            if next_cursor is None or str(next_cursor).strip() == "":
                break
            cursor = str(next_cursor)
            if cursor in seen_cursors:
                raise RuntimeError("MCP tools/list returned a repeated pagination cursor.")
            seen_cursors.add(cursor)
        else:
            raise RuntimeError("MCP tools/list exceeded the pagination page limit.")

        descriptors: list[MCPToolDescriptor] = []
        for item in pages:
            remote_name = str(getattr(item, "name", "") or "").strip()
            if not remote_name or not self.config.allows_tool(remote_name):
                continue
            input_schema = _object_field(item, "inputSchema", "input_schema") or {}
            output_schema = _object_field(item, "outputSchema", "output_schema")
            descriptors.append(
                MCPToolDescriptor(
                    server_id=self.config.server_id,
                    remote_name=remote_name,
                    public_name=build_public_tool_name(self.config.server_id, remote_name),
                    description=str(getattr(item, "description", "") or "")[:4000],
                    input_schema=dict(input_schema) if isinstance(input_schema, Mapping) else {},
                    output_schema=dict(output_schema) if isinstance(output_schema, Mapping) else None,
                )
            )
        return tuple(descriptors)

    async def _open_transport(self, stack: AsyncExitStack):
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
            try:
                from mcp import Client as HighLevelClient
            except ImportError:
                HighLevelClient = None
        except ImportError as exc:
            raise RuntimeError(
                "MCP support is not installed. Install the optional MCP dependency."
            ) from exc

        transport = MCPTransportKind(self.config.transport)
        if transport is MCPTransportKind.STDIO:
            environment = dict(os.environ)
            environment.update(_resolve_env(self.config.env))
            params = StdioServerParameters(
                command=str(self.config.command),
                args=list(self.config.args),
                env=environment,
                cwd=self.config.cwd,
            )
            transport_context = stdio_client(params)
            if HighLevelClient is not None:
                return "client", HighLevelClient, transport_context
            read_stream, write_stream = await stack.enter_async_context(transport_context)
            return "session", ClientSession, read_stream, write_stream

        from mcp.client.streamable_http import streamable_http_client
        headers = _resolve_env(self.config.headers)
        try:
            import httpx2 as http_client_lib
        except ImportError:
            import httpx as http_client_lib
        http_client = http_client_lib.AsyncClient(
            headers=headers,
            timeout=float(self.config.call_timeout_seconds),
            follow_redirects=True,
        )
        await stack.enter_async_context(http_client)
        transport_context = streamable_http_client(
            str(self.config.url),
            http_client=http_client,
        )
        if HighLevelClient is not None:
            return "client", HighLevelClient, transport_context
        streams = tuple(await stack.enter_async_context(transport_context))
        if len(streams) < 2:
            raise RuntimeError("MCP streamable HTTP transport returned incomplete streams.")
        read_stream, write_stream = streams[:2]
        return "session", ClientSession, read_stream, write_stream


def _object_field(value: Any, *names: str) -> Any:
    for name in names:
        if isinstance(value, Mapping) and name in value:
            return value[name]
        candidate = getattr(value, name, None)
        if candidate is not None:
            return candidate
    return None


def _resolve_env(values: Mapping[str, str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in values.items():
        result[str(key)] = _resolve_secret_ref(str(value))
    return result


def _resolve_secret_ref(value: str) -> str:
    prefix = "$" + "{env:"
    if value.startswith(prefix) and value.endswith("}"):
        name = value[len(prefix):-1].strip()
        if not name:
            raise ValueError("Environment reference has an empty name.")
        resolved = os.environ.get(name)
        if resolved is None:
            raise ValueError(f"Environment variable is not set: {name}")
        return resolved
    return value


def _decode_call_result(result: Any) -> MCPCallResult:
    blocks = tuple(getattr(result, "content", None) or ())
    text_parts: list[str] = []
    for block in blocks:
        value = _object_field(block, "text")
        if value is not None:
            text_parts.append(str(value))
    structured = _object_field(result, "structuredContent", "structured_content")
    is_error = bool(_object_field(result, "isError", "is_error") or False)
    return MCPCallResult(
        text="\n".join(text_parts),
        structured_content=structured,
        content_blocks=blocks,
        is_error=is_error,
    )


__all__ = ["MCPConnection"]
