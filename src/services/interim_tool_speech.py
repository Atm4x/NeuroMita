"""Opt-in capability for independently delivered Unity tool openers.

Legacy Unity clients receive buffered openers with the final v3 response.
"""
from core.services import use
from services.contracts import TaskService


def supports_interim_tool_speech(task_uid: str | None) -> bool:
    if not task_uid:
        return False
    try:
        task = use(TaskService).get_task(task_uid)
    except (LookupError, RuntimeError):
        return False
    return bool(
        task is not None
        and isinstance(task.data, dict)
        and task.data.get("interim_tool_speech") is True
        and task.data.get("client_id")
    )
