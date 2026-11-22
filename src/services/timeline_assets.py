from __future__ import annotations

import base64
import binascii

from domain.timeline import InvalidTimelineOperation
from domain.timeline.assets import TimelineAsset, TimelineAssetStore, asset_references


class TimelineContent:
    """Explicit boundary between semantic attachment references and provider/UI data."""

    def __init__(self, store: TimelineAssetStore | None):
        self.store = store

    def freeze_message(self, message: dict) -> dict:
        result = dict(message)
        content = result.get("content")
        if not isinstance(content, list):
            return result
        parts = []
        for original in content:
            part = dict(original) if isinstance(original, dict) else original
            if isinstance(part, dict) and part.get("type") == "image_url":
                image_url = part.get("image_url")
                url = image_url.get("url", "") if isinstance(image_url, dict) else image_url
                if isinstance(url, str) and url.startswith("data:image/"):
                    if self.store is None:
                        raise InvalidTimelineOperation("Image persistence requires a timeline attachment store")
                    header, separator, encoded = url.partition(",")
                    if not separator or not header.endswith(";base64"):
                        raise InvalidTimelineOperation("An inline image must be base64 encoded")
                    try:
                        data = base64.b64decode(encoded, validate=True)
                    except (ValueError, binascii.Error) as exc:
                        raise InvalidTimelineOperation("Invalid inline image data") from exc
                    asset = TimelineAsset.create(header[5:-7], data)
                    self.store.put(asset)
                    part.pop("image_url", None)
                    part.update(asset.reference())
            parts.append(part)
        result["content"] = parts
        return result

    def materialize(self, messages) -> tuple[dict, ...]:
        hydrated = []
        assets = {}
        for message in messages:
            result = dict(message)
            content = result.get("content")
            if isinstance(content, list):
                parts = []
                for original in content:
                    part = dict(original) if isinstance(original, dict) else original
                    if isinstance(part, dict) and part.get("type") == "image_ref":
                        reference = asset_references(part)[part["asset_id"]]
                        if self.store is None:
                            raise InvalidTimelineOperation("Attachment content is unavailable")
                        identity = reference["asset_id"]
                        if identity not in assets:
                            asset = self.store.get(identity)
                            assets[identity] = (asset, f"data:{asset.media_type};base64," + base64.b64encode(asset.data).decode("ascii"))
                        asset, url = assets[identity]
                        if asset.media_type != reference["media_type"] or len(asset.data) != reference["byte_size"]:
                            raise InvalidTimelineOperation("Attachment reference differs from stored content")
                        part = {key: value for key, value in part.items() if key not in {"asset_id", "media_type", "byte_size"}}
                        part.update(type="image_url", image_url={"url": url})
                    parts.append(part)
                result["content"] = parts
            hydrated.append(result)
        return tuple(hydrated)
