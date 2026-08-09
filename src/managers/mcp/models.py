from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class MCPConfigurationError(ValueError):
    pass


class MCPTransportKind(str, Enum):
    STDIO = "stdio"
    STREAMABLE_HTTP = "streamable_http"


class MCPServerState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    READY = "ready"
    ERROR = "error"


@dataclass(frozen=True)
class MCPServerConfig:
    server_id: str
    name: str
    enabled: bool
    transport: MCPTransportKind
    command: str | None = None
    args: tuple[str, ...] = ()
    cwd: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    url: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    profile: str | None = None
    auto_connect: bool = True
    connect_timeout_seconds: float = 15.0
    call_timeout_seconds: float = 120.0
    expose_tools: bool = False
    allowed_tools: tuple[str, ...] = ("*",)
    denied_tools: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "MCPServerConfig":
        if not isinstance(data, Mapping):
            raise MCPConfigurationError("MCP server entry must be an object.")
        try:
            transport = MCPTransportKind(str(data.get("transport") or "stdio"))
        except ValueError as exc:
            raise MCPConfigurationError("Unsupported MCP transport.") from exc
        config = cls(
            server_id=str(data.get("id") or "").strip(),
            name=str(data.get("name") or data.get("id") or "").strip(),
            enabled=bool(data.get("enabled", False)),
            transport=transport,
            command=_optional_string(data.get("command")),
            args=tuple(str(value) for value in _string_sequence(data.get("args"))),
            cwd=_optional_string(data.get("cwd")),
            env=_string_mapping(data.get("env")),
            url=_optional_string(data.get("url")),
            headers=_string_mapping(data.get("headers")),
            profile=_optional_string(data.get("profile")),
            auto_connect=bool(data.get("auto_connect", True)),
            connect_timeout_seconds=_positive_float(data.get("connect_timeout_seconds"), 15.0),
            call_timeout_seconds=_positive_float(data.get("call_timeout_seconds"), 120.0),
            expose_tools=bool(data.get("expose_tools", False)),
            allowed_tools=tuple(_string_sequence(data.get("allowed_tools"), default=("*",))),
            denied_tools=tuple(_string_sequence(data.get("denied_tools"))),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if not self.server_id or not re.fullmatch(r"[A-Za-z0-9_-]+", self.server_id):
            raise MCPConfigurationError("MCP server id must contain only letters, digits, '_' or '-'.")
        if not self.name:
            raise MCPConfigurationError("MCP server name must not be empty.")
        transport = MCPTransportKind(self.transport)
        if transport is MCPTransportKind.STDIO and not self.command:
            raise MCPConfigurationError(f"MCP stdio server '{self.server_id}' has no command.")
        if transport is MCPTransportKind.STREAMABLE_HTTP and not self.url:
            raise MCPConfigurationError(f"MCP HTTP server '{self.server_id}' has no URL.")
        if not self.allowed_tools:
            raise MCPConfigurationError(f"MCP server '{self.server_id}' must define allowed_tools or '*'.")
        if self.connect_timeout_seconds <= 0 or self.call_timeout_seconds <= 0:
            raise MCPConfigurationError(f"MCP server '{self.server_id}' has invalid timeout settings.")

    def allows_tool(self, remote_name: str) -> bool:
        name = str(remote_name or "")
        if any(fnmatch.fnmatchcase(name, pattern) for pattern in self.denied_tools):
            return False
        return any(fnmatch.fnmatchcase(name, pattern) for pattern in self.allowed_tools)

    def to_dict(self, *, redact: bool = True) -> dict[str, Any]:
        return {
            "id": self.server_id,
            "name": self.name,
            "enabled": self.enabled,
            "transport": MCPTransportKind(self.transport).value,
            "command": self.command,
            "args": list(self.args),
            "cwd": self.cwd,
            "env": dict(self.env),
            "url": self.url,
            "headers": (
                {key: "<redacted>" for key in self.headers}
                if redact
                else dict(self.headers)
            ),
            "profile": self.profile,
            "auto_connect": self.auto_connect,
            "connect_timeout_seconds": self.connect_timeout_seconds,
            "call_timeout_seconds": self.call_timeout_seconds,
            "expose_tools": self.expose_tools,
            "allowed_tools": list(self.allowed_tools),
            "denied_tools": list(self.denied_tools),
        }


@dataclass(frozen=True)
class MCPToolDescriptor:
    server_id: str
    remote_name: str
    public_name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] | None = None
    revision: int = 0


@dataclass(frozen=True)
class MCPCallResult:
    text: str = ""
    structured_content: Any = None
    content_blocks: tuple[Any, ...] = ()
    is_error: bool = False

    def as_tool_value(self) -> Any:
        if self.structured_content is not None:
            return self.structured_content
        return self.text


def build_public_tool_name(server_id: str, remote_name: str) -> str:
    server = _sanitize_name(server_id)
    remote = _sanitize_name(remote_name)
    if not server or not remote:
        raise MCPConfigurationError("MCP tool names must not be empty.")
    return f"mcp__{server}__{remote}"


def _sanitize_name(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", str(value or "").strip())


def _optional_string(value: Any) -> str | None:
    value = str(value or "").strip()
    return value or None


def _string_sequence(value: Any, *, default: tuple[str, ...] = ()) -> tuple[str, ...]:
    if value is None:
        return default
    if not isinstance(value, (list, tuple)):
        raise MCPConfigurationError("MCP list fields must be arrays.")
    return tuple(str(item) for item in value)


def _string_mapping(value: Any) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise MCPConfigurationError("MCP mapping fields must be objects.")
    return {str(key): str(item) for key, item in value.items()}


def _positive_float(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return float(default)
    return parsed if parsed > 0 else float(default)


__all__ = [
    "MCPCallResult",
    "MCPConfigurationError",
    "MCPServerConfig",
    "MCPServerState",
    "MCPToolDescriptor",
    "MCPTransportKind",
    "build_public_tool_name",
]
