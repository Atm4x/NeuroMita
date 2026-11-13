import asyncio
from unittest.mock import Mock, patch

from game_connections.handlers.actions import create_task as module


def registry(watch):
    return Mock(get_optional=Mock(return_value=watch))


def test_desktop_images_return_capture_when_watching():
    watch = Mock()
    watch.is_watching.return_value = True
    watch.capture_desktop_now.return_value = [b"jpeg"]
    with patch.object(module, "services", return_value=registry(watch)):
        assert asyncio.run(module._desktop_images()) == [b"jpeg"]
    watch.capture_desktop_now.assert_called_once_with(1)


def test_desktop_images_do_not_capture_when_disabled():
    watch = Mock()
    watch.is_watching.return_value = False
    with patch.object(module, "services", return_value=registry(watch)):
        assert asyncio.run(module._desktop_images()) == []
    watch.capture_desktop_now.assert_not_called()


def test_desktop_images_drop_frame_when_disabled_during_capture():
    watch = Mock()
    watch.is_watching.side_effect = [True, False]
    watch.capture_desktop_now.return_value = [b"jpeg"]
    with patch.object(module, "services", return_value=registry(watch)):
        assert asyncio.run(module._desktop_images()) == []


def test_desktop_images_allow_text_when_capture_fails():
    watch = Mock()
    watch.is_watching.return_value = True
    watch.capture_desktop_now.side_effect = RuntimeError("capture unavailable")
    with patch.object(module, "services", return_value=registry(watch)):
        assert asyncio.run(module._desktop_images()) == []


def test_desktop_images_allow_text_without_watch_service():
    with patch.object(module, "services", return_value=registry(None)):
        assert asyncio.run(module._desktop_images()) == []
