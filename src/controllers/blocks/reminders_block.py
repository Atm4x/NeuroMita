from __future__ import annotations

from main_logger import logger

from .block_base import ControllerBlock
from .block_context import BlockContext


class RemindersBlock(ControllerBlock):
    name = "reminders"
    enabled_setting = "BLOCK_REMINDERS_ENABLED"
    default_enabled = False
    dependencies = ()

    def initialize(self, ctx: BlockContext) -> None:
        from controllers.reminder_controller import ReminderController

        reminder = ReminderController(ctx.settings)
        self.controllers["reminder_controller"] = reminder
        logger.notify("ReminderController успешно инициализирован.")
