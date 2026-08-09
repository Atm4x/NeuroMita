from __future__ import annotations

from typing import Any

from main_logger import logger
from managers.tools.base import Tool
from managers.tools.tool_manager import ToolManager

from .manager import MCPManager
from .models import MCPToolDescriptor


class _MCPTool(Tool):
    def __init__(self, manager: MCPManager, descriptor: MCPToolDescriptor) -> None:
        self.manager = manager
        self.descriptor = descriptor

    @property
    def name(self) -> str:
        return self.descriptor.public_name

    @property
    def description(self) -> str:
        return self.descriptor.description or f"Call MCP tool '{self.descriptor.remote_name}'."

    @property
    def parameters(self) -> dict[str, Any]:
        return dict(self.descriptor.input_schema or {})

    def run(self, **kwargs: Any) -> Any:
        result = self.manager.call_tool(
            self.descriptor.server_id,
            self.descriptor.remote_name,
            kwargs,
        )
        return result.as_tool_value()


class MCPToolSource:
    def __init__(self, manager: MCPManager, tool_manager: ToolManager) -> None:
        self.manager = manager
        self.tool_manager = tool_manager
        self._tools: dict[str, _MCPTool] = {}

    def refresh(self, *, connect_if_needed: bool = False) -> dict[str, str]:
        errors: dict[str, str] = {}
        configs = tuple(self.manager.load_configs())
        eligible_ids = {
            config.server_id
            for config in configs
            if config.enabled and config.expose_tools
        }
        discovered: dict[str, MCPToolDescriptor] = {}
        successful_ids: set[str] = set()

        for config in configs:
            if config.server_id not in eligible_ids:
                continue
            try:
                refresh = getattr(self.manager, "refresh_tools", None)
                list_cached = getattr(self.manager, "list_cached_tools", None)
                should_connect = bool(connect_if_needed and config.auto_connect)
                if should_connect and callable(refresh):
                    descriptors = refresh(config.server_id)
                elif callable(list_cached):
                    descriptors = list_cached(config.server_id)
                else:
                    descriptors = self.manager.list_tools(config.server_id)
                successful_ids.add(config.server_id)
                for descriptor in descriptors:
                    discovered[descriptor.public_name] = descriptor
            except Exception as exc:
                errors[config.server_id] = str(exc)
                logger.error("Failed to expose MCP tools from '%s': %s", config.server_id, exc)

        for public_name, descriptor in discovered.items():
            existing = self._tools.get(public_name)
            if existing is not None and existing.descriptor == descriptor:
                continue
            tool = _MCPTool(self.manager, descriptor)
            try:
                self.tool_manager.register(tool, replace=existing is not None)
            except Exception as exc:
                errors.setdefault(descriptor.server_id, str(exc))
                logger.error("Failed to register MCP tool '%s': %s", public_name, exc)
                continue
            self._tools[public_name] = tool

        for public_name, tool in tuple(self._tools.items()):
            server_id = tool.descriptor.server_id
            should_remove = (
                server_id not in eligible_ids
                or (server_id in successful_ids and public_name not in discovered)
            )
            if should_remove and self.tool_manager.unregister(public_name, expected=tool):
                self._tools.pop(public_name, None)
        return errors

    def tools(self) -> tuple[Tool, ...]:
        return tuple(self._tools.values())


__all__ = ["MCPToolSource"]
