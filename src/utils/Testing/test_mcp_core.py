import shutil
import sys
from pathlib import Path
PROJECT_SRC = Path(__file__).resolve().parents[2]
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from managers.mcp.config_store import MCPConfigStore
from managers.mcp.models import (
    MCPServerConfig,
    MCPToolDescriptor,
    MCPTransportKind,
    build_public_tool_name,
)
from managers.mcp.source import MCPToolSource
from managers.mcp.background_tasks import MCPBackgroundTaskRunner
from managers.mcp.models import MCPCallResult
from managers.mcp.profiles.codex import CodexProfile, CodexTaskService, CodexTaskTool
from managers.task_manager import TaskManager, TaskStatus
from managers.tools.models import ToolExecutionContext
from managers.tools.base import Tool
from managers.tools.tool_manager import ToolManager


import pytest


@pytest.fixture
def local_temp_dir():
    root = PROJECT_SRC / ".mcp_test_tmp"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir()
    try:
        yield root
    finally:
        if root.exists():
            shutil.rmtree(root)


def test_mcp_config_store_bootstraps_disabled_codex_and_round_trips_env_refs(local_temp_dir):
    path = local_temp_dir / "Settings" / "mcp_servers.json"
    store = MCPConfigStore(path)

    configs = store.load()

    assert len(configs) == 1
    assert configs[0].server_id == "codex"
    assert configs[0].enabled is False
    assert path.is_file()

    config = MCPServerConfig.from_dict(
        {
            "id": "my_server",
            "name": "My Server",
            "enabled": True,
            "transport": "stdio",
            "command": "python",
            "args": ["server.py"],
            "env": {"TOKEN": "$" + "{env:MY_TOKEN}"},
            "headers": {"Authorization": "$" + "{env:MY_TOKEN}"},
            "expose_tools": True,
            "allowed_tools": ["read_*"],
            "denied_tools": ["read_secret"],
        }
    )
    store.upsert(config)

    loaded = {item.server_id: item for item in store.load()}
    assert loaded["my_server"].env["TOKEN"] == "$" + "{env:MY_TOKEN}"
    assert loaded["my_server"].headers["Authorization"] == "$" + "{env:MY_TOKEN}"
    assert loaded["my_server"].allows_tool("read_file")
    assert not loaded["my_server"].allows_tool("read_secret")


def test_mcp_config_store_does_not_overwrite_invalid_json(local_temp_dir):
    path = local_temp_dir / "mcp_servers.json"
    path.write_text("{broken", encoding="utf-8")
    store = MCPConfigStore(path)

    assert store.load() == []
    assert path.read_text(encoding="utf-8") == "{broken"


def test_mcp_public_tool_names_are_stable_and_sanitized():
    assert build_public_tool_name("my-server", "read file") == "mcp__my-server__read_file"


class _ExistingTool(Tool):
    @property
    def name(self):
        return "mcp__server__read_file"

    @property
    def description(self):
        return "Existing"

    def run(self, **kwargs):
        return "existing"


class _FakeMCPManager:
    def load_configs(self):
        return [
            MCPServerConfig(
                server_id="server",
                name="Server",
                enabled=True,
                transport=MCPTransportKind.STDIO,
                command="python",
                expose_tools=True,
            )
        ]

    def list_tools(self, server_id):
        return (
            MCPToolDescriptor(
                server_id=server_id,
                remote_name="read_file",
                public_name="mcp__server__read_file",
                description="Read a file",
                input_schema={"type": "object"},
            ),
        )


def test_mcp_source_rejects_tool_name_collision():
    tool_manager = ToolManager()
    tool_manager.register(_ExistingTool())
    source = MCPToolSource(_FakeMCPManager(), tool_manager)

    errors = source.refresh()

    assert "server" in errors
    assert source.tools() == ()

class _FakeCodexManager:
    def __init__(self):
        self.calls = []

    def call_tool(self, server_id, remote_name, arguments):
        self.calls.append((server_id, remote_name, arguments))
        return MCPCallResult(
            text="Codex finished.",
            structured_content={"threadId": "thread-1", "content": "Codex finished."},
        )


def test_codex_profile_uses_safe_defaults_and_thread_id():
    manager = _FakeCodexManager()
    profile = CodexProfile(manager)

    arguments = profile.build_start_arguments(cwd="C:/project")
    turn = profile.start("Inspect the project.", arguments)

    assert arguments["sandbox"] == "read-only"
    assert arguments["approval-policy"] == "on-request"
    assert turn.thread_id == "thread-1"
    assert manager.calls[0] == (
        "codex",
        "codex",
        {"prompt": "Inspect the project.", "cwd": "C:/project", "sandbox": "read-only", "approval-policy": "on-request"},
    )


def test_codex_task_tool_returns_immediately_and_completes_in_background():
    manager = _FakeCodexManager()
    task_manager = TaskManager()
    runner = MCPBackgroundTaskRunner(task_manager, max_workers=1)
    service = CodexTaskService(manager, task_manager=task_manager, runner=runner)
    tool = CodexTaskTool(service)

    accepted = tool.run_with_context(
        ToolExecutionContext(character_id="mita", request_id="request-1"),
        prompt="Run tests.",
    )

    assert accepted["accepted"] is True
    task_uid = accepted["task_id"]
    deadline = __import__("time").monotonic() + 2.0
    task = task_manager.get_task(task_uid)
    while task is not None and task.status not in {TaskStatus.SUCCESS, TaskStatus.FAILED}:
        if __import__("time").monotonic() >= deadline:
            raise AssertionError("Codex background task did not finish")
        __import__("time").sleep(0.01)
        task = task_manager.get_task(task_uid)

    assert task is not None
    assert task.status is TaskStatus.SUCCESS
    assert task.result["thread_id"] == "thread-1"
    assert task.data["character_id"] == "mita"
    service.close()
