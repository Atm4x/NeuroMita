from PyQt6.QtWidgets import QPushButton
from PyQt6.QtCore import QTimer, QRect
from PyQt6.QtGui import QPainter, QColor


class CooldownButton(QPushButton):
    """QPushButton that locks itself for N seconds after click and shows a progress bar."""

    def __init__(self, text: str, parent=None, lock_duration: float = 0.0):
        super().__init__(text, parent)
        self._lock_duration = float(lock_duration)
        self._remaining = 0.0

        self._tick_interval_ms = 50
        self._timer = QTimer(self)
        self._timer.setInterval(self._tick_interval_ms)
        self._timer.timeout.connect(self._tick)

        if lock_duration > 0:
            self.clicked.connect(self._on_clicked)

    def set_lock_duration(self, seconds: float) -> None:
        self._lock_duration = float(seconds)

    def start_cooldown(self, duration: float | None = None) -> None:
        """Start cooldown manually (e.g. from external code)."""
        d = duration if duration is not None else self._lock_duration
        if d <= 0:
            return
        self._remaining = float(d)
        self.setEnabled(False)
        self._timer.start()
        self.update()

    def _on_clicked(self) -> None:
        self.start_cooldown()

    def _tick(self) -> None:
        self._remaining -= self._tick_interval_ms / 1000.0
        if self._remaining <= 0.0:
            self._remaining = 0.0
            self._timer.stop()
            self.setEnabled(True)
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)

        if self._remaining <= 0.0 or self._lock_duration <= 0.0:
            return

        progress = self._remaining / self._lock_duration  # 1.0 → 0.0

        r = self.rect()
        bar_h = 3
        bar_w = int(r.width() * progress)
        bar_rect = QRect(0, r.height() - bar_h, bar_w, bar_h)

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(bar_rect, QColor(138, 43, 226, 210))
        p.end()
