from __future__ import annotations

from typing import Any, Optional

from main_logger import logger

from .block_base import ControllerBlock
from .block_context import BlockContext


class GuiBlock(ControllerBlock):
    """GUI controllers (PyQt6). Created lazily via attach_view() after the main window exists.

    initialize() only marks the block as active; the actual GuiController is constructed
    when MainController.update_view() calls attach_view(). This avoids importing PyQt6
    in headless mode.
    """

    name = "gui"
    enabled_setting = "BLOCK_GUI_ENABLED"
    default_enabled = True
    dependencies = ()

    def __init__(self) -> None:
        super().__init__()
        self._main_controller: Optional[Any] = None

    def initialize(self, ctx: BlockContext) -> None:
        # Сохраняем ссылку, чтобы потом передать в GuiController.
        self._main_controller = ctx.main_controller
        # GuiController создаётся в attach_view() после показа окна.

    def attach_view(self, view: Any) -> Optional[Any]:
        if "gui_controller" in self.controllers:
            return self.controllers["gui_controller"]
        if self._main_controller is None:
            logger.warning("[GuiBlock] attach_view() вызван без main_controller")
            return None
        from controllers.gui_controller import GuiController

        gui = GuiController(self._main_controller, view)
        self.controllers["gui_controller"] = gui
        logger.notify("GuiController успешно инициализирован.")
        return gui
