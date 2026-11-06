"""Request-scoped native tool policy and the structured-runtime boundary."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
import logging

from handlers.llm_providers.base import ToolResult
from handlers.llm_providers.protocols.history import normalize_history_message, normalize_tool_call_history
from schemas.structured_response import StructuredResponse, ToolCall
from services.structured_response_capabilities import StructuredResponseCapabilities


NATIVE_DIALECTS = frozenset({'openai_chat_completions', 'openai_responses'})

logger = logging.getLogger(__name__)


# Intents that may be lifted into tool calls, with the arguments each one needs.
# Nothing outside this table is ever converted, so a Unity intent cannot turn
# into a tool call just because the two share a name.
BRIDGEABLE_TOOL_INTENTS = {
    "load_skill": ("ids", "id"),
}


def resolve_tool_mode(settings, capabilities, dialect_id):
    profile = capabilities.get('structured_response_profile')
    requested = str(settings.get('TOOLS_MODE', 'native')).strip().lower()
    active = isinstance(profile, StructuredResponseCapabilities) and profile.can_call_tools
    if not active or requested == 'off':
        return {'requested': requested, 'effective': 'off', 'reason': 'tools_unavailable'}
    if (requested == 'native'
            and capabilities.get('structured_output', False)
            and capabilities.get('native_structured_output', True)
            and not capabilities.get('native_tools_with_structured_output', True)):
        return {'requested': requested, 'effective': 'schema',
                'reason': 'native_tools_with_structured_output_unsupported'}
    if requested == 'native' and dialect_id in NATIVE_DIALECTS and capabilities.get('tools_native', False):
        return {'requested': requested, 'effective': 'native', 'reason': None}
    return {'requested': requested, 'effective': 'schema',
            'reason': 'native_protocol_unsupported' if requested == 'native' else None}


def configure_native_tools(req, settings, tool_manager):
    decision = resolve_tool_mode(settings, req.capabilities, req.dialect_id)
    if tool_manager is None:
        decision = {**decision, 'effective': 'off', 'reason': 'tool_manager_unavailable'}
    req.tools_mode = decision['effective']
    req.extra['tool_mode'] = decision
    req.capabilities['tool_mode'] = decision
    profile = req.capabilities.get('structured_response_profile')
    req.tools_on = req.tools_mode == 'native'
    req.tools_payload = tool_manager._filtered_schema(list(profile.enabled_tools)) if req.tools_on else None
    req.tools_on = bool(req.tools_on and req.tools_payload)
    req.tools_dialect = req.dialect_id if req.tools_on else None
    req.depth = profile.tool_depth if isinstance(profile, StructuredResponseCapabilities) else 0
    if req.tools_on:
        excluded = set(profile.excluded_fields) | {'tool_call'}
        req.capabilities['structured_response_profile'] = replace(profile, excluded_fields=tuple(sorted(excluded)))
        req.capabilities['structured_exclude_fields'] = tuple(sorted(excluded))
        req.capabilities['structured_prompt_features'] = req.capabilities['structured_response_profile'].prompt_features()
    elif req.tools_mode == 'schema':
        excluded = set(profile.excluded_fields) - {'tool_call'}
        req.capabilities['structured_response_profile'] = replace(profile, excluded_fields=tuple(sorted(excluded)))
        req.capabilities['structured_exclude_fields'] = tuple(sorted(excluded))
    return decision


def bridge_native_tool_response(response, req, *, model_cls=StructuredResponse):
    calls = getattr(response, 'tool_calls', []) or []
    text = response.text or ''
    response.raw = dict(response.raw or {})
    response.raw.pop('native_tool_call', None)
    response.raw.pop('native_tool_history', None)
    response.raw['tool_mode'] = deepcopy(req.extra.get('tool_mode') or {'effective': req.tools_mode})
    if req.tools_mode == 'native' and not calls and text.strip().startswith('{'):
        try:
            schema_data = json.loads(text)
        except ValueError:
            schema_data = None
        if isinstance(schema_data, dict) and _has_schema_tool_call(schema_data):
            raise ValueError('Schema tool calls are forbidden in native mode')
    if not calls:
        return response
    if len(calls) != 1:
        raise ValueError('The runtime supports one native tool call per turn')
    call = calls[0]
    profile = req.capabilities.get('structured_response_profile')
    advertised = {str((tool.get('function') or tool).get('name') or '') for tool in req.tools_payload or []}
    if (not req.tools_on or req.tools_mode != 'native' or not isinstance(profile, StructuredResponseCapabilities)
            or not profile.can_call_tools or call.name not in profile.enabled_tools or call.name not in advertised):
        raise ValueError('The model requested an unadvertised or disabled native tool')
    if not isinstance(call.id, str) or not call.id.strip() or not isinstance(call.arguments, dict):
        raise ValueError('Native tool call requires a call ID and object arguments')
    if any(message.get('role') == 'tool' and message.get('tool_call_id') == call.id for message in req.messages):
        raise ValueError('Native tool call ID was already executed in this request')
    if text.strip().startswith(('{', '[')):
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError('Native tool structured content must be an object')
    else:
        data = {'segments': [{'text': text}] if text else []}
    if _has_schema_tool_call(data):
        raise ValueError('Schema and native tool calls cannot be combined')
    if 'changes' in data or 'events' in data:
        from schemas.sparse_structured_response import normalize_sparse_response
        data = normalize_sparse_response(data, model_cls, profile)
    data['tool_call'] = {'name': call.name, 'args': deepcopy(call.arguments)}
    raw = dict(response.raw or {})
    raw['native_tool_call'] = {
        'name': call.name, 'arguments': deepcopy(call.arguments), 'id': call.id,
        'assistant_text': text or None,
        'protocol_history': deepcopy(response.protocol_history),
    }
    response.raw = raw
    response.text = json.dumps(data, ensure_ascii=False)
    return response


def native_tool_followup_messages(call, result):
    content = str(result)
    if (call.get('name') == 'load_skill' and '[skill:' in content
            and not content.lstrip().startswith('[LOADED SKILLS]')):
        # The native tool-role reply needs the same section marker as schema
        # mode so the context viewer can identify freshly loaded instructions.
        content = f'[LOADED SKILLS]\n{content}\n[/LOADED SKILLS]'
    output = ToolResult(id=call['id'], content=content)
    assistant = {'role': 'assistant', 'content': call.get('assistant_text'), 'tool_calls': [{
        'id': call['id'], 'type': 'function', 'function': {
            'name': call['name'], 'arguments': json.dumps(call['arguments'], ensure_ascii=False)}}]}
    history = normalize_tool_call_history(call)
    if history:
        assistant['protocol_history'] = history
    return [assistant, {'role': 'tool', 'tool_call_id': output.id, 'content': output.content}]


def lift_tool_intent(structured: StructuredResponse, enabled_tools) -> str:
    """Move an explicitly bridged tool from intents onto the tool-call field.

    A model that cannot emit tool_call sometimes asks through intents:
    {"type": "load_skill", "payload": "wardrobe"}. Unity knows no such
    intent, so the request would be dropped and the turn would end without the
    follow-up request that reads the skill.

    Only BRIDGEABLE_TOOL_INTENTS entries are converted, only while that tool is
    enabled for the request, and only with a complete, correctly typed argument
    set. Anything else stays where the model put it: guessing arguments would
    run a tool the model did not actually ask for. Returns the lifted name.
    """
    names = {str(name).strip() for name in (enabled_tools or ()) if str(name).strip()}
    if not names:
        return ""

    lifted = ""
    for segment in getattr(structured, "segments", None) or []:
        intents = list(getattr(segment, "intents", None) or [])
        kept = []
        changed = False
        for intent in intents:
            name = str(getattr(intent, "type", "") or "").strip()
            required = BRIDGEABLE_TOOL_INTENTS.get(name)
            if required is None:
                if name in names:
                    logger.warning(
                        "[ToolIntentBridge] Tool %r was sent as a Unity intent; "
                        "only %s can be bridged.",
                        name, sorted(BRIDGEABLE_TOOL_INTENTS),
                    )
                kept.append(intent)
                continue
            if name not in names:
                kept.append(intent)
                continue
            changed = True
            args = _bridge_arguments(name, getattr(intent, "payload", None), required)
            if args is None:
                continue
            if lifted:
                logger.warning(
                    "[ToolIntentBridge] Dropping a second %r request: one tool call per turn.",
                    name,
                )
                continue
            lifted = name
            structured.tool_call = ToolCall(name=name, args=args)
        if changed:
            segment.intents = kept
    return lifted


def _bridge_arguments(name, payload, required):
    """Return validated arguments for a bridged intent, or None when unsure."""
    payload = payload if isinstance(payload, dict) else {}
    args = {}
    for key in required:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            args[key] = value.strip()
        elif isinstance(value, (list, tuple)):
            values = [str(item).strip() for item in value if isinstance(item, str) and str(item).strip()]
            if values:
                args[key] = values
    if not args:
        logger.warning(
            "[ToolIntentBridge] %r came through intents without a usable argument; "
            "not lifting it.",
            name,
        )
        return None
    unknown = sorted(set(payload) - set(required))
    if unknown:
        logger.warning(
            "[ToolIntentBridge] Ignoring unknown %r arguments from intents: %s",
            name, unknown,
        )
    return args


def _has_schema_tool_call(data):
    return data.get('tool_call') is not None or any(
        isinstance(change, dict) and change.get('type') == 'tool_call' for change in data.get('changes') or [])


def validate_runtime_native_call(call, structured_call, *, profile, tools_on, enabled_tools, depth, max_depth, mode):
    if (mode != 'native' or not tools_on or not isinstance(profile, StructuredResponseCapabilities)
            or not profile.can_call_tools or not profile.at_tool_depth(max(depth, profile.tool_depth)).can_call_tools
            or depth >= max_depth or not isinstance(call, dict)
            or not isinstance(call.get('id'), str) or not call['id'].strip()
            or call.get('name') not in profile.enabled_tools or call.get('name') not in (enabled_tools or ())
            or not isinstance(call.get('arguments'), dict) or structured_call is None
            or structured_call.name != call['name'] or structured_call.args != call['arguments']):
        raise ValueError('Native tool call is not allowed by the runtime request profile')


def persisted_native_tool_messages(structured_data):
    if not isinstance(structured_data, dict):
        return []
    messages = structured_data.get('native_tool_history')
    if not isinstance(messages, list) or len(messages) != 2 or not all(isinstance(message, dict) for message in messages):
        return []
    assistant, result = messages
    assistant = normalize_history_message(assistant)
    calls = assistant.get('tool_calls')
    if (assistant.get('role') != 'assistant' or result.get('role') != 'tool'
            or not isinstance(calls, list) or len(calls) != 1 or not isinstance(calls[0], dict)
            or not calls[0].get('id') or calls[0]['id'] != result.get('tool_call_id')
            or not isinstance(result.get('content'), str)):
        return []
    function = calls[0].get('function')
    if not isinstance(function, dict) or not function.get('name'):
        return []
    historical_content = result['content']
    if function['name'] == 'load_skill':
        # Tool replies must remain paired with their assistant tool calls, but
        # replaying the full skill body from old turns bypasses skill retention,
        # including scope changes that deliberately invalidate loaded skills.
        # The immediately following tool request still receives the full body;
        # this abbreviation is only for replay of earlier conversation turns.
        historical_content = (
            '[Previous load_skill result omitted from history. '
            'Call load_skill again if this scene needs those instructions.]'
        )
    return [deepcopy({key: value for key, value in assistant.items()
                      if key in {'role', 'content', 'tool_calls', 'protocol_history'}}),
            {'role': 'tool', 'tool_call_id': result['tool_call_id'], 'content': historical_content}]
