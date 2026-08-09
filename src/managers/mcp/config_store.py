from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Sequence

from core.app_paths import settings_path
from main_logger import logger

from .models import MCPConfigurationError, MCPServerConfig, MCPTransportKind


class MCPConfigStore:
    DEFAULT_FILENAME = "mcp_servers.json"

    def __init__(self, path: str | os.PathLike[str] | None = None) -> None:
        self.path = Path(path) if path is not None else settings_path(self.DEFAULT_FILENAME)

    def load(self) -> list[MCPServerConfig]:
        self.bootstrap_defaults()
        if not self.path.is_file():
            return []
        try:
            with self.path.open("r", encoding="utf-8") as source:
                payload = json.load(source)
            rows = payload.get("servers", []) if isinstance(payload, dict) else []
            if not isinstance(rows, list):
                raise MCPConfigurationError("MCP config field 'servers' must be an array.")
            configs = []
            for row in rows:
                try:
                    configs.append(MCPServerConfig.from_dict(row))
                except Exception as exc:
                    logger.error("Ignoring invalid MCP server configuration: %s", exc)
            return configs
        except (OSError, json.JSONDecodeError, MCPConfigurationError) as exc:
            logger.error("Failed to read MCP configuration; MCP remains disabled: %s", exc)
            return []

    def save(self, configs: Sequence[MCPServerConfig]) -> None:
        rows = list(configs)
        for config in rows:
            config.validate()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "servers": [config.to_dict(redact=False) for config in rows],
        }
        temporary = self.path.with_name(f".{self.path.name}.{os.getpid()}.tmp")
        try:
            with temporary.open("w", encoding="utf-8", newline="") as target:
                json.dump(payload, target, ensure_ascii=False, indent=2)
                target.write("\n")
                target.flush()
                os.fsync(target.fileno())
            os.replace(temporary, self.path)
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass

    def upsert(self, config: MCPServerConfig) -> None:
        configs = self.load()
        by_id = {item.server_id: item for item in configs}
        by_id[config.server_id] = config
        self.save(list(by_id.values()))

    def delete(self, server_id: str) -> bool:
        configs = self.load()
        filtered = [item for item in configs if item.server_id != server_id]
        if len(filtered) == len(configs):
            return False
        self.save(filtered)
        return True

    def bootstrap_defaults(self) -> None:
        if self.path.exists():
            return
        self.save(
            [
                MCPServerConfig(
                    server_id="codex",
                    name="Codex MCP",
                    enabled=False,
                    transport=MCPTransportKind.STDIO,
                    command="codex",
                    args=("mcp-server",),
                    profile="codex",
                    expose_tools=False,
                )
            ]
        )


__all__ = ["MCPConfigStore"]
