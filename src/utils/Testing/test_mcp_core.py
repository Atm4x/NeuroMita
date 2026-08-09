import asyncio
import shutil
import sys
import threading
from types import SimpleNamespace
from pathlib import Path
PROJECT_SRC = Path(__file__).resolve().parents[2]
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from managers.mcp.config_store import MCPConfigStore
from managers.mcp.manager import MCPManager
from managers.mcp.models import (
    MCPServerConfig,
    MCPToolDescriptor,
    MCPTransportKind,
    build_public_tool_name,
)
from managers.mcp.source import MCPToolSource
from managers.mcp.background_tasks import MCPBackgroundTaskRunner
from managers.mcp.connection import MCPConnection
from managers.mcp.models import MCPCallResult
from managers.mcp.profiles.codex import CodexProfile, CodexTaskService, CodexTaskTool
from handlers.llm_providers.base import LLMRequest, LLMResponse
from handlers.llm_providers.gemini_provider import GeminiProvider
from managers.provider_manager import ProviderManager
from managers.task_manager import TaskManager, TaskStatus
from managers.tools.models import ToolExecutionContext
from managers.tools.base import Tool
from managers.tools.tool_manager import ToolManager
from controllers.model_controller import ModelController
from services.contracts import LoopService


import pytest


class _TestLoopService(LoopService):
    def __init__(self):
        self._loop = asyncio.new_event_loop()
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        assert self._ready.wait(timeout=2.0)

    def _run(self):
        asyncio.set_event_loop(self._loop)
        self._ready.set()
        self._loop.run_forever()

    def loop(self):
        return self._loop

    def is_running(self):
        return self._loop.is_running()

    def run(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    def close(self):
        if self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=2.0)
        self._loop.close()


@pytest.fixture
def loop_service():
    service = _TestLoopService()
    try:
        yield service
    finally:
        service.close()


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
            "projects": {"repo": "C:/trusted/repo"},
        }
    )
    store.upsert(config)

    loaded = {item.server_id: item for item in store.load()}
    assert loaded["my_server"].env["TOKEN"] == "$" + "{env:MY_TOKEN}"
    assert loaded["my_server"].headers["Authorization"] == "$" + "{env:MY_TOKEN}"
    assert loaded["my_server"].allows_tool("read_file")
    assert not loaded["my_server"].allows_tool("read_secret")
    assert loaded["my_server"].projects == {"repo": "C:/trusted/repo"}


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

    def list_cached_tools(self, server_id):
        return self.list_tools(server_id)

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


class _AutoConnectTrackingManager(_FakeMCPManager):
    def __init__(self):
        self.refresh_calls = 0
        self.list_calls = 0

    def load_configs(self):
        return [
            MCPServerConfig(
                server_id="server",
                name="Server",
                enabled=True,
                transport=MCPTransportKind.STDIO,
                command="python",
                auto_connect=False,
                expose_tools=True,
            )
        ]

    def list_tools(self, server_id):
        self.list_calls += 1
        return super().list_tools(server_id)

    def refresh_tools(self, server_id):
        self.refresh_calls += 1
        return super().list_tools(server_id)


def test_mcp_manager_cache_read_does_not_connect():
    config = MCPServerConfig(
        server_id="server",
        name="Server",
        enabled=True,
        transport=MCPTransportKind.STDIO,
        command="python",
        expose_tools=True,
    )
    descriptor = MCPToolDescriptor(
        server_id="server",
        remote_name="cached",
        public_name="mcp__server__cached",
        description="Cached",
        input_schema={"type": "object"},
    )

    class _Store:
        def load(self):
            return [config]

    class _Connection(MCPConnection):
        async def connect(self):
            raise AssertionError("cache-only discovery must not connect")

    manager = MCPManager(_Store())
    connection = _Connection(config)
    connection._tools = (descriptor,)
    manager._connections[config.server_id] = connection

    assert manager.list_cached_tools("server") == (descriptor,)


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


def test_provider_manager_builds_tools_with_selected_provider_dialect():
    class _ToolManager:
        def __init__(self):
            self.calls = []

        def get_tools_payload(self, dialect_id, *, enabled_names=None):
            self.calls.append((dialect_id, enabled_names))
            return [{"dialect": dialect_id}]

    class _Provider:
        name = "fake"
        supports_tools_native = True
        supports_streaming_with_tools = True
        tools_dialect_id = "provider-dialect"

        def generate(self, req):
            return LLMResponse(text="ok", provider_name=self.name)

    provider_manager = ProviderManager()
    provider_manager._providers = [_Provider()]
    provider_manager._unavailable = {}
    tool_manager = _ToolManager()
    request = LLMRequest(
        model="model",
        messages=[],
        provider_name="fake",
        dialect_id="preset-dialect",
        tools_on=True,
        tools_mode="native",
        tool_manager=tool_manager,
        allowed_tool_names=frozenset({"lookup"}),
        extra={
            "tools_requested": True,
            "enabled_tool_names": ["lookup"],
        },
    )

    response = provider_manager.generate(request)

    assert response.text == "ok"
    assert request.tools_dialect == "provider-dialect"
    assert request.tools_payload == [{"dialect": "provider-dialect"}]
    assert tool_manager.calls == [("provider-dialect", ["lookup"])]


def test_provider_manager_disables_tools_on_mcp_completion_turn():
    class _ToolManager:
        def get_tools_payload(self, dialect_id, *, enabled_names=None):
            raise AssertionError("completion turn must not build tools")

    class _Provider:
        name = "fake"
        supports_tools_native = True
        tools_dialect_id = "provider-dialect"

        def generate(self, req):
            return LLMResponse(text="ok", provider_name=self.name)

    provider_manager = ProviderManager()
    provider_manager._providers = [_Provider()]
    provider_manager._unavailable = {}
    request = LLMRequest(
        model="model",
        messages=[],
        provider_name="fake",
        tools_on=True,
        tools_mode="native",
        tool_manager=_ToolManager(),
        extra={"tools_requested": True, "event_type": "mcp_completion"},
    )

    response = provider_manager.generate(request)

    assert response.text == "ok"
    assert request.tools_on is False
    assert request.tools_payload is None
    assert request.tools_dialect is None


def test_gemini_provider_does_not_advertise_unimplemented_native_tools():
    assert GeminiProvider.supports_tools_native is False


def test_mcp_source_does_not_connect_auto_connect_false_on_startup():
    manager = _AutoConnectTrackingManager()
    source = MCPToolSource(manager, ToolManager())

    assert source.refresh(connect_if_needed=True) == {}
    assert manager.refresh_calls == 0
    assert manager.list_calls == 1


def test_mcp_completion_is_submitted_as_character_owned_internal_turn():
    captured = []
    controller = object.__new__(ModelController)
    controller.submit_internal_turn = lambda *args, **kwargs: captured.append((args, kwargs)) or True

    from managers.task_manager import Task
    task = Task(
        uid="task-1",
        status=TaskStatus.SUCCESS,
        type="codex_task",
        data={
            "character_id": "mita",
            "request_id": "request-1",
            "origin_message_id": "message-1",
            "profile": "codex",
        },
        created_at=0.0,
        updated_at=1.0,
        result={"thread_id": "thread-1", "content": "done"},
    )

    ModelController._on_mcp_task_complete(controller, task)

    assert len(captured) == 1
    args, kwargs = captured[0]
    assert args[0] == "mita"
    assert "thread-1" not in args[1]
    assert kwargs["event_type"] == "mcp_completion"
    assert kwargs["external_result"] and "thread-1" in kwargs["external_result"]
    assert kwargs["metadata"]["task_uid"] == "task-1"
    assert kwargs["metadata"]["origin_request_id"] == "request-1"


def test_mcp_connection_lists_all_tool_pages():
    config = MCPServerConfig(
        server_id="server",
        name="Server",
        enabled=True,
        transport=MCPTransportKind.STDIO,
        command="python",
    )
    connection = MCPConnection(config)

    class _Session:
        def __init__(self):
            self.calls = []

        async def list_tools(self, **kwargs):
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                return SimpleNamespace(
                    tools=[SimpleNamespace(name="first", description="First", inputSchema={"type": "object"})],
                    next_cursor="page-2",
                )
            return SimpleNamespace(
                tools=[SimpleNamespace(name="second", description="Second", inputSchema={"type": "object"})],
                next_cursor=None,
            )

    session = _Session()
    connection._session = session
    descriptors = asyncio.run(connection._list_tools_unlocked())

    assert [item.remote_name for item in descriptors] == ["first", "second"]
    assert session.calls == [{}, {"cursor": "page-2"}]


def test_internal_mcp_completion_uses_fresh_request_id_and_preserves_origin():
    class _EventBus:
        def __init__(self):
            self.events = []

        def emit(self, *args, **kwargs):
            self.events.append((args, kwargs))

    controller = object.__new__(ModelController)
    controller.event_bus = _EventBus()

    assert controller.submit_internal_turn(
        "mita",
        "A trusted completion instruction.",
        metadata={"task_uid": "task-1", "origin_request_id": "request-1"},
    )
    assert controller.submit_internal_turn(
        "mita",
        "Another trusted completion instruction.",
        metadata={"task_uid": "task-1", "origin_request_id": "request-1"},
    )

    first = controller.event_bus.events[0][0][1]
    second = controller.event_bus.events[1][0][1]
    assert first["req_id"] != second["req_id"]
    assert first["req_id"] != "request-1"
    assert first["origin_request_id"] == "request-1"
    assert second["origin_request_id"] == "request-1"


def test_mcp_background_runner_cancels_async_operation_once(loop_service):
    manager = TaskManager()
    runner = MCPBackgroundTaskRunner(manager, loop_service=loop_service)
    started = threading.Event()
    completions = []

    async def operation():
        started.set()
        await asyncio.Future()

    task = runner.submit(
        "cancellable",
        {},
        operation,
        on_complete=completions.append,
    )
    assert started.wait(timeout=2.0)
    runner.close(wait=True)

    deadline = __import__("time").monotonic() + 2.0
    while __import__("time").monotonic() < deadline:
        current = manager.get_task(task.uid)
        if current is not None and current.status is TaskStatus.CANCELLED:
            break
        __import__("time").sleep(0.01)

    current = manager.get_task(task.uid)
    assert current is not None
    assert current.status is TaskStatus.CANCELLED
    assert [item.uid for item in completions] == [task.uid]


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


def test_codex_task_tool_does_not_expose_raw_sandbox_or_approval_controls(loop_service):
    manager = _FakeCodexManager()
    task_manager = TaskManager()
    service = CodexTaskService(
        manager,
        task_manager=task_manager,
        runner=MCPBackgroundTaskRunner(task_manager, loop_service=loop_service, max_workers=1),
        project_paths={"repo": "C:/trusted/repo"},
    )
    try:
        schema = CodexTaskTool(service).parameters
        properties = schema["properties"]
        assert set(properties) == {"prompt", "mode", "project"}
        assert properties["mode"]["enum"] == ["analyze", "edit"]
        assert properties["project"]["enum"] == ["repo", "current"]
        assert "danger-full-access" not in str(schema)
        assert "approval_policy" not in str(schema)
    finally:
        service.close()


def test_codex_task_tool_rejects_untrusted_project_and_mode(loop_service):
    manager = _FakeCodexManager()
    task_manager = TaskManager()
    service = CodexTaskService(
        manager,
        task_manager=task_manager,
        runner=MCPBackgroundTaskRunner(task_manager, loop_service=loop_service),
        project_paths={"repo": "C:/trusted/repo"},
    )
    try:
        tool = CodexTaskTool(service)
        for project in ("../../", "C:\\"):
            result = tool.run_with_context(
                ToolExecutionContext(character_id="mita", request_id="request-1"),
                prompt="Edit files.",
                project=project,
            )
            assert result["accepted"] is False
        result = tool.run_with_context(
            ToolExecutionContext(character_id="mita", request_id="request-1"),
            prompt="Edit files.",
            mode="danger-full-access",
            project="repo",
        )
        assert result["accepted"] is False
        assert manager.calls == []
        assert task_manager._tasks == {}
    finally:
        service.close()


def test_codex_task_service_cancels_async_operation_on_shutdown(loop_service):
    started = threading.Event()
    completions = []

    class _AsyncCodexManager:
        async def call_tool_async(self, server_id, remote_name, arguments):
            started.set()
            await asyncio.Future()

    manager = _AsyncCodexManager()
    task_manager = TaskManager()
    service = CodexTaskService(
        manager,
        task_manager=task_manager,
        runner=MCPBackgroundTaskRunner(task_manager, loop_service=loop_service),
        on_complete=completions.append,
    )
    task = service.submit(
        "Wait for cancellation.",
        context=ToolExecutionContext(character_id="mita", request_id="request-1"),
    )
    assert started.wait(timeout=2.0)
    service.close()

    deadline = __import__("time").monotonic() + 2.0
    while __import__("time").monotonic() < deadline:
        current = task_manager.get_task(task.uid)
        if current is not None and current.status is TaskStatus.CANCELLED:
            break
        __import__("time").sleep(0.01)

    current = task_manager.get_task(task.uid)
    assert current is not None
    assert current.status is TaskStatus.CANCELLED
    assert [item.uid for item in completions] == [task.uid]


def test_codex_task_tool_returns_immediately_and_completes_in_background(loop_service):
    manager = _FakeCodexManager()
    task_manager = TaskManager()
    runner = MCPBackgroundTaskRunner(task_manager, loop_service=loop_service, max_workers=1)
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
