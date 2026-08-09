# src/managers/tools/dialects/gemini.py
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

from .base import ToolDialect


class Dialect(ToolDialect):
    @property
    def id(self) -> str:
        return "gemini"

    @property
    def title(self) -> str:
        return "Gemini functionDeclarations"

    def build_tools_payload(self, tools_schema: List[dict]) -> Any:
        return [{"functionDeclarations": tools_schema or []}]

    def mk_tool_call_msg(self, name: str, args: dict, tool_call_id: Optional[str] = None) -> Dict[str, Any]:
        return {"role": "assistant", "content": {"functionCall": {"name": name, "args": args or {}}}}

    def mk_tool_calls_msg(self, calls: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
        return {
            "role": "assistant",
            "content": {
                "parts": [
                    {"functionCall": {"name": str(call.get("name") or ""), "args": call.get("arguments") or {}}}
                    for call in calls
                ]
            },
        }

    def mk_tool_resp_msg(self, name: str, result: str | dict, tool_call_id: Optional[str] = None) -> Dict[str, Any]:
        response = result if isinstance(result, dict) else {"result": str(result)}
        return {"role": "tool", "content": {"functionResponse": {"name": name, "response": response}}}