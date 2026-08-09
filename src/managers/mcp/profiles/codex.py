from __future__ import annotations

from typing import Any, Callable, Mapping

from managers.task_manager import Task, TaskManager, get_task_manager
from managers.tools.base import Tool
from managers.tools.models import ToolExecutionContext

from ..background_tasks import MCPBackgroundTaskRunner
from ..manager import MCPManager
from ..models import MCPCallResult
from .base import TaskExecutorProfile, TaskExecutorTurn


class CodexProfile(TaskExecutorProfile):
    def __init__(self, manager: MCPManager, *, server_id: str = "codex") -> None:
        super().__init__(
            manager,
            server_id=server_id,
            start_tool="codex",
            continue_tool="codex-reply",
        )

    @staticmethod
    def build_start_arguments(
        *,
        cwd: str | None = None,
        model: str | None = None,
        sandbox: str = "read-only",
        approval_policy: str = "on-request",
        base_instructions: str | None = None,
        developer_instructions: str | None = None,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "sandbox": sandbox,
            "approval-policy": approval_policy,
        }
        optional = {
            "cwd": cwd,
            "model": model,
            "base-instructions": base_instructions,
            "developer-instructions": developer_instructions,
        }
        result.update({key: value for key, value in optional.items() if value})
        return result


class CodexTaskService:
    def __init__(
        self,
        manager: MCPManager,
        *,
        task_manager: TaskManager | None = None,
        runner: MCPBackgroundTaskRunner | None = None,
        on_complete: Callable[[Task], None] | None = None,
    ) -> None:
        self.manager = manager
        self.task_manager = task_manager or get_task_manager()
        self.runner = runner or MCPBackgroundTaskRunner(self.task_manager)
        self.profile = CodexProfile(manager)
        self.on_complete = on_complete

    def close(self) -> None:
        self.runner.close()

    def submit(
        self,
        prompt: str,
        *,
        context: ToolExecutionContext | None = None,
        cwd: str | None = None,
        model: str | None = None,
        sandbox: str = "read-only",
        approval_policy: str = "on-request",
    ) -> Task:
        context = context or ToolExecutionContext()
        arguments = CodexProfile.build_start_arguments(
            cwd=cwd,
            model=model,
            sandbox=sandbox,
            approval_policy=approval_policy,
        )
        data = {
            "profile": "codex",
            "character_id": context.character_id,
            "request_id": context.request_id,
            "origin_message_id": context.origin_message_id,
            "prompt": str(prompt),
            "cwd": cwd or "",
            "sandbox": sandbox,
            "approval_policy": approval_policy,
        }

        def operation() -> dict[str, Any]:
            turn = self.profile.start(prompt, arguments)
            return _turn_payload(turn)

        return self.runner.submit(
            "codex_task",
            data,
            operation,
            on_complete=self.on_complete,
        )

    def continue_task(
        self,
        task_uid: str,
        prompt: str,
        *,
        context: ToolExecutionContext | None = None,
    ) -> Task:
        previous = self.task_manager.get_task(task_uid)
        if previous is None:
            raise KeyError(f"Unknown Codex task: {task_uid}")
        result = previous.result if isinstance(previous.result, Mapping) else {}
        thread_id = str(result.get("thread_id") or "").strip()
        if not thread_id:
            raise RuntimeError("Codex task has no thread id yet.")
        context = context or ToolExecutionContext()
        data = {
            "profile": "codex",
            "parent_task_id": task_uid,
            "character_id": context.character_id,
            "request_id": context.request_id,
            "origin_message_id": context.origin_message_id,
            "prompt": str(prompt),
        }

        def operation() -> dict[str, Any]:
            turn = self.profile.continue_task(thread_id, prompt)
            return _turn_payload(turn)

        return self.runner.submit(
            "codex_task_continue",
            data,
            operation,
            on_complete=self.on_complete,
        )


class CodexTaskTool(Tool):
    """Start a Codex task without blocking the active character turn."""

    @property
    def name(self) -> str:
        return "delegate_to_codex"

    @property
    def description(self) -> str:
        return (
            "Delegate a coding task to Codex. The task runs in the background and returns a task id."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
                "cwd": {"type": "string"},
                "model": {"type": "string"},
                "sandbox": {
                    "type": "string",
                    "enum": ["read-only", "workspace-write", "danger-full-access"],
                },
                "approval_policy": {
                    "type": "string",
                    "enum": ["untrusted", "on-request", "never"],
                },
            },
            "required": ["prompt"],
        }

    def __init__(self, service: CodexTaskService) -> None:
        self.service = service

    def run_with_context(self, context: ToolExecutionContext | None = None, **kwargs: Any) -> dict[str, Any]:
        prompt = str(kwargs.get("prompt") or "").strip()
        if not prompt:
            return {"accepted": False, "error": "Codex prompt must not be empty."}
        task = self.service.submit(
            prompt,
            context=context,
            cwd=_optional_string(kwargs.get("cwd")),
            model=_optional_string(kwargs.get("model")),
            sandbox=str(kwargs.get("sandbox") or "read-only"),
            approval_policy=str(kwargs.get("approval_policy") or "on-request"),
        )
        return {
            "accepted": True,
            "task_id": task.uid,
            "status": task.status.value,
        }

    def run(self, **kwargs: Any) -> dict[str, Any]:
        return self.run_with_context(None, **kwargs)


def _turn_payload(turn: TaskExecutorTurn) -> dict[str, Any]:
    result = turn.result
    return {
        "thread_id": turn.thread_id,
        "content": result.as_tool_value(),
        "is_error": result.is_error,
    }


def _optional_string(value: Any) -> str | None:
    value = str(value or "").strip()
    return value or None


__all__ = ["CodexProfile", "CodexTaskService", "CodexTaskTool"]
