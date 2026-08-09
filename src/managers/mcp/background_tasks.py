from __future__ import annotations

import asyncio
import concurrent.futures
import inspect
import threading
from typing import Any, Awaitable, Callable

from main_logger import logger
from core.services import services
from managers.task_manager import Task, TaskManager, TaskStatus, get_task_manager
from services.contracts import LoopService


class MCPBackgroundTaskRunner:
    """Run cancellable MCP operations on the application asyncio loop."""

    def __init__(
        self,
        task_manager: TaskManager | None = None,
        *,
        loop_service: LoopService | None = None,
        max_workers: int = 2,
    ) -> None:
        self.task_manager = task_manager or get_task_manager()
        self.loop_service = loop_service or services().get_optional(LoopService)
        self._max_workers = max(1, int(max_workers))
        self._lock = threading.RLock()
        self._futures: dict[concurrent.futures.Future, tuple[str, Callable[[Task], None] | None]] = {}
        self._closed = False
        if self.loop_service is None:
            raise RuntimeError("MCP background tasks require a running LoopService.")

    def submit(
        self,
        task_type: str,
        data: dict[str, Any],
        operation: Callable[[], Any | Awaitable[Any]],
        *,
        on_complete: Callable[[Task], None] | None = None,
    ) -> Task:
        with self._lock:
            if self._closed:
                raise RuntimeError("MCP background task runner is closed.")
            task = self.task_manager.create_task(task_type, data)
            coroutine = self._run_operation(task.uid, operation, on_complete)
            try:
                future = self.loop_service.run(coroutine)
            except Exception as exc:
                coroutine.close()
                failed = self.task_manager.update_task_status(
                    task.uid,
                    TaskStatus.FAILED,
                    error=str(exc),
                )
                if failed is not None and callable(on_complete):
                    on_complete(failed)
                raise
            self._futures[future] = (task.uid, on_complete)
            future.add_done_callback(self._forget_future)
            return task

    def close(self, *, wait: bool = True) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            futures = tuple(self._futures)
        for future in futures:
            future.cancel()
        if not wait:
            return
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None
        try:
            service_loop = self.loop_service.loop()
        except Exception:
            service_loop = None
        if running_loop is service_loop:
            return
        for future in futures:
            try:
                future.result()
            except (asyncio.CancelledError, concurrent.futures.CancelledError):
                pass
            except Exception:
                logger.debug("MCP task cancellation wait failed", exc_info=True)

    async def _run_operation(
        self,
        task_uid: str,
        operation: Callable[[], Any | Awaitable[Any]],
        on_complete: Callable[[Task], None] | None,
    ) -> None:
        self.task_manager.update_task_status(task_uid, TaskStatus.RUNNING)
        try:
            result = operation()
            if inspect.isawaitable(result):
                result = await result
            payload = result if isinstance(result, dict) else {"value": result}
            task = self.task_manager.update_task_status(
                task_uid,
                TaskStatus.SUCCESS,
                result=payload,
            )
        except asyncio.CancelledError:
            task = self.task_manager.update_task_status(task_uid, TaskStatus.CANCELLED)
            self._notify_completion(task, on_complete)
            raise
        except Exception as exc:
            logger.exception("MCP background task failed: %s", task_uid)
            task = self.task_manager.update_task_status(
                task_uid,
                TaskStatus.FAILED,
                error=str(exc),
            )
        self._notify_completion(task, on_complete)

    def _forget_future(self, future: concurrent.futures.Future) -> None:
        with self._lock:
            record = self._futures.pop(future, None)
        if record is None or not future.cancelled():
            return
        task_uid, on_complete = record
        task = self.task_manager.get_task(task_uid)
        if task is None or task.status is not TaskStatus.PENDING:
            return
        task = self.task_manager.update_task_status(task_uid, TaskStatus.CANCELLED)
        self._notify_completion(task, on_complete)

    @staticmethod
    def _notify_completion(task: Task | None, on_complete: Callable[[Task], None] | None) -> None:
        if task is None or not callable(on_complete):
            return
        try:
            on_complete(task)
        except Exception:
            logger.exception("MCP background task completion callback failed: %s", task.uid)


__all__ = ["MCPBackgroundTaskRunner"]
