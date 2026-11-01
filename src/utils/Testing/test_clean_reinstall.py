from pathlib import Path
from unittest.mock import Mock
import sys

import pytest

from controllers.install_controller import InstallController
from core.backends import BackendKind
from core.install_types import InstallAction, InstallPlan
from core.runtime_environments import RuntimeEnvironmentManager
from handlers.voice_models.f5_tts_model import F5TTSInstallSpec
from handlers.voice_models.fish_speech_model import FishSpeechInstallSpec
from handlers.voice_models.omnivoice_model import OmniVoiceInstallSpec
from managers.rag import install_spec


@pytest.mark.parametrize("spec,model", [
    (F5TTSInstallSpec, "F5"),
    (FishSpeechInstallSpec, "medium"),
    (OmniVoiceInstallSpec, "omnivoice"),
])
@pytest.mark.parametrize("clean_ctx", [{"clean": True}, {"meta": {"clean": True}}])
def test_installed_voice_builds_complete_clean_plan(monkeypatch, spec, model, clean_ctx):
    monkeypatch.setattr(spec, "is_installed", lambda *args: True)
    monkeypatch.setattr(spec, "required_backend", lambda *args: BackendKind.NONE)
    assert spec.build_install_plan(model, {}).already_installed
    plan = spec.build_install_plan(model, clean_ctx)
    assert not plan.already_installed
    assert any(action.type == "pip" and action.packages for action in plan.actions)
    assert plan.actions[-1].type == "call"


def test_installed_rag_builds_complete_clean_plan(monkeypatch):
    status = {"required": True, "ok": True, "needs_local_runtime": True}
    monkeypatch.setattr(install_spec, "get_install_status", lambda *args, **kwargs: status)
    monkeypatch.setattr(install_spec, "model_install_status", lambda *args, **kwargs: status)
    ctx = {"clean": True, "gpu_vendor": "CPU", "rag_backend": "torch"}
    for plan in (
        install_spec.build_install_plan("embeddings", ctx=ctx),
        install_spec.build_model_install_plan("embeddings", "owner/model", ctx=ctx),
    ):
        assert not plan.already_installed
        assert any(action.type == "pip" and action.packages for action in plan.actions)


def _write_dependency(target, content):
    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    (target / "example.py").write_text(content, encoding="utf-8")
    metadata = target / "example-1.0.dist-info"
    metadata.mkdir(exist_ok=True)
    (metadata / "METADATA").write_text("Name: example\nVersion: 1.0\n", encoding="utf-8")


@pytest.mark.parametrize("mode", ["already_installed", "empty", "failed", "success"])
def test_clean_reinstall_preserves_old_overlay_until_success(tmp_path, mode):
    manager = RuntimeEnvironmentManager(tmp_path / "Lib")
    meta = {"category": "tts", "item_id": "test", "op": "install"}
    tx = manager.begin(meta=meta, requested_specs=["example==1.0"],
                       required_backend=BackendKind.NONE, backend_context={})
    _write_dependency(tx.site_packages, "stale dependency")
    old = tx.commit()

    class Installer:
        script_path = sys.executable

        def __init__(self, target):
            self.target = target

        def install_environment_lock(self, *args, **kwargs):
            assert (old.site_packages / "example.py").read_text() == "stale dependency"
            _write_dependency(self.target, "fresh dependency")
            return mode != "failed"

        def cancel(self):
            pass

    class Controller(InstallController):
        def __init__(self):
            self.environment_manager = manager
            self.event_bus = Mock()

        def _make_pip_installer(self, callbacks, target_path=None):
            return Installer(target_path)

        def _release_pip_installer(self, installer):
            pass

    plan = InstallPlan(actions=[], required_backend=BackendKind.NONE)
    if mode == "already_installed":
        plan.already_installed = True
    elif mode in {"failed", "success"}:
        plan.actions = [InstallAction(type="pip", packages=["example==1.0"])]

    result = Controller().run_task(
        task_id="clean-reinstall", runner=lambda **kwargs: plan,
        meta={**meta, "clean": True},
    )
    current = manager.active(old.logical_id)
    if mode == "success":
        assert result is True
        assert current.revision_id != old.revision_id
        assert current.packages == old.packages
        assert (current.site_packages / "example.py").read_text() == "fresh dependency"
    else:
        assert result is False
        assert current.revision_id == old.revision_id
        assert (old.site_packages / "example.py").read_text() == "stale dependency"
    assert not list(manager.staging_root.glob("e-*"))
