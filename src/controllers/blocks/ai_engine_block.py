from __future__ import annotations

from main_logger import logger

from .block_base import ControllerBlock
from .block_context import BlockContext


class AIEngineBlock(ControllerBlock):
    """AI engine worker process (TTS/ASR/embedding). Activated only if voice or rag is enabled."""

    name = "ai_engine"
    enabled_setting = None  # активность определяется зависимыми блоками
    default_enabled = False
    dependencies = ()

    def is_enabled(self, ctx: BlockContext) -> bool:
        # Поднимаемся, если включён хотя бы один из зависимых блоков (voice или rag).
        if ctx.cli_args is not None and getattr(ctx.cli_args, "server_only", False):
            return False
        for blk_name, settings_key in (
            ("voice", "BLOCK_VOICE_ENABLED"),
            ("rag", "BLOCK_RAG_ENABLED"),
        ):
            if ctx.cli_args is not None:
                cli_val = getattr(ctx.cli_args, f"block_{blk_name}_enabled", None)
                if cli_val is True:
                    return True
            try:
                if ctx.settings is not None and bool(ctx.settings.get(settings_key, False)):
                    return True
            except Exception:
                pass
        return False

    def initialize(self, ctx: BlockContext) -> None:
        from controllers.ai_engine_controller import AIEngineController

        controller = AIEngineController()
        self.controllers["ai_engine_controller"] = controller
        logger.notify("AIEngineController успешно инициализирован (separate process).")

    def shutdown(self) -> None:
        ctrl = self.controllers.get("ai_engine_controller")
        if not ctrl:
            return
        try:
            ctrl.shutdown(timeout=5.0)
        except Exception as e:
            logger.error(f"[AIEngineBlock] shutdown: {e}")
