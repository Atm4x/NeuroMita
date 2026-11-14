from __future__ import annotations

from typing import Any, Dict

from core.services import services
from game_connections.handlers.registry import RequestContext
from main_logger import logger
from services.contracts import DesktopWatchService, SettingsService, SpeechService


class DesktopStateAction:
    """Состояние desktop-оверлея: позиция окна, активность, включена ли слежка.

    Оверлей присылает его при подключении, при изменениях и раз в несколько
    секунд как heartbeat. Захват требует явного watching_screen и разрешений
    настроек; подключение само по себе его не запускает.
    """

    async def handle(self, request: Dict[str, Any], ctx: RequestContext) -> None:
        server = ctx.server
        payload = request.get("desktop_state")
        state = payload if isinstance(payload, dict) else request

        server.set_desktop_voice_request(ctx.client_id, state.get("voice_input") is True)
        settings = services().get_optional(SettingsService)

        if settings is not None and not settings.get("DESKTOP_MODE_ACTIVE", False):
            settings.set("DESKTOP_MODE_ACTIVE", True)
            logger.info("[Desktop] оверлей подключился — режим рабочего стола активен")

        watch = services().get_optional(DesktopWatchService)
        effective = server.set_desktop_watch_request(ctx.client_id, state.get("watching_screen") is True)
        desktop = watch.apply_desktop_state({**state, "watching_screen": effective}) if watch is not None else {}
        speech = services().get_optional(SpeechService)
        microphone = {"status": "unavailable"}
        if settings is not None and speech is not None:
            capture = speech.capture_state()
            status = ("disabled" if not capture.enabled else
                      "starting" if not capture.ready else
                      "manual" if capture.mode != "vad" else
                      "game" if server.primary_client_id() else
                      "paused" if not capture.permitted else "ready")
            microphone = {"status": status, "mode": capture.mode}
        await server.send_json(ctx.writer, {
            "type": "desktop_state_ack",
            "desktop_state": desktop,
            "watching": bool(watch.is_watching()) if watch is not None else False,
            "microphone": microphone,
        })
