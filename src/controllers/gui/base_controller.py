from __future__ import annotations

import threading

from PyQt6.QtCore import QThread, QTimer
from PyQt6.QtWidgets import QApplication
from core.events import get_event_bus
from main_logger import logger


class BaseController:
    def __init__(self, main_controller, view):
        self.main_controller = main_controller
        self.view = view
        self.event_bus = get_event_bus()
        self.subscribe_to_events()

    def subscribe_to_events(self):
        pass

    def _ui(self, fn):
        if not callable(fn):
            return

        v = self.view
        sig = getattr(v, "run_ui_task_signal", None) if v is not None else None
        if sig is not None:
            try:
                sig.emit(fn)
                return
            except Exception:
                pass

        # fallback (если вдруг сигнала нет)
        if self._is_gui_thread():
            try:
                QTimer.singleShot(0, fn)
            except Exception:
                try:
                    fn()
                except Exception:
                    pass
        else:
            logger.warning("Cannot dispatch UI task: view has no run_ui_task_signal")

    def _ui_call(self, fn, default=None, timeout: float = 1.0):
        if not callable(fn):
            return default

        if self._is_gui_thread():
            try:
                return fn()
            except Exception as e:
                logger.error(f"UI call failed: {e}", exc_info=True)
                return default

        v = self.view
        sig = getattr(v, "run_ui_task_signal", None) if v is not None else None
        if sig is None:
            logger.warning("Cannot dispatch blocking UI call: view has no run_ui_task_signal")
            return default

        done = threading.Event()
        holder = {"value": default, "error": None}

        def runner():
            try:
                holder["value"] = fn()
            except Exception as e:
                holder["error"] = e
            finally:
                done.set()

        try:
            sig.emit(runner)
        except Exception as e:
            logger.error(f"UI call dispatch failed: {e}", exc_info=True)
            return default

        if not done.wait(timeout=max(0.0, float(timeout))):
            logger.warning("UI call timed out")
            return default

        if holder["error"] is not None:
            logger.error(f"UI call failed: {holder['error']}", exc_info=True)
            return default

        return holder["value"]

    @staticmethod
    def _is_gui_thread() -> bool:
        app = QApplication.instance()
        return app is None or QThread.currentThread() == app.thread()
