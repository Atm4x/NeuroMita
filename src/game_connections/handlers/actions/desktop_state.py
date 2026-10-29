from __future__ import annotations

from typing import Any, Dict

from core.services import services
from game_connections.handlers.registry import RequestContext
from main_logger import logger
from services.contracts import DesktopWatchService, SettingsService


class DesktopStateAction:
    """Состояние desktop-оверлея: позиция окна, активность, включена ли слежка.

    Оверлей присылает его при подключении, при изменениях и раз в несколько
    секунд как heartbeat. Само подключение с ролью desktop включает режим
    рабочего стола, из-за чего в Python поднимается фоновое наблюдение.
    """

    async def handle(self, request: Dict[str, Any], ctx: RequestContext) -> None:
        server = ctx.server
        payload = request.get("desktop_state")
        state = payload if isinstance(payload, dict) else request

        settings = services().get_optional(SettingsService)
        watch = services().get_optional(DesktopWatchService)

        if settings is not None and not settings.get("DESKTOP_MODE_ACTIVE", False):
            settings.set("DESKTOP_MODE_ACTIVE", True)
            logger.info("[Desktop] оверлей подключился — режим рабочего стола активен")

        desktop = watch.apply_desktop_state(state) if watch is not None else {}
        await server.send_json(ctx.writer, {
            "type": "desktop_state_ack",
            "desktop_state": desktop,
            "watching": bool(watch.is_watching()) if watch is not None else False,
        })
