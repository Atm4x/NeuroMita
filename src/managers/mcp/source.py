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

    def refresh(self) -> dict[str, str]:
        errors: dict[str, str] = {}
        for config in self.manager.load_configs():
            if not config.enabled or not config.expose_tools or not config.auto_connect:
                continue
            try:
                for descriptor in self.manager.list_tools(config.server_id):
                    if descriptor.public_name in self._tools:
                        continue
                    tool = _MCPTool(self.manager, descriptor)
                    self.tool_manager.register(tool)
                    self._tools[descriptor.public_name] = tool
            except Exception as exc:
                errors[config.server_id] = str(exc)
                logger.error("Failed to expose MCP tools from '%s': %s", config.server_id, exc)
        return errors

    def tools(self) -> tuple[Tool, ...]:
        return tuple(self._tools.values())


__all__ = ["MCPToolSource"]
