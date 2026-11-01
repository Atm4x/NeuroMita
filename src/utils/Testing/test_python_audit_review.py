from __future__ import annotations

import json
import sqlite3
import sys
from dataclasses import asdict
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.mark.parametrize("metadata", [
    '{"private":"secret-content", broken',
    '["secret-content"]',
    '{"multimodal_parts":["secret-content"]}',
    '{"multimodal_parts":{"private":"secret-content"}}',
    '{"multimodal_parts":[{"image_url":["secret-content"]}]}',
])
def test_image_scan_reports_exact_row_without_logging_message_content(tmp_path, monkeypatch, caplog, metadata):
    from utils.image_cleanup import delete_orphaned_images

    monkeypatch.setenv("NEUROMITA_HISTORIES_DIR", str(tmp_path))
    image = tmp_path / "A" / "Images" / "used.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"keep")
    with sqlite3.connect(tmp_path / "world.db") as conn:
        conn.execute("CREATE TABLE history(id INTEGER PRIMARY KEY, meta_data TEXT)")
        conn.execute("INSERT INTO history VALUES (7, ?)", (json.dumps({"multimodal_parts": [{"image_url": {"url": str(image)}}]}),))
        conn.execute("INSERT INTO history VALUES (42, ?)", (metadata,))
    with pytest.raises(RuntimeError, match=r"history.id=42") as caught:
        delete_orphaned_images()
    assert "history.id=42" in caplog.text
    assert "secret-content" not in caplog.text + str(caught.value)
    assert image.read_bytes() == b"keep"


@pytest.mark.parametrize("component_kind", ["model", "aggregate"])
@pytest.mark.parametrize("serialized_plan", [False, True])
def test_unsupported_rag_uninstall_reaches_ai_hub_as_explicit_failure(tmp_path, component_kind, serialized_plan):
    from controllers.gui.ai_hub_view_model import AIHubViewModel
    from controllers.install_controller import InstallController
    from core.events import Event, Events
    from core.install_types import InstallCallbacks
    from core.runtime_environments import RuntimeEnvironmentManager
    from managers.rag.install_spec import RagInstallableComponent, RagModelInstallableComponent

    component = (RagModelInstallableComponent("embeddings", "test/model")
                 if component_kind == "model" else RagInstallableComponent("embeddings"))
    plan = component.build_uninstall_plan()
    controller = InstallController.__new__(InstallController)
    controller.event_bus = Mock()
    controller.environment_manager = RuntimeEnvironmentManager(tmp_path / "Lib")
    controller.environment_manager.begin = Mock(side_effect=AssertionError("Unsupported operation must not mutate environments"))
    controller._make_pip_installer = Mock(return_value=SimpleNamespace(script_path=sys.executable, cancel=Mock()))
    controller._release_pip_installer = Mock()
    logs = Mock()
    callbacks = InstallCallbacks(progress=Mock(), status=Mock(), log=logs)
    result = controller.run_task(
        task_id="rag-uninstall", runner=lambda **_: asdict(plan) if serialized_plan else plan,
        meta={"category": "rag", "kind": "rag", "item_id": component.item_id,
              "component_id": component.id, "op": "uninstall"},
        callbacks=callbacks,
    )
    assert result is False
    events = controller.event_bus.emit.call_args_list
    failures = [call.args[1] for call in events if call.args[0] == Events.Install.TASK_FAILED]
    assert len(failures) == 1
    assert failures[0]["error_code"] == "unsupported_operation"
    assert failures[0]["error"] == plan.unsupported_reason
    assert not any(call.args[0] == Events.Install.TASK_FINISHED for call in events)
    controller.environment_manager.begin.assert_not_called()
    logs.assert_called_with(plan.unsupported_reason)

    view = SimpleNamespace(
        _is_installable_task=AIHubViewModel._is_installable_task,
        _event_data=AIHubViewModel._event_data,
        _event_component_id=AIHubViewModel._event_component_id,
        _install_ui_generation=0, _post_ui=lambda callback: callback(),
        update_state=Mock(), _invalidate_component=Mock(), refresh=Mock(),
    )
    AIHubViewModel._on_install_failed(view, Event(Events.Install.TASK_FAILED, failures[0]))
    assert view.update_state.call_args.kwargs["error"] == plan.unsupported_reason
    assert view.update_state.call_args.kwargs["install_bar_visible"] is False
    view._invalidate_component.assert_called_once_with(component.id)
