from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


PROJECT_SRC = Path(__file__).resolve().parents[2]
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from controllers.chat_controller import ChatController
from core.events import Events


class _EventBusStub:
    def __init__(self) -> None:
        self.emitted: list[tuple[str, dict]] = []

    def emit(self, event_name: str, data: dict) -> None:
        self.emitted.append((event_name, data))


class ChatRetryTests(unittest.TestCase):
    def _controller(self) -> tuple[ChatController, _EventBusStub]:
        controller = ChatController.__new__(ChatController)
        bus = _EventBusStub()
        controller.event_bus = bus
        controller._last_ui_request = {"req_id": "newest", "character_id": "Crazy"}
        controller._ui_requests_by_message_id = {
            "in:older": {"req_id": "older", "character_id": "Crazy"},
        }
        return controller, bus

    def test_retry_uses_request_matched_to_clicked_failed_message(self) -> None:
        controller, bus = self._controller()

        controller._on_retry_last(SimpleNamespace(data={
            "message_id": "in:older",
            "character_id": "Crazy",
        }))

        self.assertEqual(
            bus.emitted,
            [
                (Events.GUI.CLEAR_CHAT_MESSAGE_ERROR, {
                    "message_id": "in:older",
                    "character_id": "Crazy",
                }),
                (Events.Chat.SEND_MESSAGE, {"req_id": "older", "character_id": "Crazy"}),
            ],
        )

    def test_retry_does_not_substitute_newest_request_when_message_id_is_unknown(self) -> None:
        controller, bus = self._controller()

        controller._on_retry_last(SimpleNamespace(data={
            "message_id": "in:missing",
            "character_id": "Crazy",
        }))

        self.assertEqual(bus.emitted, [])


if __name__ == "__main__":
    unittest.main()
