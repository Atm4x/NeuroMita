"""Compact provider DTOs compiled from the internal response and request policy."""
from __future__ import annotations

import copy
import json
from functools import lru_cache
from types import UnionType
from typing import Literal, Union, get_args, get_origin

from pydantic import BaseModel, ConfigDict, Field, create_model
from pydantic_core import PydanticUndefined

from schemas.structured_response import ResponseSegment, StructuredResponse, _inline_json_schema_refs
from services.structured_response_capabilities import StructuredResponseCapabilities


class _StrictDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class SparseSegment(_StrictDTO):
    text: str


class SparseStructuredResponse(_StrictDTO):

    @classmethod
    def json_schema_dict(cls) -> dict:
        def clean(node):
            if isinstance(node, list):
                return [clean(value) for value in node]
            if not isinstance(node, dict):
                return node
            result = {key: clean(value) for key, value in node.items() if key not in {"default", "title"}}
            if "const" in result:
                result["enum"] = [result.pop("const")]
            if result.get("type") == "object":
                result["additionalProperties"] = False
                result["required"] = list(result.get("properties", {}))
            return result
        return clean(_inline_json_schema_refs(cls.model_json_schema()))

    @classmethod
    def openai_response_format(cls, **_options) -> dict:
        return {"type": "json_schema", "json_schema": {
            "name": "sparse_structured_response", "strict": True, "schema": cls.json_schema_dict(),
        }}

    @classmethod
    def gemini_schema_dict(cls, **_options) -> dict:
        return cls.json_schema_dict()


def _non_null(annotation):
    if get_origin(annotation) in (Union, UnionType):
        members = tuple(value for value in get_args(annotation) if value is not type(None))
        return members[0] if len(members) == 1 else Union[members]
    return annotation


@lru_cache(maxsize=128)
def _strict_model(model: type[BaseModel]) -> type[BaseModel]:
    fields = {}
    for name, field in model.model_fields.items():
        info = copy.deepcopy(field)
        info.default = PydanticUndefined
        info.default_factory = None
        fields[name] = (_strict_annotation(field.annotation), info)
    return create_model(f"SparseValue_{model.__name__}", __base__=_StrictDTO, **fields)


def _strict_annotation(annotation):
    origin = get_origin(annotation)
    if origin in (Union, UnionType):
        return Union[tuple(_strict_annotation(value) for value in get_args(annotation))]
    if origin is list:
        return list[_strict_annotation(get_args(annotation)[0])]
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return _strict_model(annotation)
    return annotation


@lru_cache(maxsize=128)
def build_sparse_response_model(
    model_cls: type[StructuredResponse] = StructuredResponse,
    profile: StructuredResponseCapabilities | None = None,
) -> type[SparseStructuredResponse]:
    excluded = set(profile.excluded_fields) if profile else set()
    segment_excluded = set(profile.excluded_segment_fields) if profile else set()
    events = []

    def add_event(name, annotation=None, *, segment=False, fields=None, description=""):
        properties = {"type": (Literal[name], Field(...))}
        if segment:
            properties["segment"] = (int, Field(..., ge=0, description="Zero-based index in segments"))
        if fields:
            properties.update(fields)
        else:
            properties["value"] = (_strict_annotation(annotation), Field(..., description=description))
        event = create_model(f"SparseEvent_{name}", __base__=_StrictDTO, **properties)
        events.append(event)

    for name, field in model_cls.model_fields.items():
        if name in excluded or name in {"segments", "reasoning", "secret_exposed", "custom_fields"}:
            continue
        if name == "tool_call":
            names = profile.enabled_tools if profile else ()
            add_event(name, fields={
                "name": (Literal[names] if names else str, Field(..., min_length=1)),
                "args": (str, Field(..., description="JSON-encoded object containing actual tool arguments")),
            })
        else:
            annotation = _non_null(field.annotation)
            if get_origin(annotation) is list:
                annotation = get_args(annotation)[0]
            add_event(name, annotation, description=field.description or "")

    for name, field in ResponseSegment.model_fields.items():
        if name == "text" or name in segment_excluded:
            continue
        if name == "intents":
            add_event(name, segment=True, fields={
                "intent_type": (str, Field(..., min_length=1, description="Exact verified Unity intent identifier")),
                "payload": (str, Field(..., description="JSON-encoded object matching the Unity Intent Contract")),
            })
        else:
            annotation = _non_null(field.annotation)
            if get_origin(annotation) is list:
                annotation = get_args(annotation)[0]
            add_event(name, annotation, segment=True, description=field.description or "")

    fields = {
        "segments": (list[SparseSegment], Field(...)),
        "events": (list[Union[tuple(events)]], Field(..., description="Only operations needed this turn; otherwise []")),
    }
    for name in ("reasoning", "secret_exposed", "custom_fields"):
        if name in excluded:
            continue
        info = copy.deepcopy(model_cls.model_fields[name])
        annotation = info.annotation
        if name == "custom_fields" and get_origin(_non_null(annotation)) is dict:
            annotation = str | None
            info.description = "JSON-encoded custom parameter object"
        info.default = PydanticUndefined if profile else None
        info.default_factory = None
        fields[name] = (_strict_annotation(annotation), info)
    if "reasoning" in fields:
        fields = {"reasoning": fields["reasoning"], **fields}
    wire = create_model(f"Sparse_{model_cls.__name__}", __base__=SparseStructuredResponse, **fields)
    return wire


def _json_object(value: str) -> dict:
    def reject_constant(_value):
        raise ValueError("Non-finite JSON values are not allowed")
    result = json.loads(value, parse_constant=reject_constant)
    if not isinstance(result, dict):
        raise ValueError("Event payload must decode to a JSON object")
    return result


def normalize_sparse_response(
    data: dict,
    model_cls: type[StructuredResponse] = StructuredResponse,
    profile: StructuredResponseCapabilities | None = None,
) -> dict:
    wire = build_sparse_response_model(model_cls, profile).model_validate(data)
    result = {"segments": [segment.model_dump() for segment in wire.segments]}
    for name in ("reasoning", "secret_exposed", "custom_fields"):
        if name in type(wire).model_fields:
            value = getattr(wire, name)
            if isinstance(value, BaseModel):
                value = value.model_dump()
            if name == "custom_fields" and isinstance(value, str):
                value = _json_object(value)
            result[name] = value
    singletons = set()
    for event in wire.events:
        name = event.type
        index = getattr(event, "segment", None)
        if index is not None and index >= len(result["segments"]):
            raise ValueError("Event segment index is outside segments")
        target = result if index is None else result["segments"][index]
        source = model_cls if index is None else ResponseSegment
        is_list = get_origin(_non_null(source.model_fields[name].annotation)) is list
        if not is_list:
            key = (index, name)
            if key in singletons:
                raise ValueError(f"Duplicate scalar event: {name}")
            singletons.add(key)
        if name == "tool_call":
            value = {"name": event.name, "args": _json_object(event.args)}
        elif name == "intents":
            if not event.intent_type.strip():
                raise ValueError("Intent type must not be blank")
            value = {"type": event.intent_type, "payload": _json_object(event.payload)}
        else:
            value = event.value.model_dump() if isinstance(event.value, BaseModel) else event.value
        if is_list:
            target.setdefault(name, []).append(value)
        else:
            target[name] = value
    return result


def provider_structured_model(model_cls, capabilities):
    profile = (capabilities or {}).get("structured_response_profile")
    if isinstance(profile, StructuredResponseCapabilities) and profile.sparse_enabled and issubclass(model_cls, StructuredResponse):
        return build_sparse_response_model(model_cls, profile)
    return model_cls
