import sys
from pathlib import Path

PROJECT_SRC = Path(__file__).resolve().parents[2]
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from handlers.llm_providers.base import LLMRequest, LLMResponse, LLMUsage, ToolCall
from managers.tools.executor import ToolCallExecutor
from managers.tools.models import ToolExecutionContext


class _FakeToolManager:
    def __init__(self):
        self.executed = []

    def run(self, name, arguments, *, context=None):
        self.executed.append((name, arguments, context))
        return {"ok": True, "name": name}

    def mk_tool_call_msg(self, dialect_id, name, args, tool_call_id=None):
        return {
            "role": "assistant",
            "tool_call_id": tool_call_id,
            "name": name,
            "args": args,
            "dialect": dialect_id,
        }

    def mk_tool_calls_msg(self, dialect_id, calls):
        return {"role": "assistant", "tool_calls": list(calls), "dialect": dialect_id}

    def mk_tool_resp_msg(self, dialect_id, name, result, tool_call_id=None):
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": name,
            "result": result,
            "dialect": dialect_id,
        }


def test_tool_call_executor_runs_calls_and_merges_usage():
    manager = _FakeToolManager()
    req = LLMRequest(
        model="model",
        messages=[{"role": "user", "content": "run it"}],
        provider_name="common",
        tools_on=True,
        tools_dialect="openai",
        tool_manager=manager,
        extra={"request_id": "request-1", "character_id": "mita"},
    )
    generated = [
        LLMResponse(
            text=None,
            provider_name="common",
            usage=LLMUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            tool_calls=[ToolCall(id="call-1", name="lookup", arguments={"query": "status"})],
        ),
        LLMResponse(
            text="done",
            provider_name="common",
            usage=LLMUsage(prompt_tokens=2, completion_tokens=3, total_tokens=5),
        ),
    ]
    seen_messages = []

    def generate(current_req):
        seen_messages.append(list(current_req.messages))
        return generated.pop(0)

    response = ToolCallExecutor(max_depth=2).execute_until_final(generate, req)

    assert response.text == "done"
    assert response.usage.total_tokens == 7
    assert len(manager.executed) == 1
    name, arguments, context = manager.executed[0]
    assert name == "lookup"
    assert arguments == {"query": "status"}
    assert isinstance(context, ToolExecutionContext)
    assert context.character_id == "mita"
    assert context.request_id == "request-1"
    assert req.messages[-2]["role"] == "assistant"
    assert req.messages[-1]["role"] == "tool"
    assert len(seen_messages) == 2
    assert req.depth == 1


def test_tool_call_executor_batches_multiple_calls_and_keeps_result_order():
    manager = _FakeToolManager()
    req = LLMRequest(
        model="model",
        messages=[],
        provider_name="common",
        tools_on=True,
        tools_dialect="openai",
        tool_manager=manager,
    )
    generated = [
        LLMResponse(
            text=None,
            provider_name="common",
            tool_calls=[
                ToolCall(id="call-1", name="first", arguments={"value": 1}),
                ToolCall(id="call-2", name="second", arguments={"value": 2}),
            ],
        ),
        LLMResponse(text="done", provider_name="common"),
    ]

    response = ToolCallExecutor(max_depth=2).execute_until_final(
        lambda _req: generated.pop(0),
        req,
    )

    assert response.text == "done"
    assert [item[0] for item in manager.executed] == ["first", "second"]
    assert req.messages[-3]["role"] == "assistant"
    assert len(req.messages[-3]["tool_calls"]) == 2
    assert [item["role"] for item in req.messages[-2:]] == ["tool", "tool"]


def test_tool_call_executor_reuses_generated_id_for_assistant_and_tool_messages():
    manager = _FakeToolManager()
    req = LLMRequest(
        model="model",
        messages=[],
        provider_name="common",
        tools_on=True,
        tools_dialect="openai",
        tool_manager=manager,
    )
    generated = [
        LLMResponse(
            text=None,
            provider_name="common",
            tool_calls=[ToolCall(id="", name="lookup", arguments={})],
        ),
        LLMResponse(text="done", provider_name="common"),
    ]

    ToolCallExecutor(max_depth=2).execute_until_final(lambda _req: generated.pop(0), req)

    assistant_call_id = req.messages[-2]["tool_calls"][0]["tool_call_id"]
    tool_call_id = req.messages[-1]["tool_call_id"]
    assert assistant_call_id
    assert assistant_call_id == tool_call_id


def test_tool_call_executor_rejects_tool_calls_when_tools_are_disabled():
    manager = _FakeToolManager()
    req = LLMRequest(
        model="model",
        messages=[],
        provider_name="common",
        tools_on=False,
        tool_manager=manager,
    )
    generated = [
        LLMResponse(
            text=None,
            provider_name="common",
            tool_calls=[ToolCall(id="call-1", name="delete_everything", arguments={})],
        ),
        LLMResponse(text="recovered", provider_name="common"),
    ]

    response = ToolCallExecutor(max_depth=2).execute_until_final(
        lambda _req: generated.pop(0),
        req,
    )

    assert response.text == "recovered"
    assert manager.executed == []
    assert "disabled" in req.messages[-1]["result"]


def test_tool_call_executor_rejects_hallucinated_tool_outside_request_allowlist():
    manager = _FakeToolManager()
    req = LLMRequest(
        model="model",
        messages=[],
        provider_name="common",
        tools_on=True,
        tools_dialect="openai",
        tool_manager=manager,
        allowed_tool_names=frozenset({"allowed"}),
    )
    generated = [
        LLMResponse(
            text=None,
            provider_name="common",
            tool_calls=[ToolCall(id="call-1", name="not_advertised", arguments={})],
        ),
        LLMResponse(text="recovered", provider_name="common"),
    ]

    response = ToolCallExecutor(max_depth=2).execute_until_final(
        lambda _req: generated.pop(0),
        req,
    )

    assert response.text == "recovered"
    assert manager.executed == []
    assert "not_advertised" in req.messages[-1]["result"]


def test_tool_call_executor_stops_at_depth_limit():
    manager = _FakeToolManager()
    req = LLMRequest(
        model="model",
        messages=[],
        provider_name="common",
        tools_on=True,
        tool_manager=manager,
    )

    def generate(_req):
        return LLMResponse(
            text=None,
            provider_name="common",
            tool_calls=[ToolCall(id="call-1", name="lookup", arguments={})],
        )

    response = ToolCallExecutor(max_depth=1).execute_until_final(generate, req)

    assert response.text is None
    assert response.error_message == "Maximum tool-call depth reached."
    assert len(manager.executed) == 1
