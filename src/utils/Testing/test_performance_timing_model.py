from __future__ import annotations

import unittest

from ui.models.performance_timing_model import build_timing_view_model


def _snapshot() -> dict:
    return {
        "trace_id": "trace-1",
        "source": "desktop",
        "status": "ok",
        "started_ns": 1_000_000_000,
        "total_ms": 10_000.0,
        "marks": [
            {"name": "generation.enqueued", "elapsed_ms": 100.0},
            {"name": "generation.worker_started", "elapsed_ms": 400.0},
            {"name": "response.first_visible_text", "elapsed_ms": 4_000.0},
            {"name": "response.generated", "elapsed_ms": 6_500.0},
            {"name": "tts.ready", "elapsed_ms": 7_500.0},
        ],
        "spans": [
            {"name": "generation.prompt_build", "started_ns": 1_500_000_000, "duration_ms": 300.0, "attributes": {}},
            {"name": "llm.total", "started_ns": 1_800_000_000, "duration_ms": 4_500.0, "attributes": {"phase": "initial"}},
            {"name": "llm.attempt", "started_ns": 1_900_000_000, "duration_ms": 4_300.0, "attributes": {}},
            {"name": "tool.call", "started_ns": 6_400_000_000, "duration_ms": 700.0, "attributes": {"tool": "calculator"}},
            {"name": "tts.synthesis", "started_ns": 7_100_000_000, "duration_ms": 600.0, "attributes": {"method": "local"}},
        ],
        "metrics": {},
    }


class PerformanceTimingModelTests(unittest.TestCase):
    def test_builds_synthetic_wait_and_uses_only_waterfall_for_bottleneck(self):
        view = build_timing_view_model(_snapshot())

        self.assertEqual(view.summary.waits_ms, 300.0)
        self.assertIn("generation.pool_wait", [stage.name for stage in view.waterfall_stages])
        self.assertEqual(view.bottleneck.name, "llm.total [initial]")
        self.assertEqual(view.bottleneck.duration_ms, 4_500.0)

    def test_summary_and_recent_stats_keep_response_metrics_separate_from_full_pipeline(self):
        history = [_snapshot(), {**_snapshot(), "total_ms": 12_000.0}]
        view = build_timing_view_model(_snapshot(), history=history)

        self.assertEqual(view.summary.first_visible_ms, 4_000.0)
        self.assertEqual(view.summary.response_ready_ms, 6_500.0)
        self.assertEqual(view.summary.voice_ready_ms, 7_500.0)
        self.assertEqual(view.summary.total_ms, 10_000.0)
        self.assertEqual(view.recent_stats.count, 2)
        self.assertEqual(view.recent_stats.total_median_ms, 11_000.0)

    def test_marker_and_stage_labels_include_safe_technical_qualifiers(self):
        view = build_timing_view_model(_snapshot())

        self.assertIn("tool.call [calculator]", [stage.name for stage in view.detail_stages])
        self.assertIn("tts.synthesis [local]", [stage.name for stage in view.detail_stages])
        self.assertEqual(
            [marker.name for marker in view.markers],
            ["response.first_visible_text", "response.generated", "tts.ready"],
        )


if __name__ == "__main__":
    unittest.main()
