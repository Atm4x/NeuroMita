from types import SimpleNamespace
from unittest.mock import patch

import pytest

from core.backends import BackendKind
from core.install_requirements import InstallRequirement
from core.installables import ComponentStatusCode
from handlers.voice_models.base_model import IVoiceModel
from handlers.voice_models.f5_tts_model import F5TTSInstallSpec, F5TTSModel
from handlers.voice_models.fish_speech_model import FishSpeechInstallSpec, FishSpeechModel
from handlers.voice_models.omnivoice_model import OmniVoiceInstallSpec, OmniVoiceModel


@pytest.mark.parametrize("model_cls,spec", [
    (OmniVoiceModel, OmniVoiceInstallSpec),
    (FishSpeechModel, FishSpeechInstallSpec),
    (F5TTSModel, F5TTSInstallSpec),
])
@pytest.mark.parametrize("present_count,expected", [
    (0, ComponentStatusCode.NOT_INSTALLED),
    (1, ComponentStatusCode.NEEDS_REINSTALL),
    (2, ComponentStatusCode.READY),
])
def test_model_status_checks_install_spec_files(tmp_path, model_cls, spec, present_count, expected):
    paths = [tmp_path / "config.json", tmp_path / "weights.bin"]
    for path in paths[:present_count]:
        path.write_bytes(b"test")
    requirements = [
        InstallRequirement(id=str(index), kind="file", path=str(path), required=True)
        for index, path in enumerate(paths)
    ]
    for model_id in model_cls.supported_model_ids():
        model = model_cls(SimpleNamespace(), model_id)
        with patch.object(spec, "requirements", return_value=requirements) as probe, patch.object(
            model_cls, "required_backend_for_model", return_value=BackendKind.NONE
        ):
            status = model.status({"gpu_vendor": "CPU"})
        assert status.code == expected, (model_id, status.message)
        assert status.ready == (expected == ComponentStatusCode.READY)
        assert status.installed == (present_count > 0)
        assert probe.call_args.args[0] == model_id


@pytest.mark.parametrize("installed", [False, True])
def test_models_without_requirements_keep_installation_probe(installed):
    class LegacyModel(OmniVoiceModel):
        requirements = classmethod(IVoiceModel.requirements.__func__)

    model = LegacyModel(SimpleNamespace(), "legacy")
    with patch.object(LegacyModel, "is_model_installed", return_value=installed) as probe, patch.object(
        LegacyModel, "required_backend_for_model", return_value=BackendKind.NONE
    ):
        status = model.status({"gpu_vendor": "CPU"})
    assert status.code == (ComponentStatusCode.READY if installed else ComponentStatusCode.NOT_INSTALLED)
    probe.assert_called_once()
