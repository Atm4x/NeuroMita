import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from handlers.voice_models.fairseq_compat import patch_fairseq_compatibility


class FairseqCompatibilityTests(unittest.TestCase):
    def _write_utils(self, root, newline="\n"):
        path = Path(root) / "fairseq" / "dataclass" / "utils.py"
        path.parent.mkdir(parents=True)
        source = (
            "from hydra.experimental import compose, initialize\n"
            "from omegaconf import OmegaConf\n"
            "def convert():\n"
            "    with initialize(config_path='../config'):\n"
            "        composed_cfg = compose('config', overrides=[], strict=False)\n"
            "        composed_cfg['deleted'] = None\n"
            "    return composed_cfg\n"
        )
        path.write_bytes(source.replace("\n", newline).encode())
        return path

    def test_patched_conversion_uses_modern_hydra_and_allows_missing_keys(self):
        hydra = ModuleType("hydra")
        experimental = ModuleType("hydra.experimental")
        calls = []

        class Config(dict):
            structured = True

            def __setitem__(self, key, value):
                if self.structured and key not in self:
                    raise KeyError(key)
                super().__setitem__(key, value)

        def compose(config_name, overrides):
            calls.append((config_name, overrides))
            return Config()

        class Initialize:
            def __init__(self, config_path):
                self.config_path = config_path

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        hydra.compose = compose
        hydra.initialize = Initialize
        omega = ModuleType("omegaconf")
        omega.OmegaConf = SimpleNamespace(
            set_struct=lambda cfg, value: setattr(cfg, "structured", value)
        )
        with tempfile.TemporaryDirectory() as root:
            path = self._write_utils(root)
            self.assertTrue(patch_fairseq_compatibility(ctx={"target_dir": root}))
            namespace = {}
            with patch.dict(sys.modules, {
                "hydra": hydra, "hydra.experimental": experimental, "omegaconf": omega,
            }):
                exec(compile(path.read_text(), str(path), "exec"), namespace)
                self.assertEqual(namespace["convert"](), {"deleted": None})
            self.assertEqual(calls, [("config", [])])

    def test_patch_is_idempotent_and_preserves_windows_newlines(self):
        with tempfile.TemporaryDirectory() as root:
            path = self._write_utils(root, "\r\n")
            self.assertTrue(patch_fairseq_compatibility(ctx={"target_dir": root}))
            first = path.read_bytes()
            self.assertIn(b"from hydra import compose, initialize\r\n", first)
            self.assertNotIn(b"\n", first.replace(b"\r\n", b""))
            self.assertTrue(patch_fairseq_compatibility(ctx={"target_dir": root}))
            self.assertEqual(path.read_bytes(), first)

    def test_legacy_hydra_remains_supported(self):
        hydra = ModuleType("hydra")
        hydra.__path__ = []
        experimental = ModuleType("hydra.experimental")
        experimental.compose = object()
        experimental.initialize = object()
        omega = ModuleType("omegaconf")
        omega.OmegaConf = object()
        with tempfile.TemporaryDirectory() as root:
            path = self._write_utils(root)
            self.assertTrue(patch_fairseq_compatibility(ctx={"target_dir": root}))
            namespace = {}
            with patch.dict(sys.modules, {
                "hydra": hydra, "hydra.experimental": experimental, "omegaconf": omega,
            }):
                exec(compile(path.read_text(), str(path), "exec"), namespace)
            self.assertIs(namespace["compose"], experimental.compose)
            self.assertIs(namespace["initialize"], experimental.initialize)

    def test_installer_target_takes_precedence_and_existing_config_patch_is_preserved(self):
        with tempfile.TemporaryDirectory() as target, tempfile.TemporaryDirectory() as other:
            path = self._write_utils(target)
            untouched = self._write_utils(other)
            original = untouched.read_bytes()
            configs = path.with_name("configs.py")
            configs.write_text('value = dict(metadata={help: "description"})\n', encoding="utf-8")
            self.assertTrue(patch_fairseq_compatibility(
                pip_installer=SimpleNamespace(libs_path_abs=target),
                ctx={"target_dir": other},
            ))
            self.assertIn('metadata={"help":', configs.read_text())
            self.assertEqual(untouched.read_bytes(), original)

    def test_missing_target_is_rejected_and_absent_fairseq_is_skipped(self):
        self.assertFalse(patch_fairseq_compatibility())
        with tempfile.TemporaryDirectory() as root:
            self.assertTrue(patch_fairseq_compatibility(ctx={"target_dir": root}))

    def test_write_failure_is_reported_without_masking_original_error(self):
        messages = []
        with tempfile.TemporaryDirectory() as root:
            path = self._write_utils(root)
            with patch.object(Path, "open", side_effect=PermissionError("read denied")):
                self.assertFalse(patch_fairseq_compatibility(
                    ctx={"target_dir": root}, callbacks=SimpleNamespace(log=messages.append),
                ))
            self.assertTrue(path.exists())
        self.assertIn("read denied", messages[0])


if __name__ == "__main__":
    unittest.main()
