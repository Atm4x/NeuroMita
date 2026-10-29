from __future__ import annotations

import threading
from typing import Any, List

from core.desktop_context import format_desktop_context, normalize_desktop_context
from core.desktop_watch import WatchProfile, profile_from_settings
from core.error_utils import format_exception
from core.events import get_event_bus
from core.services import use
from handlers.screen_handler import ScreenCapture
from main_logger import logger
from services.contracts import DesktopWatchService, SettingsService


class DesktopWatchController(DesktopWatchService):
    """Фоновое наблюдение за рабочим столом для режима «Мита на рабочем столе».

    Кадры копятся в собственном буфере и никуда не отправляются сами: забирает их
    только desktop-клиент, когда решает отреагировать. Своё окно Unity исключает
    через WDA_EXCLUDEFROMCAPTURE, поэтому чёрная заплатка по HWND здесь не нужна.
    """

    _SETTING_KEYS = frozenset({
        "DESKTOP_WATCH_INTERVAL",
        "DESKTOP_WATCH_QUALITY",
        "DESKTOP_WATCH_FRAME_WIDTH",
        "DESKTOP_WATCH_FRAME_HEIGHT",
        "DESKTOP_WATCH_HISTORY_LIMIT",
        "DESKTOP_WATCH_TRANSFER_LIMIT",
    })

    def __init__(self, settings=None):
        self.settings = settings or use(SettingsService)
        self.event_bus = get_event_bus()
        self._capture = ScreenCapture()
        self._profile = profile_from_settings(self.settings)
        self._lock = threading.Lock()
        self._desktop_state: dict = {}
        self._settings_subscription = self.settings.subscribe(
            self._on_setting_changed, keys=self._SETTING_KEYS
        )
        self.start()

    def start(self) -> bool:
        if not self.settings.get("ENABLE_IMAGE_ANALYSIS", True):
            logger.info("[DesktopWatch] обработка изображений отключена — наблюдение не запускается")
            return False
        if self._capture.is_running():
            return True
        self._profile = profile_from_settings(self.settings)
        self._capture.start_capture(
            interval_seconds=self._profile.interval_seconds,
            quality=self._profile.quality,
            fps=1,
            max_history_frames=self._profile.history_limit,
            max_transfer_frames=self._profile.transfer_limit,
            capture_width=self._profile.width,
            capture_height=self._profile.height,
        )
        logger.info(f"[DesktopWatch] фоновое наблюдение запущено: {self._profile.describe()}")
        return self._capture.is_running()

    def stop(self) -> None:
        if self._capture.is_running():
            self._capture.stop_capture()
            logger.info("[DesktopWatch] фоновое наблюдение остановлено")

    def shutdown(self) -> None:
        try:
            self._settings_subscription()
        except Exception as exc:
            logger.debug(f"[DesktopWatch] отписка от настроек не удалась: {format_exception(exc)}")
        self.stop()

    @property
    def profile(self) -> WatchProfile:
        return self._profile

    def is_watching(self) -> bool:
        return self._capture.is_running()

    def desktop_frames(self, limit: int = 1) -> List[Any]:
        count = max(1, min(int(limit), self._profile.transfer_limit))
        return list(self._capture.get_recent_frames(count))

    def capture_desktop_now(self, limit: int = 1) -> List[Any]:
        frames = self.desktop_frames(limit)
        if frames:
            return frames
        frame = self._capture.capture_one_shot(
            self._profile.quality, self._profile.width, self._profile.height
        )
        return [frame] if frame else []

    def apply_desktop_state(self, state: Any) -> dict:
        desktop = normalize_desktop_context(state)
        with self._lock:
            self._desktop_state = desktop
        return desktop

    def desktop_state(self) -> dict:
        with self._lock:
            return dict(self._desktop_state)

    def prompt_block(self) -> str:
        return format_desktop_context(self.desktop_state())

    def status(self) -> dict:
        return {
            "watching": self.is_watching(),
            "profile": self._profile.describe(),
            "desktop": self.desktop_state(),
        }

    def _on_setting_changed(self, change) -> None:
        if getattr(change, "key", None) not in self._SETTING_KEYS:
            return
        logger.info(f"[DesktopWatch] профиль захвата изменён ({change.key}) — перезапуск")
        self.stop()
        self.start()
