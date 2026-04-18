from __future__ import annotations

import os
import shutil
from core.install_types import InstallAction
from utils import getTranslationVariant as _


def remove_paths_action(paths: list[str], *, description: str, progress: int = 90) -> InstallAction:
    pp = [str(p).strip() for p in (paths or []) if str(p).strip()]

    def _rm(p: str) -> None:
        if not p:
            return
        if os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)
        elif os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass

    def _do_rm(*, callbacks=None, ctx=None, **_kwargs) -> bool:
        for p in pp:
            _rm(p)
        try:
            if callbacks:
                callbacks.status(description)
        except Exception:
            pass
        return True

    return InstallAction(type="call", description=description, progress=int(progress), fn=_do_rm)
