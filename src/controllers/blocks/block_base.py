from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple

from .block_context import BlockContext


class ControllerBlock(ABC):
    """Functional group of controllers initialized as a unit.

    Subclasses populate `controllers` in `initialize()`. The block is skipped
    by the registry if `is_enabled()` returns False (CLI override > settings).
    """

    name: str = ""
    enabled_setting: Optional[str] = None
    default_enabled: bool = False
    dependencies: Tuple[str, ...] = ()

    def __init__(self) -> None:
        self.controllers: Dict[str, Any] = {}
        self.active: bool = False

    def is_enabled(self, ctx: BlockContext) -> bool:
        if ctx.cli_args is not None and self.enabled_setting:
            cli_attr = self.enabled_setting.lower()
            cli_val = getattr(ctx.cli_args, cli_attr, None)
            if cli_val is not None:
                return bool(cli_val)
            if getattr(ctx.cli_args, "server_only", False):
                return False
        if self.enabled_setting is None:
            return True
        if ctx.settings is None:
            return self.default_enabled
        try:
            return bool(ctx.settings.get(self.enabled_setting, self.default_enabled))
        except Exception:
            return self.default_enabled

    @abstractmethod
    def initialize(self, ctx: BlockContext) -> None:
        ...

    def shutdown(self) -> None:
        return None

    def get(self, controller_name: str) -> Optional[Any]:
        return self.controllers.get(controller_name)
