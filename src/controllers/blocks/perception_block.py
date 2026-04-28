from __future__ import annotations

from main_logger import logger

from .block_base import ControllerBlock
from .block_context import BlockContext


class PerceptionBlock(ControllerBlock):
    name = "perception"
    enabled_setting = "BLOCK_PERCEPTION_ENABLED"
    default_enabled = False
    dependencies = ()

    def initialize(self, ctx: BlockContext) -> None:
        from controllers.capture_controller import CaptureController

        capture = CaptureController(ctx.settings)
        self.controllers["capture_controller"] = capture
        logger.notify("CaptureController успешно инициализирован.")

    def shutdown(self) -> None:
        capture = self.controllers.get("capture_controller")
        if not capture:
            return
        try:
            capture.stop_screen_capture_thread()
        except Exception as e:
            logger.error(f"[PerceptionBlock] stop_screen_capture_thread: {e}")
        try:
            capture.stop_camera_capture_thread()
        except Exception as e:
            logger.error(f"[PerceptionBlock] stop_camera_capture_thread: {e}")
