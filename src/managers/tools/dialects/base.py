# src/managers/tools/dialects/base.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Mapping, Optional, Sequence


class ToolDialect(ABC):
    @property
    @abstractmethod
    def id(self) -> str: ...

    @property
    def title(self) -> str:
        return self.id

    @abstractmethod
    def build_tools_payload(self, tools_schema: List[dict]) -> Any:
        pass

    @abstractmethod
    def mk_tool_call_msg(self, name: str, args: dict, tool_call_id: Optional[str] = None) -> Dict[str, Any]:
        pass

    def mk_tool_calls_msg(self, calls: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
        """Build one assistant message containing all calls from one model turn."""
        if len(calls) != 1:
            raise NotImplementedError(f"Dialect {self.id} does not support batched tool calls")
        call = calls[0]
        return self.mk_tool_call_msg(
            name=str(call.get("name") or ""),
            args=dict(call.get("arguments") or {}),
            tool_call_id=call.get("tool_call_id"),
        )

    @abstractmethod
    def mk_tool_resp_msg(
        self,
        name: str,
        result: str | dict,
        tool_call_id: Optional[str] = None
    ) -> Dict[str, Any]:
        pass