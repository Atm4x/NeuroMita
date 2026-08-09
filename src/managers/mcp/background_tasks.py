from __future__ import annotations

import concurrent.futures
import threading
from typing import Any, Callable

from main_logger import logger
from managers.task_manager import Task, TaskManager, TaskStatus, get_task_manager


class MCPBackgroundTaskRunner:
    """Run long MCP operations without blocking the LLM request thread."""

    def __init__(
        self,
        task_manager: TaskManager | None = None,
        *,
        max_workers: int = 2,
    ) -> None:
        self.task_manager = task_manager or get_task_manager()
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max(1, int(max_workers)),
            thread_name_prefix="neuromita-mcp-task",
        )
        self._lock = threading.RLock()
        self._futures: set[concurrent.futures.Future] = set()
        self._closed = False

    def submit(
        self,
        task_type: str,
        data: dict[str, Any],
        operation: Callable[[], Any],
        *,
        on_complete: Callable[[Task], None] | None = None,
    ) -> Task:
        with self._lock:
            if self._closed:
                raise RuntimeError("MCP background task runner is closed.")
            task = self.task_manager.create_task(task_type, data)
            future = self._executor.submit(
                self._run_operation,
                task.uid,
                operation,
                on_complete,
            )
            self._futures.add(future)
            future.add_done_callback(self._forget_future)
            return task

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            futures = tuple(self._futures)
        for future in futures:
            future.cancel()
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _run_operation(
        self,
        task_uid: str,
        operation: Callable[[], Any],
        on_complete: Callable[[Task], None] | None,
    ) -> None:
        self.task_manager.update_task_status(task_uid, TaskStatus.RUNNING)
        try:
            result = operation()
            payload = result if isinstance(result, dict) else {"value": result}
            task = self.task_manager.update_task_status(
                task_uid,
                TaskStatus.SUCCESS,
                result=payload,
            )
        except concurrent.futures.CancelledError:
            task = self.task_manager.update_task_status(task_uid, TaskStatus.CANCELLED)
        except Exception as exc:
            logger.exception("MCP background task failed: %s", task_uid)
            task = self.task_manager.update_task_status(
                task_uid,
                TaskStatus.FAILED,
                error=str(exc),
            )
        if task is not None and callable(on_complete):
            try:
                on_complete(task)
            except Exception:
                logger.exception("MCP background task completion callback failed: %s", task_uid)

    def _forget_future(self, future: concurrent.futures.Future) -> None:
        with self._lock:
            self._futures.discard(future)


__all__ = ["MCPBackgroundTaskRunner"]
