"""Prompt contract rendered from the exact sparse wire DTO."""
from __future__ import annotations

import json

from schemas.sparse_structured_response import build_sparse_response_model
from schemas.structured_response import StructuredResponse


def render_sparse_response_contract(profile, model_cls=StructuredResponse, *, reply_limits=None) -> str:
    wire = build_sparse_response_model(model_cls or StructuredResponse, profile)
    schema = wire.json_schema_dict()
    lines = [
        "[Structured Response Contract: sparse_events_v1]",
        "This contract defines the JSON wire format for this request and supersedes field layouts in older examples or history.",
        'Return one JSON object with required "segments": [{"text": "spoken words"}] and "events": []. No text outside JSON.',
        "Segment objects contain ONLY text. It contains spoken words, never XML tags or action descriptions.",
        "Put only operations needed this turn in events. Do not emit null, zero or empty-list events for unused operations.",
        "Instructions elsewhere referring to a response field mean the event of that type. For example, a segment's commands becomes a commands event with segment index and one command as value.",
        "Each list item is its own event; preserve their order. A scalar event may appear only once per type/segment. Never repeat actions from previous turns.",
        "Segment events require segment: the zero-based index of the corresponding text segment. Actions trigger with that segment; target means the exact active character identifier for its spoken text.",
        "Only the following event shapes are allowed for this request:",
    ]
    variants = schema["properties"]["events"]["items"]["anyOf"]
    event_names = {variant["properties"]["type"]["enum"][0] for variant in variants}
    for variant in variants:
        properties = variant["properties"]
        shape = {}
        for name, value in properties.items():
            if name == "type":
                shape[name] = value["enum"][0]
            elif "enum" in value:
                shape[name] = "one of: " + ", ".join(value["enum"])
            else:
                shape[name] = "<" + str(value.get("type", "object")) + ">"
        description = properties.get("value", {}).get("description", "")
        lines.append(json.dumps(shape, ensure_ascii=False) + (" — " + description if description else ""))
        if properties.get("value", {}).get("type") == "object":
            lines.append("Value object schema: " + json.dumps(properties["value"], ensure_ascii=False))

    root_fields = set(schema["properties"]) - {"segments", "events"}
    if root_fields:
        lines.append("Additional required ROOT fields for this request: " + ", ".join(sorted(root_fields)) + ".")
    if "reasoning" in root_fields:
        lines.append("Write reasoning before segments. Keep it brief; it is never shown to the player.")
    if "secret_exposed" in root_fields:
        lines.append('"secret_exposed" is required by the active schema: decide true/false, or null when no reveal decision is needed. Do not put it in events.')
    if "custom_fields" in root_fields:
        lines.append('"custom_fields" is a required root object: fill all declared custom parameters using their specified types and limits, never invent keys.')
        lines.append("Custom parameter schema: " + json.dumps(schema["properties"]["custom_fields"], ensure_ascii=False))
    lines.extend([
        "Do not put any other legacy fields at the root or inside segments. Use their event shapes above.",
        'Base example (include any additional required root fields listed above): {"segments":[{"text":"Hello."}],"events":[]}',
        'Memory example event: {"type":"memory_add","value":"island:language|Русский. Отвечай Игроку по-русски."}',
        "Create memory only for stable preferences, promises, relationship shifts or important story facts; update near-duplicates. Do not memorize greetings or temporary world state.",
        "Memory islands: island:<type>|content updates the existing island. Types: relationship, opinion, preferences, commitments_conflicts, language.",
        "The language island stores the Player's primary conversation language. If absent, infer it from the first clear natural-language Player message and create the language island. Change it only on an explicit request to switch; quotes, code and isolated foreign words do not change it. Reply in the stored language.",
        "Stat deltas are normally absent (internally 0). Use small changes, usually -2..2, only for actual feeling changes; retain the current scale.",
        "Speak concisely, usually 1-3 segments. Length limits apply to total spoken text across segments. Split only when emotion, action, target or a significant beat changes.",
        "Use only commands and intent identifiers explicitly exposed by the current runtime. Intent types are not command strings; do not guess Cat or other identifiers: use exact runtime payload keys and values.",
        "Physical events from [Unity Runtime Events] should get a bodily reaction or gaze first, then words, when those actions are available.",
        "[SYSTEM INFO] is system information, not Player speech; [SPEAKER] identifies multi-speaker dialogue.",
    ])
    if reply_limits:
        lines.append(
            f"Ordinary reply: {reply_limits['REPLY_TARGET_MIN_WORDS']}-{reply_limits['REPLY_TARGET_MAX_WORDS']} words total. "
            f"Hard maximum: {reply_limits['REPLY_HARD_MAX_WORDS']} words, {reply_limits['REPLY_MAX_SEGMENTS']} segments. "
            f"Usually at most {reply_limits['REPLY_SEGMENT_MAX_WORDS']} words per segment. Reply style: {reply_limits['REPLY_STYLE']}."
        )
    if "tool_call" in event_names:
        lines.extend([
            'tool_call event: choose only a tool from [Available Tools]. args is a JSON object ENCODED AS A STRING, e.g. "{\\\"expression\\\":\\\"2+2\\\"}". Fill actual required arguments.',
            "Use a short acknowledgement segment (2-5 words). Tool names never belong in commands. The tool result arrives in the next turn; then answer fully.",
        ])
    if "intents" in event_names:
        lines.append("intents event: intent_type is the verified Unity intent identifier; payload is a JSON object encoded as a string. Use dialogue.continue only when immediate continuation is intended.")
    return "\n".join(lines)
