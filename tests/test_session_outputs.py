from __future__ import annotations

import asyncio
import os
from contextlib import nullcontext
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.cancellation import CancellationToken
from core.events import Events
from core.services import services
from core.state_barrier import StateBarrier, StateLease, StateUnavailable, bind_state_job
from domain.timeline import JsonDocument
from infrastructure.timeline.restoration import SQLiteRestorationJournal
from infrastructure.timeline.sqlite import SQLiteTimelineRepository
from managers.task_manager import TaskManager, TaskStatus
from services.session_restoration import SessionRestoration
from services.timeline_runtime import SessionTimelineRuntime


class SessionOutputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        repository = SQLiteTimelineRepository(self.path / "world.db")
        self.runtime = SessionTimelineRuntime(repository, repository)
        self.previous = {key: services().get_optional(key) for key in (StateBarrier, SessionTimelineRuntime)}
        services().register(StateBarrier, self.runtime.state, replace=True)
        services().register(SessionTimelineRuntime, self.runtime, replace=True)
        self.addCleanup(self._restore_services)
        participant = SimpleNamespace(key="world", version=1, paused=nullcontext, capture=lambda: JsonDocument(),
            validate=lambda _state: None, apply=lambda _state, **_context: None)
        SessionRestoration(self.runtime, (participant,), SQLiteRestorationJournal(lambda: sqlite3.connect(self.path / "world.db")))
        self.checkpoint = self.runtime.checkpoint()

    def _restore_services(self):
        for key, value in self.previous.items():
            services().unregister(key)
            if value is not None:
                services().register(key, value)

    def test_task_snapshots_expire_without_serializing_old_results_or_revisions_repeatedly(self):
        manager = TaskManager()
        task = manager.create_task("chat", {"client_id": "client"})
        completed = manager.update_task_status(task.uid, TaskStatus.SUCCESS, result={"response": "future", "voiceover_path": "old.wav"})
        self.runtime.restore(self.checkpoint.event_id)
        current = manager.get_task(task.uid)
        self.assertEqual(current.status, TaskStatus.CANCELLED)
        self.assertIsNone(current.result)
        self.assertEqual(completed.to_dict()["status"], "CANCELLED")
        self.assertIsNone(completed.to_dict()["result"])
        self.assertEqual(completed.snapshot().snapshot().revision, completed.revision + 1)
        self.assertEqual(manager.update_task_status(task.uid, TaskStatus.SUCCESS, {"response": "late"}).status, TaskStatus.CANCELLED)

    def test_delayed_server_delivery_uses_cancelled_status_in_both_envelopes(self):
        from game_connections.server import ChatServerNew

        manager = TaskManager()
        created = manager.create_task("chat", {})
        task = manager.update_task_status(created.uid, TaskStatus.SUCCESS, result={"response": "future"})
        self.runtime.restore(self.checkpoint.event_id)
        server = SimpleNamespace(_writer_for=lambda _client: object(), send_json=AsyncMock(return_value=True))
        asyncio.run(ChatServerNew.send_task_update(server, "client", task))
        envelope = server.send_json.call_args.args[1]
        self.assertEqual(envelope["status"], "CANCELLED")
        self.assertEqual(envelope["body"]["status"], "CANCELLED")
        self.assertIsNone(envelope["body"]["result"])

    def test_task_polling_does_not_reattach_expired_audio_to_a_cancelled_response(self):
        from game_connections.handlers.actions.get_task_status import GetTaskStatusAction

        manager = TaskManager()
        created = manager.create_task("chat", {})
        task = manager.update_task_status(created.uid, TaskStatus.SUCCESS, result={"voiceover_path": "old.wav"})
        self.runtime.restore(self.checkpoint.event_id)
        context = SimpleNamespace(server=SimpleNamespace(send_json=AsyncMock()), writer=object())
        with patch("game_connections.handlers.actions.get_task_status.use", return_value=SimpleNamespace(get_task=lambda _uid: task)):
            asyncio.run(GetTaskStatusAction().handle({"task_uid": task.uid}, context))
        response = context.server.send_json.call_args.args[1]
        self.assertEqual(response["status"], "CANCELLED")
        self.assertIsNone(response["result"])

    @staticmethod
    def audio_controller():
        from controllers.audio_controller import AudioController

        controller = object.__new__(AudioController)
        controller.settings = {"VOICEOVER_LOCAL_CHAT": True}
        controller.event_bus = Mock()
        controller._emit_show_voicing = Mock()
        controller._set_mita_speaking = Mock()
        controller._update_task_failed_voiceover = Mock()
        controller.waiting_answer = True
        controller._waiting_lease = StateLease.capture()
        return controller

    def test_tts_completing_after_restore_never_starts_playback_or_delivers_an_old_result(self):
        controller = self.audio_controller()
        path = self.path / "voice.wav"
        path.write_bytes(b"generated audio")

        async def synthesize(*_args, **_kwargs):
            self.runtime.restore(self.checkpoint.event_id)
            return str(path)

        with patch("controllers.audio_controller.use", return_value=SimpleNamespace(synthesize=synthesize)), patch(
            "controllers.audio_controller.AudioHandler.handle_voice_file", new_callable=AsyncMock) as play:
            asyncio.run(controller._synthesize_and_deliver("old", "old", "task", method="API"))
        play.assert_not_awaited()
        controller._emit_show_voicing.assert_not_called()
        controller._update_task_failed_voiceover.assert_not_called()
        self.assertFalse(controller.is_waiting_answer())
        self.assertFalse(path.exists())
        self.assertFalse(any(call.args[0] == Events.Task.UPDATE_TASK_STATUS for call in controller.event_bus.emit.call_args_list))

    def test_running_voice_scope_registers_its_cancellation_until_synthesis_finishes(self):
        controller = self.audio_controller()
        cancellation = CancellationToken()
        cancellation.add_cancel_callback(lambda: controller._cancel_voice_scope(cancellation))
        controller._active_voice_token = cancellation
        path = self.path / "voice.wav"
        path.write_bytes(b"generated audio")

        async def exercise():
            started, release = asyncio.Event(), asyncio.Event()

            async def synthesize(*_args, **_kwargs):
                started.set()
                await release.wait()
                return str(path)

            with patch("controllers.audio_controller.use", return_value=SimpleNamespace(synthesize=synthesize)), patch(
                "controllers.audio_controller.AudioHandler.handle_voice_file", new_callable=AsyncMock) as play:
                operation = controller._synthesize_and_deliver("old", "old", "task", method="API",
                    state_lease=controller._waiting_lease, cancellation=cancellation)
                running = asyncio.create_task(controller._run_voice_scope(operation, "A", cancellation))
                await started.wait()
                self.runtime.restore(self.checkpoint.event_id)
                self.assertTrue(cancellation.cancelled)
                release.set()
                await running
                play.assert_not_awaited()

        asyncio.run(exercise())
        self.assertFalse(controller.waiting_answer)
        self.assertFalse(path.exists())

    def test_local_playback_stops_when_its_world_is_invalidated(self):
        from handlers.audio_handler import AudioHandler

        mixer, clock = Mock(), Mock()
        mixer.music.get_busy.side_effect = [True, True, False]
        invalidated = False

        def tick(_rate):
            nonlocal invalidated
            if not invalidated:
                invalidated = True
                with self.runtime.state.exclusive(invalidate=True):
                    pass

        clock.tick.side_effect = tick
        with patch("handlers.audio_handler.pygame.mixer", mixer), patch("handlers.audio_handler.pygame.time.Clock", return_value=clock):
            asyncio.run(AudioHandler.play_audio_with_pygame("not-read-by-mock.wav"))
        self.assertEqual(mixer.music.get_busy.call_count, 2)
        mixer.music.stop.assert_called_once()
        mixer.quit.assert_called_once()

    def test_long_lived_input_service_starts_new_requests_in_the_current_world(self):
        from game_connections.server import ChatServerNew

        manager = TaskManager()
        created = []
        server = object.__new__(ChatServerNew)
        server._state_owner = self.runtime.state

        async def handle(_request, _client):
            created.append(manager.create_task("chat", {}))

        server._process_request_in_world = handle
        service_tick = bind_state_job(lambda: asyncio.run(server.process_request({}, "client")))
        self.runtime.restore(self.checkpoint.event_id)
        service_tick()
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].status, TaskStatus.PENDING)
        services().register(StateBarrier, StateBarrier(), replace=True)
        with self.assertRaises(StateUnavailable):
            service_tick()

    def test_retry_outbox_cannot_deliver_results_from_another_branch(self):
        from managers.unity_retry_store import UnityRetryStore

        with patch.dict(os.environ, {"NEUROMITA_HISTORIES_DIR": str(self.path)}), patch.object(UnityRetryStore, "_delivered_in_process", set()):
            record = {"message_id": "input", "status": "generated_pending_delivery", "result": {"response": "future"}}
            self.assertTrue(UnityRetryStore.add("A", record))
            with self.runtime.state.exclusive():
                self.runtime.activate(self.runtime.selection.branch_id)
            self.assertIsNotNone(UnityRetryStore.claim("A", "input"))
            UnityRetryStore.update("A", "input", status="generated_pending_delivery")
            self.runtime.restore(self.checkpoint.event_id)
            self.assertIsNone(UnityRetryStore.claim("A", "input"))
            old = UnityRetryStore.get("A", "input")
            self.assertEqual(old["status"], "unretryable")
            self.assertNotIn("result", old)
            self.assertTrue(UnityRetryStore.add("A", {"message_id": "input", "status": "needs_generation"}))
            self.assertIsNotNone(UnityRetryStore.claim("A", "input"))


if __name__ == "__main__":
    unittest.main()
