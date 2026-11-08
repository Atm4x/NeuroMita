"""Regression tests for optional two-phase tool opener delivery to Unity."""
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.events import Events
from services.interim_tool_speech import supports_interim_tool_speech


def test_capability_requires_existing_opted_in_game_task():
    with patch("services.interim_tool_speech.use") as use:
        task_service = use.return_value
        task_service.get_task.return_value = SimpleNamespace(data={
            "interim_tool_speech": True, "client_id": "game-1",
        })
        assert supports_interim_tool_speech("task-1")
        task_service.get_task.return_value.data["interim_tool_speech"] = False
        assert not supports_interim_tool_speech("task-1")
        task_service.get_task.return_value.data["interim_tool_speech"] = True
        task_service.get_task.return_value.data["client_id"] = ""
        assert not supports_interim_tool_speech("task-1")
        assert not supports_interim_tool_speech(None)


def test_missing_task_does_not_enable_unversioned_interim_delivery():
    with patch("services.interim_tool_speech.use") as use:
        use.return_value.get_task.return_value = None
        assert not supports_interim_tool_speech("missing")


def test_server_routes_only_to_owning_opted_in_client():
    from controllers.server_controller import ServerController

    controller = object.__new__(ServerController)
    controller.server = MagicMock()
    event = lambda **data: SimpleNamespace(data=data)
    task = SimpleNamespace(data={"interim_tool_speech": True, "client_id": "game-1"})

    with patch("controllers.server_controller.use") as use:
        use.return_value.get_task.return_value = task
        controller._on_send_dialogue_interim(event(
            uid="task-1", opener_id="task-1:0", phase="pending", text="I'll draw."
        ))
        controller.server.schedule_send_json.assert_called_once_with("game-1", {
            "type": "dialogue_interim", "uid": "task-1", "opener_id": "task-1:0",
            "phase": "pending", "text": "I'll draw.",
        })
        controller.server.reset_mock()
        controller._on_send_dialogue_interim(event(
            uid="task-1", opener_id="task-1:0", phase="ready", text="I'll draw.",
            voiceover_path="C:/voice.wav",
        ))
        controller.server.schedule_send_json.assert_called_once_with("game-1", {
            "type": "dialogue_interim", "uid": "task-1", "opener_id": "task-1:0",
            "phase": "ready", "text": "I'll draw.", "voiceover_path": "C:/voice.wav",
        })
        controller.server.reset_mock()
        for data in (
            {"uid": "task-1", "opener_id": "other-task:0", "phase": "pending", "text": "bad"},
            {"uid": "task-1", "opener_id": "task-1:0", "phase": "SUCCESS", "text": "bad"},
            {"uid": "task-1", "opener_id": "task-1:0", "phase": "pending", "text": ""},
        ):
            controller._on_send_dialogue_interim(event(**data))
        controller.server.schedule_send_json.assert_not_called()
        task.data["interim_tool_speech"] = False
        controller._on_send_dialogue_interim(event(
            uid="task-1", opener_id="task-1:0", phase="pending", text="ignored"
        ))
        controller.server.schedule_send_json.assert_not_called()


def test_interim_tool_opener_uses_independent_audio_request():
    from controllers.model_controller import _emit_tool_turn_voiceover

    bus = MagicMock()
    meta = {"uid": "task-1", "opener_id": "task-1:0"}
    _emit_tool_turn_voiceover(
        event_bus=bus,
        settings={"USE_VOICEOVER": True},
        text="I'll draw.",
        voice_profile={"character_id": "Kind", "silero_command": "/speaker Mita"},
        char_id="Kind",
        message_id="tool-message",
        trace_id=None,
        policy=SimpleNamespace(allow_voiceover=True),
        interim_tool=meta,
    )
    bus.emit.assert_called_once()
    event_type, payload = bus.emit.call_args.args
    assert event_type == Events.Audio.VOICEOVER_REQUESTED
    assert payload["task_uid"] is None  # must never complete the parent task
    assert payload["interim_tool"] == {**meta, "text": "I'll draw."}


def test_interim_speech_without_tts_emits_text_ready_instead_of_finishing_parent():
    from controllers.model_controller import _emit_tool_turn_voiceover

    bus = MagicMock()
    meta = {"uid": "task-1", "opener_id": "task-1:0"}
    _emit_tool_turn_voiceover(
        event_bus=bus,
        settings={"USE_VOICEOVER": False},
        text="Checking...",
        voice_profile={"character_id": "Kind"},
        char_id="Kind",
        message_id="tool-message",
        trace_id=None,
        policy=SimpleNamespace(allow_voiceover=True),
        interim_tool=meta,
    )
    bus.emit.assert_called_once_with(Events.Server.SEND_DIALOGUE_INTERIM, {
        **meta, "phase": "ready", "text": "Checking...", "voiceover_path": "",
    })
