from __future__ import annotations

import math


def _seconds(key: str, default: float, *, allow_auto: bool = False) -> float:
    from managers.settings_manager import SettingsManager

    try:
        seconds = float(SettingsManager.get(key, default))
    except (TypeError, ValueError):
        return default
    if not math.isfinite(seconds) or seconds < 0 or (seconds == 0 and not allow_auto):
        return default
    if allow_auto and seconds == 0:
        return 0.0
    return min(3600.0, max(1.0, seconds))


def embedding_timeout() -> float:
    return _seconds("RAG_EMBED_TIMEOUT_SEC", 60.0)


def reranker_timeout(candidate_count: int) -> float:
    configured = _seconds("RAG_RERANK_TIMEOUT_SEC", 0.0, allow_auto=True)
    return configured or max(30.0, min(3600.0, float(max(1, candidate_count)) * 10.0))
