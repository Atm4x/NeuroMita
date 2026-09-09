from __future__ import annotations

from dataclasses import dataclass
from typing import Any


ASR_CAPTURE_SAMPLE_RATE = 16000

_WINDOWS_DEFAULT_INPUT_ALIASES = frozenset(
    {
        "microsoft sound mapper - input",
        "primary sound capture driver",
        "первичный драйвер записи звука",
        "первичный драйвер захвата звука",
    }
)


@dataclass(frozen=True)
class ASRInputDevice:
    index: int
    name: str
    host_api: str
    default_sample_rate: float | None = None

    @property
    def option_text(self) -> str:
        return f"{self.name} ({self.index})"


def normalize_device_name(value: Any) -> str:
    return " ".join(str(value or "").split()).casefold()


def _host_api_priority(host_api: str) -> int:
    normalized = str(host_api or "").casefold()
    if "wasapi" in normalized:
        return 0
    if "directsound" in normalized:
        return 1
    if normalized == "mme" or " mme" in normalized:
        return 2
    return 3


def _host_api_name(sounddevice, device: Any) -> str:
    try:
        host_api = sounddevice.query_hostapis(int(device.get("hostapi")))
        return str(host_api.get("name") or "").strip()
    except Exception:
        return ""


def _supports_asr_capture(sounddevice, index: int, sample_rate: int) -> bool:
    checker = getattr(sounddevice, "check_input_settings", None)
    if not callable(checker):
        return True
    try:
        checker(
            device=int(index),
            channels=1,
            dtype="float32",
            samplerate=int(sample_rate),
        )
        return True
    except Exception:
        return False


def list_asr_input_devices(
    sounddevice,
    *,
    sample_rate: int = ASR_CAPTURE_SAMPLE_RATE,
) -> list[ASRInputDevice]:
    """Return one compatible PortAudio endpoint for each input-device name.

    PortAudio exposes the same Windows endpoint through several host APIs.  The
    ASR capture loop uses blocking ``InputStream.read()``, so WDM-KS endpoints
    must not be offered: that host API rejects blocking streams.  Of the other
    representations, keep the best one that can actually open the ASR format.
    """

    selected: dict[tuple[str, int], ASRInputDevice] = {}
    order: list[tuple[str, int]] = []
    occurrences: dict[tuple[str, str], int] = {}

    for index, device in enumerate(sounddevice.query_devices()):
        try:
            if int(device.get("max_input_channels", 0) or 0) <= 0:
                continue
        except Exception:
            continue

        name = " ".join(str(device.get("name") or f"Device {index}").split())
        key = normalize_device_name(name)
        if not key:
            continue

        host_api = _host_api_name(sounddevice, device)
        occurrence_key = (host_api.casefold(), key)
        occurrence = occurrences.get(occurrence_key, 0)
        occurrences[occurrence_key] = occurrence + 1
        physical_key = (key, occurrence)

        # These are PortAudio aliases for the Windows default input, not
        # additional microphones.  Keeping them would reintroduce a duplicate
        # for whichever physical endpoint is currently the system default.
        if key in _WINDOWS_DEFAULT_INPUT_ALIASES:
            continue

        if "wdm-ks" in host_api.casefold():
            continue
        if not _supports_asr_capture(sounddevice, index, sample_rate):
            continue

        try:
            default_rate = float(device.get("default_samplerate"))
        except (TypeError, ValueError):
            default_rate = None

        candidate = ASRInputDevice(
            index=int(index),
            name=name,
            host_api=host_api,
            default_sample_rate=default_rate,
        )
        current = selected.get(physical_key)
        if current is None:
            selected[physical_key] = candidate
            order.append(physical_key)
        elif _host_api_priority(candidate.host_api) < _host_api_priority(current.host_api):
            selected[physical_key] = candidate

    return [selected[key] for key in order]


def resolve_asr_input_device(
    sounddevice,
    *,
    requested_index: int | None,
    requested_name: str | None,
    sample_rate: int = ASR_CAPTURE_SAMPLE_RATE,
) -> ASRInputDevice | None:
    """Resolve persisted selection to a currently compatible PortAudio index."""

    devices = list_asr_input_devices(sounddevice, sample_rate=sample_rate)
    if not devices:
        return None

    try:
        requested_index_value = int(requested_index) if requested_index is not None else None
    except (TypeError, ValueError):
        requested_index_value = None

    requested_key = normalize_device_name(requested_name)
    if requested_key:
        same_name = [
            device
            for device in devices
            if normalize_device_name(device.name) == requested_key
        ]
        for device in same_name:
            if device.index == requested_index_value:
                return device
        if same_name:
            return same_name[0]

    if requested_index_value is not None:
        for device in devices:
            if device.index == requested_index_value:
                return device

    try:
        default_device = sounddevice.default.device
        try:
            default_input = int(default_device[0])
        except (TypeError, IndexError, KeyError):
            default_input = int(default_device)
    except Exception:
        default_input = -1
    for device in devices:
        if device.index == default_input:
            return device

    return devices[0]
