"""SessionAction — операции над сейвами по запросу игры.

Запрос: {"action": "session", "op": <select|list|copy|delete|rename>, ...}
Ответ:  {"type": "session_result", "op": ..., "ok": bool, ...}
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from core.services import use
from services.contracts import SessionService
from game_connections.handlers.registry import RequestContext

logger = logging.getLogger(__name__)


class SessionAction:
    async def handle(self, request: Dict[str, Any], ctx: RequestContext) -> None:
        op = str(request.get("op") or "").strip().lower()
        try:
            svc = use(SessionService)
        except Exception as exc:
            await ctx.server.send_json(
                ctx.writer,
                {"type": "session_result", "op": op, "ok": False, "error": f"SessionService unavailable: {exc}"},
            )
            return

        try:
            result: Dict[str, Any] = {"type": "session_result", "op": op, "ok": True}
            if op == "select":
                sid = str(request.get("session_id") or "").strip()
                result["session_id"] = svc.switch(sid)
            elif op == "list":
                result["sessions"] = svc.list_sessions()
                result["current"] = svc.current()
            elif op == "copy":
                src = str(request.get("from") or request.get("src") or "").strip()
                dst = str(request.get("to") or request.get("dst") or "").strip()
                overwrite = bool(request.get("overwrite", False))
                result["ok"] = svc.copy(src, dst, overwrite=overwrite)
            elif op == "delete":
                result["ok"] = svc.delete(str(request.get("session_id") or "").strip())
            elif op == "rename":
                old = str(request.get("from") or request.get("old") or "").strip()
                new = str(request.get("to") or request.get("new") or "").strip()
                result["ok"] = svc.rename(old, new)
            else:
                result = {"type": "session_result", "op": op, "ok": False, "error": f"Unknown session op: {op}"}
            await ctx.server.send_json(ctx.writer, result)
        except Exception as exc:
            logger.error(f"SessionAction op={op!r} failed: {exc}", exc_info=True)
            await ctx.server.send_json(
                ctx.writer,
                {"type": "session_result", "op": op, "ok": False, "error": str(exc)},
            )
