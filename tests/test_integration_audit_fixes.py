import json
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from characters.novel import TwoDMita
from characters.cartridge import CartridgeCharacter
from controllers.model_controller import ModelController
from controllers.desktop_watch_controller import DesktopWatchController
from domain.cartridge_catalog import CartridgeDefinition
from domain.timeline import JsonDocument, InvalidTimelineOperation
from managers.character_manager import CharacterManager, _CHARACTER_DEFINITIONS
from managers.session_state_participants import CatalogSnapshotParticipant, CharacterRuntimeSnapshot


def manager():
    value = object.__new__(CharacterManager)
    value._lock = threading.RLock()
    value._definitions = {d.character_id: d for d in _CHARACTER_DEFINITIONS}
    value.characters = {}
    value.current_character = None
    value.resources = MagicMock()
    return value


def runtime_state(value):
    return JsonDocument({"characters": {identity: {
        "app_vars": {}, "materialized": False, "working_state": {},
        "reminders": {"reminders": [], "next_number": 1, "timer_remaining": {}},
    } for identity in value.get_all_characters()}})


def test_catalog_snapshots_validate_before_and_after_registration_and_restart():
    value = manager()
    wrapped = CatalogSnapshotParticipant(CharacterRuntimeSnapshot(value, None), value)
    old = runtime_state(value)
    definition = CartridgeDefinition("audit", "Cartridge_audit", "Audit", "Prompt", 12, 12000)
    value.register_cartridges([definition])
    new = JsonDocument({**runtime_state(value).to_dict(), "_cartridges": value.capture_cartridge_definitions()})
    wrapped.validate(old)
    wrapped.validate(new)
    assert "Cartridge_audit" in value.get_all_characters()
    restarted = manager()
    CatalogSnapshotParticipant(CharacterRuntimeSnapshot(restarted, None), restarted).validate(new)
    value.restore_cartridge_definitions([])
    assert "Cartridge_audit" not in value.get_all_characters()
    value.restore_cartridge_definitions(value.validate_cartridge_definitions(new.to_dict()["_cartridges"]))
    wrapped.validate(new)
    broken = old.to_dict()
    broken["characters"].pop("Crazy")
    with pytest.raises(InvalidTimelineOperation):
        wrapped.validate(JsonDocument(broken))
    value.register_cartridges([definition])
    assert value.get_all_characters().count("Cartridge_audit") == 1


def test_catalog_apply_replaces_roster_before_dependent_apply_and_can_roll_back():
    value = manager()
    inner = SimpleNamespace(key="fake", version=1, paused=lambda: None)
    inner.validate = lambda state: (set(state.to_dict()["characters"]) == set(value.get_all_characters())) or (_ for _ in ()).throw(ValueError("roster"))
    applied = []
    inner.apply = lambda state, **kwargs: applied.append(tuple(value.get_all_characters()))
    inner.capture = lambda: JsonDocument({"characters": {i: {} for i in value.get_all_characters()}})
    wrapped = CatalogSnapshotParticipant(inner, value)
    before = wrapped.capture()
    value.register_cartridges([CartridgeDefinition("audit", "Cartridge_audit", "Audit", "Prompt", 12, 12000)])
    after = wrapped.capture()
    wrapped.apply(before, branch_id="a")
    wrapped.apply(after, branch_id="b")
    assert "Cartridge_audit" not in applied[0]
    assert "Cartridge_audit" in applied[1]
    bad = after.to_dict()
    bad["_cartridges"][0]["character_id"] = "Crazy"
    with pytest.raises(InvalidTimelineOperation):
        wrapped.validate(JsonDocument(bad))


@pytest.mark.parametrize("kind", [TwoDMita, CartridgeCharacter])
def test_shared_postprocessor_serializes_character_normalized_response(kind):
    model = object.__new__(ModelController)
    model.settings = {"ENABLE_WORKING_STATE": False}
    model.event_writer = SimpleNamespace(timeline=None)
    model.event_bus = MagicMock()
    model._store_last_usage = MagicMock()
    model._build_usage_snapshot = MagicMock(return_value=None)
    character = SimpleNamespace(process_structured_response=lambda response, **kwargs: kind.process_structured_response(None, response, **kwargs))
    answer = model._process_structured_output(
        visible_raw=json.dumps({"segments": [{"text": "Audit", "intents": [
            {"type": "novel.transform", "payload": {"scale": 99}},
            {"type": "inventory.collect", "payload": {"object": "key"}},
        ]}]}), think_text="", usage=None, response_model="audit", response_provider="audit",
        pricing_info=None, char=character, char_id="TwoD", char_name="TwoD", origin_message_id=None,
        capabilities={}, policy=SimpleNamespace(write_to_history=False), sender="Player", participants=[],
        user_input="audit", image_data=[], image_source="", req_id="audit", task_uid="audit", event_type="chat")
    serialized = json.dumps({key: value for key, value in answer.structured.items() if not key.startswith("_")})
    assert "inventory.collect" not in serialized
    assert "99" not in serialized
    if kind is TwoDMita:
        assert "1.5" in serialized


def watcher():
    value = object.__new__(DesktopWatchController)
    value.settings = {"ENABLE_IMAGE_ANALYSIS": True, "DESKTOP_WATCH_ENABLED": True, "DESKTOP_MODE_ACTIVE": True}
    value._lock = threading.RLock()
    value._desktop_state = {}
    value._capture = MagicMock()
    running = [False]
    value._capture.is_running.side_effect = lambda: running[0]
    value._capture.start_capture.side_effect = lambda **kwargs: running.__setitem__(0, True)
    value._capture.stop_capture.side_effect = lambda: running.__setitem__(0, False)
    value._capture.get_recent_frames.return_value = [b"frame"]
    return value


def test_capture_requires_request_and_permissions_and_clears_frames_on_off():
    value = watcher()
    assert not value.start()
    value.apply_desktop_state({"watching_screen": True})
    assert value.is_watching()
    assert value.desktop_frames() == [b"frame"]
    value.apply_desktop_state({"watching_screen": False})
    assert not value.is_watching()
    assert value.desktop_frames() == value.capture_desktop_now() == []
    value._capture.clear_history.assert_called()
    value.settings["ENABLE_IMAGE_ANALYSIS"] = False
    value.apply_desktop_state({"watching_screen": True})
    assert not value.is_watching()
    value.settings["ENABLE_IMAGE_ANALYSIS"] = True
    value.settings["DESKTOP_MODE_ACTIVE"] = False
    assert not value.start()


def test_disconnect_removes_only_disconnected_overlay_request():
    from game_connections.server import ChatServerNew
    server = object.__new__(ChatServerNew)
    server._clients_lock = threading.RLock()
    server.client_roles = {"one": server.DESKTOP_ROLE, "two": server.DESKTOP_ROLE}
    assert server.set_desktop_watch_request("one", True)
    assert server.set_desktop_watch_request("two", True)
    assert server.set_desktop_watch_request("one", False)
    assert not server.set_desktop_watch_request("two", False)
    assert not server.set_desktop_watch_request("unknown", True)


def test_catalog_actual_timeline_restore_failure_compensates_roster(tmp_path):
    import sqlite3
    from contextlib import nullcontext
    from infrastructure.timeline.sqlite import SQLiteTimelineRepository
    from infrastructure.timeline.restoration import SQLiteRestorationJournal
    from services.timeline_runtime import SessionTimelineRuntime
    from services.session_restoration import SessionRestoration, RestorationFailed
    value = manager()
    repository = SQLiteTimelineRepository(tmp_path / "timeline.db")
    runtime = SessionTimelineRuntime(repository, repository)
    inner = SimpleNamespace(key="characters", version=1, paused=nullcontext)
    inner.capture = lambda: JsonDocument({"characters": {i: {} for i in value.get_all_characters()}})
    def validate(state):
        if set(state.to_dict()["characters"]) != set(value.get_all_characters()):
            raise InvalidTimelineOperation("Roster mismatch")
    inner.validate = validate
    inner.apply = lambda state, **kwargs: validate(state)
    fault = SimpleNamespace(key="fault", version=1, paused=nullcontext, value="old", fail=False)
    fault.capture = lambda: JsonDocument({"value": fault.value})
    fault.validate = lambda state: None
    def apply(state, **kwargs):
        fault.value = state.to_dict()["value"]
        if fault.fail and fault.value == "old":
            raise RuntimeError("Injected participant failure")
    fault.apply = apply
    coordinator = SessionRestoration(runtime, (CatalogSnapshotParticipant(inner, value), fault),
        SQLiteRestorationJournal(lambda: sqlite3.connect(tmp_path / "timeline.db")))
    before = runtime.checkpoint()
    value.register_cartridges([CartridgeDefinition("audit", "Cartridge_audit", "Audit", "Prompt", 12, 12000)])
    fault.value = "new"
    after = runtime.checkpoint()
    source_branch = runtime.selection.branch_id
    fault.fail = True
    with pytest.raises(RestorationFailed) as error:
        runtime.restore(before.event_id)
    assert not error.value.recovery_required
    assert "Cartridge_audit" in value.get_all_characters()
    assert fault.value == "new"
    fault.fail = False
    runtime.restore(before.event_id)
    assert "Cartridge_audit" not in value.get_all_characters()
    runtime.restore(after.event_id, checkpoint_branch_id=source_branch)
    assert "Cartridge_audit" in value.get_all_characters()


def test_snapshot_owners_must_agree_on_catalog_before_mutation():
    from services.session_restoration import SessionRestoration
    coordinator = object.__new__(SessionRestoration)
    def owner(key, catalog):
        return SimpleNamespace(key=key, version=1, validate=lambda state: None,
            validation_dependencies=lambda state: {"character_catalog": catalog})
    coordinator.participants = (owner("one", []), owner("two", ["different"]))
    snapshot = JsonDocument({"snapshot_version": 1, "presence": [], "participants": {
        key: {"version": 1, "state": {}} for key in ("one", "two")}})
    with pytest.raises(InvalidTimelineOperation, match="disagree"):
        coordinator._validate(snapshot)


def test_retired_cartridge_records_are_removed_by_semantic_store(tmp_path):
    import sqlite3
    from infrastructure.timeline.character_state import SQLiteCharacterState
    path = tmp_path / "characters.db"
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE variables (character_id TEXT, key TEXT, value TEXT);
            CREATE TABLE memories (id INTEGER PRIMARY KEY, character_id TEXT, eternal_id INTEGER, content TEXT);
            INSERT INTO variables VALUES ('Cartridge_audit', 'future', '99');
            INSERT INTO memories VALUES (1, 'Cartridge_audit', 1, 'future memory');
        """)
    store = SQLiteCharacterState(lambda: sqlite3.connect(path), lambda: ["Crazy"],
        retired_character_ids=lambda: ["Cartridge_audit"])
    state = store.capture()
    store.apply(state)
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT * FROM variables WHERE character_id='Cartridge_audit'").fetchall() == []
        assert connection.execute("SELECT * FROM memories WHERE character_id='Cartridge_audit'").fetchall() == []


def test_capture_stop_interrupts_long_interval_without_waiting_for_next_frame():
    from handlers.screen_handler import ScreenCapture
    capture = ScreenCapture()
    capture._running = True
    capture._frame_history = [b"old frame"]
    capture._thread = threading.Thread(target=lambda: capture._stop_event.wait(60), daemon=True)
    capture._thread.start()
    capture.stop_capture()
    capture.clear_history()
    assert not capture._thread.is_alive()
    assert capture.get_latest_frame() is None


def test_last_desktop_disconnect_stops_request_and_deactivates_mode():
    from game_connections.server import ChatServerNew
    from services.contracts import DesktopWatchService
    server = object.__new__(ChatServerNew)
    server._clients_lock = threading.RLock()
    server.client_roles = {"one": server.DESKTOP_ROLE, "two": server.DESKTOP_ROLE}
    for name in ("active_connections", "client_tasks", "last_participants", "_last_sent_dialogue_text"):
        setattr(server, name, {})
    server._deactivate_desktop_mode = MagicMock()
    server.set_desktop_watch_request("one", True)
    server.set_desktop_watch_request("two", True)
    watch = MagicMock()
    registry = MagicMock()
    registry.get_optional.return_value = watch
    with patch("core.services.services", return_value=registry):
        server._forget_client_state("one")
        watch.apply_desktop_state.assert_called_with({"watching_screen": True})
        server._deactivate_desktop_mode.assert_not_called()
        server._forget_client_state("two")
        watch.apply_desktop_state.assert_called_with({"watching_screen": False})
        server._deactivate_desktop_mode.assert_called_once()
