from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from managers.database_manager import DatabaseManager
from managers.memory_manager import MemoryManager
from managers.settings_manager import SettingsManager


@pytest.fixture
def database(tmp_path, monkeypatch):
    monkeypatch.setenv("NEUROMITA_HISTORIES_DIR", str(tmp_path))
    monkeypatch.setattr(DatabaseManager, "_instance", None)
    monkeypatch.setattr(DatabaseManager, "_path_override", str(tmp_path / "world.db"))
    db = DatabaseManager()
    yield db
    DatabaseManager._instance = None


def memory(character):
    manager = MemoryManager(character)
    manager.rag = None
    manager._dedup_enabled = lambda: False
    manager._get_memory_capacity = lambda: 100
    return manager


def test_weighted_ttl_does_not_forget_another_character(database, monkeypatch):
    first, second = memory("A"), memory("B")
    for manager in (first, second):
        manager.add_memory("old", date="01.01.2020 10:00:00", priority="Low")
    settings = {"MEMORY_TTL_ENABLED": True, "MEMORY_TTL_MODE": "access_weighted", "MEMORY_TTL_LOW_DAYS": 1}
    monkeypatch.setattr(SettingsManager, "get", lambda key, default=None: settings.get(key, default))
    assert first.apply_ttl_cleanup() == 1
    with database.connection() as conn:
        rows = conn.execute("SELECT character_id, is_forgotten FROM memories ORDER BY character_id").fetchall()
    assert rows == [("A", 1), ("B", 0)]


def test_existing_memory_returns_public_id_and_restores_only_its_owner(database):
    memory("A").add_memory("other")
    manager = memory("B")
    number = manager.add_memory("existing")
    manager.delete_memory(number)
    assert manager.add_memory("existing", skip_if_exists=True) == number
    with database.connection() as conn:
        assert conn.execute("SELECT character_id, is_deleted FROM memories ORDER BY id").fetchall() == [("A", 0), ("B", 0)]


def test_purge_cleans_only_deleted_public_memory_ids(database):
    memory("A").add_memory("other")
    manager = memory("B")
    deleted = manager.add_memory("deleted")
    active = manager.add_memory("keep")
    manager.delete_memory(deleted)
    with database.connection() as conn:
        for character, number in (("A", 1), ("B", deleted), ("B", active)):
            conn.execute("INSERT INTO embeddings(source_table, source_id, character_id, model_name, dimensions, embedding) VALUES ('memories', ?, ?, 'model', 1, ?)", (number, character, b"vector"))
            conn.execute("INSERT INTO sentence_embeddings(source_table, source_id, character_id, model_name, sentence_idx, embedding) VALUES ('memories', ?, ?, 'model', 0, ?)", (number, character, b"sentence"))
        conn.commit()
    assert manager.purge_deleted(backup=False)["purged_memories"] == 1
    with database.connection() as conn:
        for table in ("embeddings", "sentence_embeddings"):
            assert conn.execute(f"SELECT character_id, source_id FROM {table} ORDER BY character_id").fetchall() == [("A", 1), ("B", active)]


def test_purge_rolls_back_if_embedding_cleanup_fails(database):
    manager = memory("B")
    number = manager.add_memory("deleted")
    manager.delete_memory(number)
    with database.connection() as conn:
        conn.execute("INSERT INTO embeddings(source_table, source_id, character_id, model_name, dimensions, embedding) VALUES ('memories', ?, 'B', 'model', 1, ?)", (number, b"vector"))
        conn.execute("CREATE TRIGGER reject_purge BEFORE DELETE ON sentence_embeddings BEGIN SELECT RAISE(ABORT, 'blocked'); END")
        conn.execute("INSERT INTO sentence_embeddings(source_table, source_id, character_id, model_name, sentence_idx, embedding) VALUES ('memories', ?, 'B', 'model', 0, ?)", (number, b"sentence"))
        conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        manager.purge_deleted(backup=False)
    with database.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM memories WHERE character_id='B'").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM embeddings WHERE character_id='B'").fetchone()[0] == 1


def test_timestamp_repair_runs_after_broken_v1_was_marked(database):
    with database.connection() as conn:
        for value in ("30.10.2026 18:32:00", "30.10.2026 18:32", "18:32", "2026-10-30T18:32:00", "2026-10-30 18:32:00"):
            conn.execute("INSERT INTO history(character_id, role, content, timestamp) VALUES ('A','user','test',?)", (value,))
        database._mark_migration(conn.cursor(), "history_timestamp_iso_v1")
        database._mark_migration(conn.cursor(), "history_timestamp_iso_v2")
        conn.execute("DELETE FROM schema_migrations WHERE name=?", (database._MIGRATION_TIMESTAMP_NORMALIZATION,))
        conn.commit()
    database._upgrade_schema()
    with database.connection() as conn:
        dates = [row[0] for row in conn.execute("SELECT timestamp FROM history ORDER BY id")]
    assert dates[:2] == ["2026-10-30 18:32:00"] * 2
    assert dates[2] == "18:32"
    assert dates[3:] == ["2026-10-30 18:32:00"] * 2
    database._upgrade_schema()
    with database.connection() as conn:
        assert dates == [row[0] for row in conn.execute("SELECT timestamp FROM history ORDER BY id")]


@pytest.mark.parametrize("operation", ["add", "delete", "clear"])
def test_failed_reminder_commit_preserves_memory_and_disk(tmp_path, monkeypatch, operation):
    from managers.reminder_manager import ReminderManager

    monkeypatch.setenv("NEUROMITA_HISTORIES_DIR", str(tmp_path))
    manager = ReminderManager("A")
    manager._notify_changed = Mock()
    number = manager.add_reminder("keep", "2099-01-01T12:00:00")
    before = manager.load_reminders()
    next_number = manager.last_reminder_number
    manager._notify_changed.reset_mock()
    with patch("managers.reminder_manager.os.replace", side_effect=OSError("disk full")):
        with pytest.raises(OSError, match="disk full"):
            if operation == "add":
                manager.add_reminder("new", "2099-01-01T13:00:00")
            elif operation == "delete":
                manager.delete_reminder(number)
            else:
                manager.clear_reminders()
    assert manager.load_reminders() == before
    assert manager.last_reminder_number == next_number
    assert ReminderManager("A").load_reminders() == before
    manager._notify_changed.assert_not_called()
    assert not list(tmp_path.rglob("*.tmp"))


@pytest.mark.parametrize("failure", ["missing", "invalid_db", "invalid_metadata"])
def test_image_cleanup_never_deletes_when_references_are_unreadable(tmp_path, monkeypatch, failure):
    from utils.image_cleanup import delete_orphaned_images

    monkeypatch.setenv("NEUROMITA_HISTORIES_DIR", str(tmp_path))
    image = tmp_path / "A" / "Images" / "used.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"image")
    db_path = tmp_path / "world.db"
    if failure == "invalid_db":
        db_path.write_bytes(b"not a database")
    elif failure == "invalid_metadata":
        with sqlite3.connect(db_path) as conn:
            conn.execute("CREATE TABLE history(id INTEGER PRIMARY KEY, meta_data TEXT)")
            conn.execute("INSERT INTO history(meta_data) VALUES ('broken JSON')")
    with pytest.raises(RuntimeError, match="references"):
        delete_orphaned_images()
    assert image.read_bytes() == b"image"


def test_image_cleanup_keeps_referenced_files_and_removes_real_orphans(tmp_path, monkeypatch):
    from utils.image_cleanup import delete_orphaned_images

    monkeypatch.setenv("NEUROMITA_HISTORIES_DIR", str(tmp_path))
    folder = tmp_path / "A" / "Images"
    folder.mkdir(parents=True)
    used, orphan = folder / "used.png", folder / "orphan.png"
    used.write_bytes(b"keep")
    orphan.write_bytes(b"remove")
    with sqlite3.connect(tmp_path / "world.db") as conn:
        conn.execute("CREATE TABLE history(id INTEGER PRIMARY KEY, meta_data TEXT)")
        conn.execute("INSERT INTO history(meta_data) VALUES (?)", (json.dumps({"multimodal_parts": [{"image_url": {"url": str(used)}}]}),))
    assert delete_orphaned_images() == (1, 6)
    assert used.exists() and not orphan.exists()


def test_manual_screenshot_stages_complete_frames():
    from controllers.gui.chat_panel_view_model import ChatPanelViewModel

    frame = b"\x89PNG\x00test"
    vm = SimpleNamespace(_stage_images=Mock(), emit_effect=Mock())
    vm.run_exclusive = lambda _key, worker, applied: applied(worker())
    with patch("controllers.gui.chat_panel_view_model.services", return_value=SimpleNamespace(get_optional=lambda _: SimpleNamespace(capture_screen=lambda _: [frame]))):
        ChatPanelViewModel._capture_screen(vm)
    vm._stage_images.assert_called_once_with((frame,))


def test_snapshot_failure_reports_error_without_successful_history_reload(tmp_path):
    from controllers.chat_controller import ChatController
    from core.events import Event, Events
    from managers.history_manager import HistoryBatchWriteError

    source = tmp_path / "snapshot.json"
    source.write_text('{"messages": []}', encoding="utf-8")
    character = SimpleNamespace(history_manager=SimpleNamespace(save_history=Mock(side_effect=HistoryBatchWriteError("write failed"))))
    controller = SimpleNamespace(_get_character_ref=lambda _: character, event_bus=Mock())
    ChatController._on_load_snapshot(controller, Event(Events.Chat.LOAD_SNAPSHOT, {"character_id": "A", "file_path": str(source)}))
    calls = controller.event_bus.emit.call_args_list
    assert [call.args[0] for call in calls] == [Events.GUI.SHOW_ERROR_MESSAGE]


def test_preset_export_removes_secrets_after_state_overlay(tmp_path):
    from controllers.api_presets_controller import ApiPresetsController
    from core.events import Event, Events

    data = {"id": 5, "name": "share", "key": "private", "reserve_keys": ["reserve"], "url": "https://example.invalid"}
    state = {"key": "override", "reserve_keys": ["override-reserve"]}
    controller = SimpleNamespace(_build_effective_preset_dict=lambda _: data, preset_states={5: state})
    destination = tmp_path / "export.json"
    assert ApiPresetsController._on_export_preset(controller, Event(Events.ApiPresets.EXPORT_PRESET, {"id": 5, "path": str(destination)}))
    exported = json.loads(destination.read_text(encoding="utf-8"))
    assert "key" not in exported and "reserve_keys" not in exported
    assert exported["name"] == "share" and data["key"] == "private" and state["key"] == "override"


@pytest.mark.parametrize("ledger_only", [False, True])
def test_gui_graph_clear_removes_processed_ledger(database, monkeypatch, ledger_only):
    import controllers.gui.rag_memory_controller as gui
    from managers.rag.graph.graph_store import GraphStore

    store = GraphStore(database, "A")
    store.mark_messages_processed([42])
    if not ledger_only:
        store.upsert_entity("test", "person")
    dialog = Mock()
    dialog.StandardButton.Yes = 1
    dialog.StandardButton.No = 2
    dialog.question.return_value = 1
    monkeypatch.setattr(gui, "QMessageBox", dialog)
    gui._delete_all_graph_data(None)
    with database.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM graph_processed_messages").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM graph_entities").fetchone()[0] == 0
    dialog.question.assert_called_once()


def test_gigaam_readiness_requires_nonempty_model_artifacts(tmp_path):
    import handlers.asr_models.gigaam_onnx_recognizer as module

    recognizer = module.GigaAMOnnxRecognizer(Mock(), Mock())
    recognizer.gigaam_model_path = str(tmp_path)
    with patch.object(module, "build_runtime_ctx", return_value={}), patch.object(module, "check_requirements", return_value={"ok": True}):
        assert not recognizer.is_installed()
        for item in recognizer.install_manifest():
            Path(item["dest"]).touch()
        assert not recognizer.is_installed()
        for item in recognizer.install_manifest():
            Path(item["dest"]).write_bytes(b"weights")
        assert recognizer.is_installed()


@pytest.mark.parametrize("component", ["model", "aggregate"])
def test_unsupported_rag_removal_does_not_report_success(component):
    from managers.rag.install_spec import RagInstallableComponent, RagModelInstallableComponent

    target = RagModelInstallableComponent("embeddings", "test/model") if component == "model" else RagInstallableComponent("embeddings")
    plan = target.build_uninstall_plan()
    assert plan.unsupported_reason
    assert plan.actions == [] and not plan.environment_managed


@pytest.mark.parametrize("error", [TimeoutError(), RuntimeError("")])
def test_asr_start_failure_preserves_error_and_device_identity(error):
    import handlers.ai_engine.services.asr_service as module
    from domain.audio_input import MicrophoneSelection

    service = module.ASRService(emit_event=Mock())
    service._recognizer, service._vad_model = object(), object()
    capture = SimpleNamespace(run=AsyncMock(side_effect=error))
    with patch.object(module, "AudioCaptureService", return_value=capture):
        with pytest.raises(RuntimeError, match="Test microphone") as caught:
            asyncio.run(service._start_live_internal(engine_id="google", selection=MicrophoneSelection(index=7, name="Test microphone"), engine_settings={}, sample_rate=16000, chunk_size=512, vad_threshold=0.5, silence_timeout=1.0, pre_buffer_duration=0.2, max_speech_duration=10.0, reuse_loaded_models=True))
    assert isinstance(caught.value.__cause__, type(error))
    assert not service._active and service._task is None


@pytest.mark.parametrize("artifact", [None, "missing", "empty", "valid"])
def test_telegram_voice_success_requires_a_real_artifact(tmp_path, artifact):
    import controllers.audio_controller as module
    from core.events import Events
    from managers.task_manager import TaskStatus

    path = None if artifact is None else tmp_path / "voice.wav"
    if artifact in ("empty", "valid"):
        path.write_bytes(b"voice" if artifact == "valid" else b"")
    provider = SimpleNamespace(send_voice=AsyncMock(return_value=str(path) if path else None))
    controller = SimpleNamespace(event_bus=Mock(), _emit_show_voicing=Mock(), _update_task_failed_voiceover=Mock(), waiting_answer=True)
    with patch.object(module, "use", return_value=provider):
        asyncio.run(module.AudioController.run_send_and_receive(controller, "voice", "original", "speaker", task_uid="task"))
    statuses = [call.args[1]["status"] for call in controller.event_bus.emit.call_args_list if call.args[0] == Events.Task.UPDATE_TASK_STATUS]
    if artifact == "valid":
        assert statuses == [TaskStatus.SUCCESS]
        controller._update_task_failed_voiceover.assert_not_called()
    else:
        assert statuses == []
        controller._update_task_failed_voiceover.assert_called_once()
        controller._emit_show_voicing.assert_not_called()
    assert controller.waiting_answer is False


@pytest.mark.parametrize("conversion", ["failed", "missing", "empty", "valid"])
def test_telegram_conversion_preserves_source_until_wav_is_ready(tmp_path, monkeypatch, conversion):
    import handlers.telegram_handler as module

    monkeypatch.chdir(tmp_path)
    source = tmp_path / "source.mp3"
    source.write_bytes(b"original")
    media_type = type("Media", (), {})
    media = media_type()
    media.document = SimpleNamespace(mime_type="audio/mpeg", attributes=[])
    message = SimpleNamespace(id=2, out=False, media=media)

    async def messages(*_args, **_kwargs):
        yield message

    async def convert(_source, destination):
        if conversion in ("empty", "valid"):
            Path(destination).write_bytes(b"wav" if conversion == "valid" else b"")
        return conversion != "failed"

    handler = module.TelegramBotHandler.__new__(module.TelegramBotHandler)
    handler.client = SimpleNamespace(iter_messages=messages, download_media=AsyncMock(return_value=str(source)))
    handler.tg_bot, handler.silero_time_limit = "test", 1
    handler._get_last_chat_message_id = AsyncMock(return_value=1)
    handler._safe_send_message = AsyncMock()
    handler._last_speaker_command_norm = handler._norm_cmd("speaker")
    handler.event_bus = Mock()
    monkeypatch.setattr(module, "MessageMediaDocument", media_type)
    monkeypatch.setattr(module, "use", lambda _: SimpleNamespace(is_connected=lambda: True))
    monkeypatch.setattr(module.AudioConverter, "convert_to_wav", convert)
    with patch.object(module.asyncio, "sleep", new=AsyncMock()):
        if conversion == "valid":
            result = asyncio.run(handler.send_and_receive("text", "speaker", "id"))
            assert result == str(tmp_path / "source.wav") and not source.exists()
        else:
            with pytest.raises(RuntimeError, match="WAV"):
                asyncio.run(handler.send_and_receive("text", "speaker", "id"))
            assert source.read_bytes() == b"original"
            handler.event_bus.emit.assert_not_called()
