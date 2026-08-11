"""Pure transformation of performance trace snapshots into Timing UI data.

This module intentionally knows nothing about Qt.  It keeps the accounting
rules testable and prevents the dialog painter from becoming telemetry logic.
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Any


_CONTEXT_STAGES = {
    "generation.rag",
    "generation.image_description",
    "generation.prompt_build",
}
_POSTPROCESS_STAGES = {
    "generation.structured_postprocess",
    "generation.nlp_postprocess",
    "generation.history_write",
}
_MAIN_STAGE_NAMES = {
    "asr.transcribe",
    "generation.rag",
    "generation.image_description",
    "generation.prompt_build",
    "llm.total",
    "tool.call",
    "generation.structured_postprocess",
    "generation.nlp_postprocess",
    "generation.history_write",
    "tts.synthesis",
    "tts.telegram",
    "audio.playback",
}
_MARKER_NAMES = {
    "asr.text_ready",
    "response.first_visible_text",
    "response.generated",
    "response.ui_complete",
    "tts.ready",
    "audio.playback_started",
}


@dataclass(frozen=True, slots=True)
class TimingStage:
    id: str
    name: str
    start_ms: float
    duration_ms: float
    category: str
    attributes: dict[str, Any]
    parent_id: str | None = None
    level: int = 0

    @property
    def end_ms(self) -> float:
        return self.start_ms + self.duration_ms


@dataclass(frozen=True, slots=True)
class TimingMarker:
    name: str
    at_ms: float
    attributes: dict[str, Any]


@dataclass(frozen=True, slots=True)
class TimingSummary:
    total_ms: float
    response_ready_ms: float | None
    first_visible_ms: float | None
    asr_ms: float | None
    llm_ms: float
    tool_ms: float
    context_ms: float
    waits_ms: float
    postprocess_ms: float
    tts_ms: float
    playback_ms: float
    voice_ready_ms: float | None
    playback_start_ms: float | None


@dataclass(frozen=True, slots=True)
class TimingBottleneck:
    name: str
    duration_ms: float
    percent_of_total: float


@dataclass(frozen=True, slots=True)
class TimingRecentStats:
    count: int
    total_median_ms: float
    total_avg_ms: float
    first_visible_median_ms: float | None


@dataclass(frozen=True, slots=True)
class TimingViewModel:
    trace_id: str
    status: str
    source: str
    summary: TimingSummary
    bottleneck: TimingBottleneck | None
    waterfall_stages: list[TimingStage]
    detail_stages: list[TimingStage]
    markers: list[TimingMarker]
    recent_stats: TimingRecentStats | None


def timing_category(stage_name: str) -> str:
    if stage_name.startswith("asr."):
        return "asr"
    if "wait" in stage_name:
        return "wait"
    if stage_name in _CONTEXT_STAGES:
        return "context"
    if stage_name.startswith("llm."):
        return "llm"
    if stage_name == "tool.call":
        return "tool"
    if stage_name in _POSTPROCESS_STAGES:
        return "postprocess"
    if stage_name.startswith("tts."):
        return "tts"
    if stage_name == "audio.playback":
        return "playback"
    return "other"


def _format_stage_name(name: str, attributes: dict[str, Any]) -> str:
    qualifier = ""
    if name == "llm.total":
        qualifier = str(attributes.get("phase") or "")
    elif name == "tool.call":
        qualifier = str(attributes.get("tool") or "")
    elif name.startswith("tts."):
        qualifier = str(attributes.get("method") or "")
    return f"{name} [{qualifier}]" if qualifier else name


def _as_float(value: Any) -> float:
    try:
        return max(0.0, float(value or 0.0))
    except (TypeError, ValueError):
        return 0.0


def _span_stages(snapshot: dict[str, Any]) -> list[TimingStage]:
    started_ns = int(snapshot.get("started_ns") or 0)
    stages: list[TimingStage] = []
    for index, raw in enumerate(snapshot.get("spans") or []):
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "")
        if not name:
            continue
        attrs = dict(raw.get("attributes") or {})
        start_ns = int(raw.get("started_ns") or started_ns)
        start_ms = max(0.0, (start_ns - started_ns) / 1_000_000.0) if started_ns else 0.0
        stages.append(TimingStage(
            id=f"span:{index}",
            name=_format_stage_name(name, attrs),
            start_ms=start_ms,
            duration_ms=_as_float(raw.get("duration_ms")),
            category=timing_category(name),
            attributes=attrs,
        ))
    return stages


def _first_mark_offsets(snapshot: dict[str, Any]) -> dict[str, tuple[float, dict[str, Any]]]:
    result: dict[str, tuple[float, dict[str, Any]]] = {}
    for raw in snapshot.get("marks") or []:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "")
        if name and name not in result:
            result[name] = (_as_float(raw.get("elapsed_ms")), dict(raw.get("attributes") or {}))
    return result


def _synthetic_wait_stages(snapshot: dict[str, Any]) -> list[TimingStage]:
    marks = _first_mark_offsets(snapshot)
    pairs = (
        ("generation.pool_wait", "generation.enqueued", "generation.worker_started"),
        ("generation.character_lock_wait", "generation.character_lock_wait_started", "generation.character_lock_acquired"),
    )
    stages: list[TimingStage] = []
    for index, (name, start_name, end_name) in enumerate(pairs):
        start = marks.get(start_name)
        end = marks.get(end_name)
        if start is None or end is None:
            continue
        duration = max(0.0, end[0] - start[0])
        stages.append(TimingStage(
            id=f"synthetic:{index}", name=name, start_ms=start[0], duration_ms=duration,
            category="wait", attributes={},
        ))
    return stages


def _markers(snapshot: dict[str, Any]) -> list[TimingMarker]:
    marks = _first_mark_offsets(snapshot)
    return [
        TimingMarker(name=name, at_ms=value[0], attributes=value[1])
        for name, value in marks.items() if name in _MARKER_NAMES
    ]


def _summary(snapshot: dict[str, Any], stages: list[TimingStage], markers: list[TimingMarker]) -> TimingSummary:
    metrics = snapshot.get("metrics") or {}
    marker_offsets = {marker.name: marker.at_ms for marker in markers}
    by_category: dict[str, float] = {}
    for stage in stages:
        by_category[stage.category] = by_category.get(stage.category, 0.0) + stage.duration_ms
    asr = next((stage.duration_ms for stage in stages if stage.name.startswith("asr.transcribe")), None)
    return TimingSummary(
        total_ms=_as_float(snapshot.get("total_ms")),
        response_ready_ms=marker_offsets.get("response.generated"),
        first_visible_ms=marker_offsets.get("response.first_visible_text"),
        asr_ms=asr,
        llm_ms=by_category.get("llm", 0.0),
        tool_ms=by_category.get("tool", 0.0),
        context_ms=by_category.get("context", 0.0),
        waits_ms=by_category.get("wait", 0.0),
        postprocess_ms=by_category.get("postprocess", 0.0),
        tts_ms=by_category.get("tts", 0.0),
        playback_ms=by_category.get("playback", 0.0),
        voice_ready_ms=marker_offsets.get("tts.ready"),
        playback_start_ms=marker_offsets.get("audio.playback_started"),
    )


def _recent_stats(history: list[dict[str, Any]] | None, source: str) -> TimingRecentStats | None:
    comparable = [item for item in (history or []) if str(item.get("source") or "") == source]
    totals = [_as_float(item.get("total_ms")) for item in comparable if _as_float(item.get("total_ms")) > 0]
    if not totals:
        return None
    first_visible = [
        _as_float((item.get("metrics") or {}).get("first_visible_text_ms"))
        for item in comparable
        if _as_float((item.get("metrics") or {}).get("first_visible_text_ms")) > 0
    ]
    return TimingRecentStats(
        count=len(totals), total_median_ms=float(median(totals)),
        total_avg_ms=sum(totals) / len(totals),
        first_visible_median_ms=float(median(first_visible)) if first_visible else None,
    )


def build_timing_view_model(snapshot: dict[str, Any], *, history: list[dict[str, Any]] | None = None) -> TimingViewModel:
    """Build a render-ready, privacy-safe representation of one trace."""
    span_stages = _span_stages(snapshot)
    synthetic_stages = _synthetic_wait_stages(snapshot)
    details = sorted(span_stages + synthetic_stages, key=lambda stage: (stage.start_ms, stage.id))
    waterfall = [stage for stage in details if stage.name.split(" [", 1)[0] in _MAIN_STAGE_NAMES or stage.category == "wait"]
    markers = _markers(snapshot)
    summary = _summary(snapshot, details, markers)
    bottleneck_stage = max(waterfall, key=lambda stage: stage.duration_ms, default=None)
    bottleneck = None
    if bottleneck_stage is not None and bottleneck_stage.duration_ms > 0:
        bottleneck = TimingBottleneck(
            name=bottleneck_stage.name,
            duration_ms=bottleneck_stage.duration_ms,
            percent_of_total=(bottleneck_stage.duration_ms / summary.total_ms * 100.0) if summary.total_ms else 0.0,
        )
    source = str(snapshot.get("source") or "unknown")
    return TimingViewModel(
        trace_id=str(snapshot.get("trace_id") or ""), status=str(snapshot.get("status") or "unknown"), source=source,
        summary=summary, bottleneck=bottleneck, waterfall_stages=waterfall, detail_stages=details,
        markers=markers, recent_stats=_recent_stats(history, source),
    )
