# src/managers/tools/dialects/openai.py
from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .base import ToolDialect


class Dialect(ToolDialect):
    @property
    def id(self) -> str:
        return "openai"

    @property
    def title(self) -> str:
        return "OpenAI-compatible"

    def build_tools_payload(self, tools_schema: List[dict]) -> Any:
        return tools_schema or []

    def mk_tool_call_msg(self, name: str, args: dict, tool_call_id: Optional[str] = None) -> Dict[str, Any]:
        call_id = tool_call_id or f"call_{uuid.uuid4().hex[:8]}"
        return {
            "role": "assistant",
            "tool_calls": [{
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(args or {}, ensure_ascii=False)}
            }]
        }

    def mk_tool_calls_msg(self, calls: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
        tool_calls = []
        for call in calls:
            call_id = call.get("tool_call_id") or f"call_{uuid.uuid4().hex[:8]}"
            tool_calls.append({
                "id": call_id,
                "type": "function",
                "function": {
                    "name": str(call.get("name") or ""),
                    "arguments": json.dumps(call.get("arguments") or {}, ensure_ascii=False),
                },
            })
        return {"role": "assistant", "tool_calls": tool_calls}

    def mk_tool_resp_msg(self, name: str, result: str | dict, tool_call_id: Optional[str] = None) -> Dict[str, Any]:
        call_id = tool_call_id or f"call_{uuid.uuid4().hex[:8]}"
        content = json.dumps(result, ensure_ascii=False) if isinstance(result, dict) else str(result)
        return {"role": "tool", "tool_call_id": call_id, "content": content}