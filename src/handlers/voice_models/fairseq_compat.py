from __future__ import annotations

import os
import re
from pathlib import Path

from core.error_utils import format_exception


_HYDRA_IMPORT = """try:
    from hydra import compose, initialize
except ImportError:
    from hydra.experimental import compose, initialize"""


def patch_fairseq_compatibility(*, pip_installer=None, callbacks=None, ctx=None, **_kwargs) -> bool:
    context = dict(ctx or {})
    target = (
        getattr(pip_installer, "libs_path_abs", None)
        or context.get("target_dir")
        or context.get("libs_dir")
    )
    if not target:
        return False

    def log(message: str) -> None:
        if callbacks is not None:
            callbacks.log(message)

    root = Path(target) / "fairseq" / "dataclass"
    try:
        for name in ("configs.py", "utils.py"):
            path = root / name
            if not path.is_file():
                continue
            with path.open(encoding="utf-8", newline="") as stream:
                source = stream.read()
            if name == "configs.py":
                patched = re.sub(r"metadata=\{(.*?)help:", r'metadata={\1"help":', source)
            else:
                newline = "\r\n" if "\r\n" in source else "\n"
                patched = re.sub(
                    r"^from hydra\.experimental import compose, initialize[ \t]*(?=\r?$)",
                    _HYDRA_IMPORT.replace("\n", newline),
                    source,
                    flags=re.MULTILINE,
                )
                patched = re.sub(
                    r"(?P<indent>^[ \t]*)(?P<name>\w+) = compose\("
                    r"(?P<args>[^\n]*?),\s*strict=False\)",
                    lambda match: (
                        f"{match['indent']}{match['name']} = compose({match['args']})"
                        f"{newline}{match['indent']}OmegaConf.set_struct({match['name']}, False)"
                    ),
                    patched,
                    flags=re.MULTILINE,
                )
            if patched != source:
                compile(patched, os.fspath(path), "exec")
                with path.open("w", encoding="utf-8", newline="") as stream:
                    stream.write(patched)
                log(f"Patched fairseq/dataclass/{name}")
        return True
    except Exception as exc:
        log(f"Failed to patch fairseq compatibility: {format_exception(exc)}")
        return False
