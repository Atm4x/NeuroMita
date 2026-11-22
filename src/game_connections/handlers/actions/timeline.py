from __future__ import annotations

import asyncio

from core.services import use
from services.unity_sessions import UnitySessions
from domain.timeline import InvalidTimelineOperation, TimelineConflict
from core.state_barrier import StateUnavailable


class TimelineAction:
    async def handle(self, request, ctx):
        response = {"type": "timeline_result", "req_id": request.get("req_id"), "protocol_version": 1}
        try:
            response["body"] = await asyncio.to_thread(use(UnitySessions).handle, request)
            response["ok"] = True
        except Exception as exc:
            message = str(exc) if isinstance(exc, (InvalidTimelineOperation, TimelineConflict, StateUnavailable)) else (
                "Не удалось выполнить операцию истории. Проверьте соединение и незавершённые переходы.")
            response.update(ok=False, error=type(exc).__name__,
                            message=message)
        await ctx.server.send_json(ctx.writer, response)
