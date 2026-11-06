"""Rendering of the [Available Tools] prompt block from the tool schema."""
from __future__ import annotations

import json


_EXAMPLE_ARG_VALUES = {"number": 0, "integer": 0, "boolean": True}


def _example_tool_args(tool: dict) -> dict:
    """Build a call example from the very schema the provider receives."""
    params = tool.get("parameters") or {}
    props = params.get("properties") or {}
    required = list(params.get("required") or list(props))
    args = {}
    for pname in required:
        spec = props.get(pname) if isinstance(props.get(pname), dict) else {}
        ptype = str(spec.get("type") or "")
        args[pname] = _EXAMPLE_ARG_VALUES.get(ptype, f"<{pname}>")
    return args


def render_tools_for_prompt(schema: list, *, args_as_json_string: bool = False) -> str:
    """Format the tool schema list into the [Available Tools] block.

    The catalog and the call example come from the same schema the provider
    receives, so the prompt cannot drift from the runtime tool contract.
    Providers that encode tool arguments as a string (Gemini) get the example
    in that shape.
    """
    tools = [tool for tool in schema or [] if isinstance(tool, dict) and tool.get("name")]
    if not tools:
        return ""
    lines = ["Available tools (Python tools of this chat, not Unity actions):"]
    for tool in tools:
        name = tool.get("name", "?")
        desc = tool.get("description", "")
        params_def = tool.get("parameters") or {}
        props = params_def.get("properties") or {}
        required_set = set(params_def.get("required") or ())
        param_parts = []
        for pname, pdef in props.items():
            pdef = pdef if isinstance(pdef, dict) else {}
            ptype = pdef.get("type", "any")
            pdesc = pdef.get("description", "")
            req_marker = " (REQUIRED)" if pname in required_set else ""
            param_parts.append(f"{pname}: {ptype}{req_marker}" + (f" — {pdesc}" if pdesc else ""))
        params_str = ", ".join(param_parts) if param_parts else "no parameters"
        lines.append(f"- {name}({params_str}) — {desc}")
    example_tool = next((tool for tool in tools if tool.get("name") == "load_skill"), tools[0])
    example_args = _example_tool_args(example_tool)
    if args_as_json_string:
        example_args = json.dumps(example_args, ensure_ascii=False)
    lines.append("")
    lines.append(
        'Call a tool through the top-level "tool_call" field next to "segments". '
        'Tool names never go into "intents" or "commands" — those are Unity actions.'
    )
    lines.append(
        "Example: " + json.dumps(
            {"segments": [{"text": "One short line."}],
             "tool_call": {"name": example_tool["name"], "args": example_args}},
            ensure_ascii=False,
        )
    )
    return "\n".join(lines)
