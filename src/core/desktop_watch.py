from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

TV_OBSERVATION_REFERENCE = (
    "TV observation samples a 512 px JPEG-40 frame roughly every 2.5 s while a video plays and "
    "hands 3 frames to the model per reaction; the desktop profile stays inside that budget."
)


def _as_float(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError, OverflowError):
        return fallback


def _as_int(value: Any, fallback: int) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError, OverflowError):
        return fallback


@dataclass(frozen=True)
class WatchProfile:
    interval_seconds: float = 15.0
    quality: int = 40
    width: int = 512
    height: int = 384
    history_limit: int = 3
    transfer_limit: int = 1

    def normalized(self) -> "WatchProfile":
        return replace(
            self,
            interval_seconds=min(600.0, max(2.0, self.interval_seconds)),
            quality=min(100, max(10, self.quality)),
            width=min(3840, max(256, self.width)),
            height=min(2160, max(144, self.height)),
            history_limit=min(8, max(1, self.history_limit)),
            transfer_limit=min(8, max(1, self.transfer_limit)),
        )

    @property
    def frames_per_minute(self) -> float:
        return 60.0 / self.interval_seconds

    def describe(self) -> str:
        return (
            f"one {self.width}x{self.height} JPEG frame (quality {self.quality}) every "
            f"{self.interval_seconds:g} s, keeping {self.history_limit}, sending up to {self.transfer_limit}"
        )


DEFAULT_PROFILE = WatchProfile()


def profile_from_settings(settings: Any) -> WatchProfile:
    def read(key: str, fallback: Any) -> Any:
        if settings is None:
            return fallback
        try:
            return settings.get(key, fallback)
        except Exception:
            return fallback

    return WatchProfile(
        interval_seconds=_as_float(read("DESKTOP_WATCH_INTERVAL", DEFAULT_PROFILE.interval_seconds), DEFAULT_PROFILE.interval_seconds),
        quality=_as_int(read("DESKTOP_WATCH_QUALITY", DEFAULT_PROFILE.quality), DEFAULT_PROFILE.quality),
        width=_as_int(read("DESKTOP_WATCH_FRAME_WIDTH", DEFAULT_PROFILE.width), DEFAULT_PROFILE.width),
        height=_as_int(read("DESKTOP_WATCH_FRAME_HEIGHT", DEFAULT_PROFILE.height), DEFAULT_PROFILE.height),
        history_limit=_as_int(read("DESKTOP_WATCH_HISTORY_LIMIT", DEFAULT_PROFILE.history_limit), DEFAULT_PROFILE.history_limit),
        transfer_limit=_as_int(read("DESKTOP_WATCH_TRANSFER_LIMIT", DEFAULT_PROFILE.transfer_limit), DEFAULT_PROFILE.transfer_limit),
    ).normalized()
