from __future__ import annotations

import asyncio
import concurrent.futures
import threading
from typing import Any, Mapping

from main_logger import logger
from core.services import services
from services.contracts import LoopService, MCPService

from .config_store import MCPConfigStore
from .connection import MCPConnection
from .models import MCPCallResult, MCPServerConfig, MCPToolDescriptor


class MCPManager(MCPService):
    """Synchronous host facade scheduled on the application LoopService."""

    def __init__(
        self,
        config_store: MCPConfigStore | None = None,
        *,
        loop_service: LoopService | None = None,
    ) -> None:
        self.config_store = config_store or MCPConfigStore()
        self.loop_service = loop_service
        self._connections: dict[str, MCPConnection] = {}
        self._lock = threading.RLock()
        self._closed = False

    def load_configs(self) -> list[MCPServerConfig]:
        return self.config_store.load()

    async def connect_async(self, server_id: str) -> MCPConnection:
        config = self._config(server_id)
        connection = await self._connection_async(config)
        await connection.connect()
        return connection

    async def refresh_tools_async(self, server_id: str) -> tuple[MCPToolDescriptor, ...]:
        connection = await self.connect_async(server_id)
        return await connection.refresh_tools()

    async def call_tool_async(
        self,
        server_id: str,
        remote_name: str,
        arguments: Mapping[str, Any] | None = None,
    ) -> MCPCallResult:
        connection = await self.connect_async(server_id)
        return await connection.call_tool(remote_name, arguments or {})

    def connect(self, server_id: str) -> MCPConnection:
        config = self._config(server_id)
        connection = self._connection(config)
        self._run(connection.connect(), timeout=config.connect_timeout_seconds)
        return connection

    def connect_enabled(self) -> dict[str, str]:
        errors: dict[str, str] = {}
        for config in self.load_configs():
            if not config.enabled or not config.auto_connect:
                continue
            try:
                self.connect(config.server_id)
            except Exception as exc:
                errors[config.server_id] = str(exc)
                logger.error("MCP server '%s' failed to connect: %s", config.server_id, exc)
        return errors

    def refresh_tools(self, server_id: str) -> tuple[MCPToolDescriptor, ...]:
        connection = self.connect(server_id)
        return self._run(
            connection.refresh_tools(),
            timeout=connection.config.connect_timeout_seconds,
        )

    def list_cached_tools(self, server_id: str) -> tuple[MCPToolDescriptor, ...]:
        """Return cached descriptors without starting or refreshing a server."""
        config = self._config(server_id)
        connection = self._connection(config)
        return connection.tools

    def list_tools(self, server_id: str) -> tuple[MCPToolDescriptor, ...]:
        """Backward-compatible alias for the cache-only discovery API."""
        return self.list_cached_tools(server_id)

    def call_tool(
        self,
        server_id: str,
        remote_name: str,
        arguments: Mapping[str, Any] | None = None,
    ) -> MCPCallResult:
        config = self._config(server_id)
        connection = self._connection(config)
        return self._run(
            connection.call_tool(remote_name, arguments or {}),
            timeout=config.call_timeout_seconds,
        )

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            connections = tuple(self._connections.values())
        loop_service = self.loop_service or services().get_optional(LoopService)
        if loop_service is None or not loop_service.is_running():
            return
        try:
            future = loop_service.run(self._close_connections(connections))
            future.result(timeout=5.0)
        except Exception:
            logger.debug("Failed to close all MCP connections", exc_info=True)

    def _config(self, server_id: str) -> MCPServerConfig:
        normalized = str(server_id or "").strip()
        for config in self.load_configs():
            if config.server_id == normalized:
                if not config.enabled:
                    raise RuntimeError(f"MCP server '{normalized}' is disabled.")
                return config
        raise KeyError(f"Unknown MCP server: {normalized}")

    def _connection(self, config: MCPServerConfig) -> MCPConnection:
        previous = None
        with self._lock:
            connection = self._connections.get(config.server_id)
            if connection is not None and connection.config == config:
                return connection
            previous = connection
            connection = MCPConnection(config)
            self._connections[config.server_id] = connection
        if previous is not None:
            try:
                self._run(previous.close(), timeout=previous.config.connect_timeout_seconds)
            except Exception:
                logger.debug("Failed to close replaced MCP connection", exc_info=True)
        return connection

    async def _connection_async(self, config: MCPServerConfig) -> MCPConnection:
        previous = None
        with self._lock:
            connection = self._connections.get(config.server_id)
            if connection is not None and connection.config == config:
                return connection
            previous = connection
            connection = MCPConnection(config)
            self._connections[config.server_id] = connection
        if previous is not None:
            try:
                await previous.close()
            except Exception:
                logger.debug("Failed to close replaced MCP connection", exc_info=True)
        return connection

    def _run(self, coroutine, *, timeout: float):
        with self._lock:
            if self._closed:
                coroutine.close()
                raise RuntimeError("MCPManager is closed.")
        loop_service = self.loop_service or services().get_optional(LoopService)
        if loop_service is None or not loop_service.is_running():
            coroutine.close()
            raise RuntimeError("MCP requires a running LoopService.")
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None
        if running_loop is loop_service.loop():
            coroutine.close()
            raise RuntimeError("MCPManager cannot synchronously wait from the application event loop thread.")
        future = loop_service.run(coroutine)
        try:
            return future.result(timeout=float(timeout))
        except concurrent.futures.TimeoutError:
            future.cancel()
            raise TimeoutError(f"MCP operation exceeded {float(timeout):.1f}s.")


    @staticmethod
    async def _close_connections(connections: tuple[MCPConnection, ...]) -> None:
        for connection in connections:
            try:
                await connection.close()
            except Exception:
                logger.debug("Failed to close MCP connection", exc_info=True)


__all__ = ["MCPManager"]
