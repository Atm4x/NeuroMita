"""Regression tests for structured Unity replies racing with voice generation."""
import asyncio
from unittest.mock import Mock, patch

from controllers.audio_controller import AudioController
from controllers.chat_controller import ChatController
from core.events import Events
from managers.task_manager import TaskManager, TaskStatus
from services.contracts import GameLinkService, LocalVoiceService


def _reply():
    return ChatController._build_task_result(
        "I cast a spell",
        {"segments": [{
            "text": "I cast a spell",
            "intents": [{"type": "mita.effect.apply", "payload": {
                "effect_id": "drowsiness", "target": "self", "seconds": 60,
            }}],
        }]},
    )


def _audio_with_task_updates(manager):
    audio = AudioController.__new__(AudioController)
    audio.settings = {"VOICEOVER_LOCAL_CHAT": False}
    audio.waiting_answer = True
    audio.event_bus = Mock()
    updates = []

    def emit(name, data=None):
        if name == Events.Task.UPDATE_TASK_STATUS:
            updates.append(data)
            manager.update_task_status(
                data["uid"], data["status"], data.get("result"), data.get("error"),
            )

    audio.event_bus.emit.side_effect = emit
    return audio, updates


def test_fast_voice_success_contains_full_reply_before_voicing_update():
    manager = TaskManager()
    task = manager.create_task("dialogue", {"character": "Crazy"})
    audio, updates = _audio_with_task_updates(manager)
    generated = _reply()

    class LocalVoice:
        async def synthesize(self, *args, **kwargs):
            return "test-voice.wav"

    class DisconnectedGame:
        def is_connected(self):
            return False

    def resolve(service):
        if service is LocalVoiceService:
            return LocalVoice()
        if service is GameLinkService:
            return DisconnectedGame()
        raise AssertionError(f"Unexpected service: {service}")

    with patch("controllers.audio_controller.use", side_effect=resolve), \
         patch.object(AudioController, "_desktop_task", return_value=False):
        asyncio.run(audio._synthesize_and_deliver(
            "voice", "I cast a spell", task.uid, method="Local", task_result=generated,
        ))

    success = next(x for x in updates if x["status"] == TaskStatus.SUCCESS)
    assert success["result"]["response_protocol_version"] == 3
    assert success["result"]["segments"] == generated["segments"]
    assert success["result"]["voiceover_path"] == "test-voice.wav"
    assert manager.get_task(task.uid).status == TaskStatus.SUCCESS

    # An older queued VOICING notification must not overwrite terminal status.
    manager.update_task_status(task.uid, TaskStatus.VOICING, generated)
    assert manager.get_task(task.uid).status == TaskStatus.SUCCESS


def test_voice_failure_contains_full_reply_without_prior_voicing_update():
    manager = TaskManager()
    task = manager.create_task("dialogue", {"character": "Crazy"})
    audio, updates = _audio_with_task_updates(manager)
    generated = _reply()

    class BrokenLocalVoice:
        async def synthesize(self, *args, **kwargs):
            raise RuntimeError("voice unavailable")

    with patch("controllers.audio_controller.use", return_value=BrokenLocalVoice()):
        asyncio.run(audio._synthesize_and_deliver(
            "voice", "I cast a spell", task.uid, method="Local", task_result=generated,
        ))

    failed = next(x for x in updates if x["status"] == TaskStatus.FAILED_ON_VOICEOVER)
    assert failed["result"]["response_protocol_version"] == 3
    assert failed["result"]["response"] == "I cast a spell"
    assert failed["result"]["segments"] == generated["segments"]
    assert "error_details" in failed["result"]
