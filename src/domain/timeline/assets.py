from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol

from .errors import InvalidTimelineOperation


def canonical_media_type(value: str) -> str:
    media_type = str(value).strip().lower()
    if media_type == "image/jpg":
        media_type = "image/jpeg"
    if not re.fullmatch(r"[a-z0-9][a-z0-9!#$&^_.+-]*/[a-z0-9][a-z0-9!#$&^_.+-]*", media_type):
        raise InvalidTimelineOperation("Invalid attachment media type")
    return media_type


@dataclass(frozen=True, slots=True)
class TimelineAsset:
    asset_id: str
    media_type: str
    data: bytes

    @classmethod
    def create(cls, media_type: str, data: bytes) -> TimelineAsset:
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise InvalidTimelineOperation("Attachment content must be bytes")
        media_type = canonical_media_type(media_type)
        data = bytes(data)
        identity = "sha256:" + sha256(media_type.encode("ascii") + b"\0" + data).hexdigest()
        return cls(identity, media_type, data)

    def validate(self) -> None:
        if TimelineAsset.create(self.media_type, self.data) != self:
            raise InvalidTimelineOperation("Attachment identity or media type does not match its content")

    def reference(self) -> dict:
        return {"type": "image_ref", "asset_id": self.asset_id,
                "media_type": self.media_type, "byte_size": len(self.data)}


class TimelineAssetStore(Protocol):
    def put(self, asset: TimelineAsset) -> None: ...

    def get(self, asset_id: str) -> TimelineAsset: ...


def asset_references(value) -> dict[str, dict]:
    found = {}

    def visit(item):
        if isinstance(item, dict):
            if item.get("type") == "image_ref":
                asset_id = item.get("asset_id")
                media_type = item.get("media_type")
                size = item.get("byte_size")
                if (not isinstance(asset_id, str) or not re.fullmatch(r"sha256:[a-f0-9]{64}", asset_id)
                        or type(size) is not int or size < 0 or canonical_media_type(media_type) != media_type):
                    raise InvalidTimelineOperation("Invalid image attachment reference")
                reference = {"asset_id": asset_id, "media_type": media_type, "byte_size": size}
                if asset_id in found and found[asset_id] != reference:
                    raise InvalidTimelineOperation("Contradictory attachment references")
                found[asset_id] = reference
            for child in item.values():
                visit(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                visit(child)

    visit(value)
    return found
