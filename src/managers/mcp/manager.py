from __future__ import annotations

import asyncio
import concurrent.futures
import threading
from typing import Any, Mapping

from main_logger import logger
from services.contracts import MCPService

from .config_store import MCPConfigStore
from .connection import MCPConnection
from .models import MCPCallResult, MCPServerConfig, MCPToolDescriptor


class MCPManager(MCPService):
    """Synchronous host facade backed by one dedicated asyncio loop."""

    def __init__(self, config_store: MCPConfigStore | None = None) -> None:
        self.config_store = config_store or MCPConfigStore()
        self._connections: dict[str, MCPConnection] = {}
        self._lock = threading.RLock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._closed = False

    def load_configs(self) -> list[MCPServerConfig]:
        return self.config_store.load()

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

    def list_tools(self, server_id: str) -> tuple[MCPToolDescriptor, ...]:
        config = self._config(server_id)
        connection = self._connection(config)
        return self._run(
            connection.refresh_tools(),
            timeout=config.connect_timeout_seconds,
        )

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
        if self._loop is not None:
            future = asyncio.run_coroutine_threadsafe(
                self._close_connections(connections),
                self._loop,
            )
            try:
                future.result(timeout=5.0)
            except Exception:
                logger.debug("Failed to close all MCP connections", exc_info=True)
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self._loop = None
        self._thread = None

    def _config(self, server_id: str) -> MCPServerConfig:
        normalized = str(server_id or "").strip()
        for config in self.load_configs():
            if config.server_id == normalized:
                if not config.enabled:
                    raise RuntimeError(f"MCP server '{normalized}' is disabled.")
                return config
        raise KeyError(f"Unknown MCP server: {normalized}")

    def _connection(self, config: MCPServerConfig) -> MCPConnection:
        with self._lock:
            connection = self._connections.get(config.server_id)
            if connection is None or connection.config != config:
                connection = MCPConnection(config)
                self._connections[config.server_id] = connection
            return connection

    def _run(self, coroutine, *, timeout: float):
        self._ensure_loop()
        assert self._loop is not None
        if threading.current_thread() is self._thread:
            raise RuntimeError("MCPManager cannot synchronously wait from its event loop thread.")
        future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        try:
            return future.result(timeout=float(timeout))
        except concurrent.futures.TimeoutError:
            future.cancel()
            raise TimeoutError(f"MCP operation exceeded {float(timeout):.1f}s.")

    def _ensure_loop(self) -> None:
        with self._lock:
            if self._closed:
                raise RuntimeError("MCPManager is closed.")
            if self._loop is not None:
                return
            self._ready.clear()
            self._thread = threading.Thread(
                target=self._loop_worker,
                name="neuromita-mcp-loop",
                daemon=True,
            )
            self._thread.start()
        if not self._ready.wait(timeout=5.0):
            raise RuntimeError("MCP event loop failed to start.")

    def _loop_worker(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        with self._lock:
            self._loop = loop
            self._ready.set()
        try:
            loop.run_forever()
        finally:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()

    @staticmethod
    async def _close_connections(connections: tuple[MCPConnection, ...]) -> None:
        for connection in connections:
            try:
                await connection.close()
            except Exception:
                logger.debug("Failed to close MCP connection", exc_info=True)


__all__ = ["MCPManager"]
