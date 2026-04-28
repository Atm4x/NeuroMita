from __future__ import annotations

from main_logger import logger

from .block_base import ControllerBlock
from .block_context import BlockContext


class TelegramBlock(ControllerBlock):
    name = "telegram"
    enabled_setting = "BLOCK_TELEGRAM_ENABLED"
    default_enabled = False
    dependencies = ()

    def initialize(self, ctx: BlockContext) -> None:
        from controllers.telegram_controller import TelegramController

        controller = TelegramController()
        self.controllers["telegram_controller"] = controller
        logger.notify("TelegramController успешно инициализирован.")
