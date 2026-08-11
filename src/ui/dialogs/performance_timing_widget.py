"""Timing tab widgets for the request/response context viewer."""
from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, Callable

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ui.models.performance_timing_model import TimingViewModel, build_timing_view_model
from utils import getTranslationVariant as _


_CATEGORY_COLORS = {
    "asr": "#22D3EE",
    "wait": "#FBBF24",
    "context": "#34D399",
    "llm": "#A78BFA",
    "tool": "#FB923C",
    "postprocess": "#60A5FA",
    "tts": "#F472B6",
    "playback": "#E879F9",
    "other": "#9CA3AF",
}


def _format_ms(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value / 1000.0:.2f} s" if value >= 1000 else f"{value:.0f} ms"


class TimingWaterfallWidget(QWidget):
    """Compact painter-based waterfall; raw trace parsing stays in the model."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view: TimingViewModel | None = None
        self.setMinimumHeight(120)
        self.setMouseTracking(True)

    def set_view_model(self, view: TimingViewModel | None) -> None:
        self._view = view
        rows = len(view.waterfall_stages) if view else 0
        self.setMinimumHeight(max(120, 50 + rows * 31))
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#1E1E2E"))
        view = self._view
        if view is None or not view.waterfall_stages:
            painter.setPen(QColor("#9CA3AF"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, _("Нет измеренных этапов", "No measured stages"))
            return

        label_width = min(270, max(180, self.width() // 3))
        chart_left = label_width + 12
        chart_right = self.width() - 12
        chart_width = max(1, chart_right - chart_left)
        total = max(view.summary.total_ms, max(stage.end_ms for stage in view.waterfall_stages))
        total = max(total, 1.0)
        fm = QFontMetrics(painter.font())

        painter.setPen(QColor("#9CA3AF"))
        painter.drawText(chart_left, 18, "0 s")
        painter.drawText(chart_right - fm.horizontalAdvance(_format_ms(total)), 18, _format_ms(total))
        for marker in view.markers:
            x = chart_left + int(chart_width * marker.at_ms / total)
            painter.setPen(QPen(QColor("#5A5A70"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(x, 24, x, self.height() - 8)

        for row, stage in enumerate(view.waterfall_stages):
            y = 31 + row * 31
            text = fm.elidedText(stage.name, Qt.TextElideMode.ElideRight, label_width - 8)
            painter.setPen(QColor("#EAEAEA"))
            painter.drawText(4, y + 15, text)
            x = chart_left + int(chart_width * stage.start_ms / total)
            width = max(2, int(chart_width * stage.duration_ms / total))
            color = QColor(_CATEGORY_COLORS.get(stage.category, _CATEGORY_COLORS["other"]))
            painter.fillRect(x, y + 3, width, 17, color)
            painter.setPen(QColor("#CFCFE6"))
            painter.drawText(min(chart_right - 55, x + width + 5), y + 15, _format_ms(stage.duration_ms))

    def mouseMoveEvent(self, event) -> None:
        view = self._view
        row = (event.position().y() - 31) // 31
        if view is None or row < 0 or row >= len(view.waterfall_stages):
            self.setToolTip("")
            return super().mouseMoveEvent(event)
        stage = view.waterfall_stages[int(row)]
        hints = {
            "generation.pool_wait": _(
                "Ожидание свободного worker в очереди генерации.",
                "Time spent waiting for a free worker in the generation executor.",
            ),
            "generation.character_lock_wait": _(
                "Ожидание завершения другой генерации того же персонажа.",
                "Waiting for another generation of the same character to release its serialization lock.",
            ),
        }
        self.setToolTip(hints.get(stage.name, ""))
        return super().mouseMoveEvent(event)


class PerformanceTimingPanel(QWidget):
    """Render and refresh Timing data supplied by the context dialog."""

    def __init__(
        self,
        snapshot_getter: Callable[[], dict[str, Any] | None],
        history_getter: Callable[[], list[dict[str, Any]]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._snapshot_getter = snapshot_getter
        self._history_getter = history_getter
        self._view: TimingViewModel | None = None
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        header = QFrame()
        header.setObjectName("HeaderFrame")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(12, 8, 12, 8)
        self._status_label = QLabel()
        self._status_label.setObjectName("HeaderLabel")
        self._bottleneck_label = QLabel()
        self._bottleneck_label.setObjectName("HeaderLabel")
        header_layout.addWidget(self._status_label)
        header_layout.addWidget(self._bottleneck_label)
        root.addWidget(header)

        summary = QFrame()
        summary.setObjectName("HeaderFrame")
        self._summary_grid = QGridLayout(summary)
        self._summary_grid.setContentsMargins(12, 8, 12, 8)
        self._summary_grid.setHorizontalSpacing(24)
        self._summary_grid.setVerticalSpacing(5)
        self._summary_labels: dict[str, QLabel] = {}
        for index, (key, title) in enumerate((
            ("total", _("Полный путь", "Full pipeline")),
            ("first_visible", _("Первый текст", "First visible text")),
            ("response_ready", _("Ответ готов", "Response ready")),
            ("llm", "LLM total"),
            ("context", _("Контекст", "Context")),
            ("waits", _("Очередь / ожидание", "Queue / waits")),
            ("tools", _("Инструменты", "Tool calls")),
            ("postprocess", _("Постобработка", "Postprocess")),
            ("tts", "TTS"),
            ("playback", _("Воспроизведение", "Playback")),
        )):
            row, col = divmod(index, 2)
            label = QLabel(f"<span style='color:#9CA3AF'>{title}</span>")
            value = QLabel("—")
            self._summary_grid.addWidget(label, row, col * 2)
            self._summary_grid.addWidget(value, row, col * 2 + 1)
            self._summary_labels[key] = value
        root.addWidget(summary)

        toolbar = QHBoxLayout()
        self._recent_cb = QCheckBox(_("Недавняя статистика", "Recent statistics"))
        self._recent_cb.toggled.connect(self._render_recent_stats)
        toolbar.addWidget(self._recent_cb)
        toolbar.addStretch()
        refresh_btn = QPushButton(_("Обновить", "Refresh"))
        refresh_btn.clicked.connect(self.refresh)
        toolbar.addWidget(refresh_btn)
        copy_btn = QPushButton(_("Копировать тайминги", "Copy timings"))
        copy_btn.clicked.connect(self._copy_timings)
        toolbar.addWidget(copy_btn)
        root.addLayout(toolbar)

        self._recent_label = QLabel()
        self._recent_label.setWordWrap(True)
        self._recent_label.setStyleSheet("color:#9CA3AF; padding: 2px 4px;")
        self._recent_label.setVisible(False)
        root.addWidget(self._recent_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._waterfall = TimingWaterfallWidget()
        scroll.setWidget(self._waterfall)
        root.addWidget(scroll, stretch=1)

        self._details = QTextBrowser()
        self._details.setMinimumHeight(120)
        root.addWidget(self._details)

    def refresh(self) -> None:
        snapshot = self._snapshot_getter()
        self._view = build_timing_view_model(snapshot, history=self._history_getter()) if snapshot else None
        self._waterfall.set_view_model(self._view)
        if self._view is None:
            self._status_label.setText(_("Данных timing для этого запроса нет.", "No timing data is available for this request."))
            self._bottleneck_label.setText("")
            for label in self._summary_labels.values():
                label.setText("—")
            self._details.setPlainText("")
            self._render_recent_stats()
            return

        view = self._view
        self._status_label.setText(f"<b>Status:</b> {view.status.upper()} &nbsp;&nbsp; <b>Trace:</b> {view.trace_id[:12]}…")
        if view.bottleneck:
            self._bottleneck_label.setText(
                f"<b>{_('Крупнейший этап', 'Largest contributor')}:</b> {view.bottleneck.name} — "
                f"{_format_ms(view.bottleneck.duration_ms)} ({view.bottleneck.percent_of_total:.0f}%)"
            )
        else:
            self._bottleneck_label.setText("")
        summary = view.summary
        values = {
            "total": summary.total_ms, "first_visible": summary.first_visible_ms,
            "response_ready": summary.response_ready_ms, "llm": summary.llm_ms,
            "context": summary.context_ms, "waits": summary.waits_ms, "tools": summary.tool_ms,
            "postprocess": summary.postprocess_ms, "tts": summary.tts_ms, "playback": summary.playback_ms,
        }
        for key, value in values.items():
            self._summary_labels[key].setText(_format_ms(value) if value or value is None else "—")
        detail_lines = []
        for stage in view.detail_stages:
            attrs = ", ".join(f"{key}={value}" for key, value in stage.attributes.items())
            suffix = f"  ({attrs})" if attrs else ""
            detail_lines.append(f"{stage.start_ms:8.1f} ms  {stage.duration_ms:8.1f} ms  {stage.name}{suffix}")
        self._details.setPlainText("\n".join(detail_lines))
        self._render_recent_stats()

    def _render_recent_stats(self) -> None:
        visible = self._recent_cb.isChecked()
        self._recent_label.setVisible(visible)
        stats = self._view.recent_stats if self._view else None
        if not visible:
            return
        if stats is None:
            self._recent_label.setText(_("Нет сопоставимых завершённых запросов.", "No comparable completed requests."))
            return
        first = _format_ms(stats.first_visible_median_ms) if stats.first_visible_median_ms is not None else "—"
        self._recent_label.setText(
            f"{stats.count} { _('завершённых запросов', 'completed requests')}: "
            f"median total {_format_ms(stats.total_median_ms)}, average {_format_ms(stats.total_avg_ms)}, "
            f"median first text {first}."
        )

    def _copy_timings(self) -> None:
        if self._view is None:
            return
        payload = {
            "trace_id": self._view.trace_id,
            "status": self._view.status,
            "source": self._view.source,
            "summary": asdict(self._view.summary),
            "bottleneck": asdict(self._view.bottleneck) if self._view.bottleneck else None,
            "stages": [asdict(stage) for stage in self._view.detail_stages],
            "markers": [asdict(marker) for marker in self._view.markers],
        }
        QApplication.clipboard().setText(json.dumps(payload, ensure_ascii=False, indent=2))
