from __future__ import annotations

import os
import tempfile

from core.install_types import InstallCallbacks
from main_logger import logger
from utils.pip_installer import PipInstaller


class UvSync:
    def apply(
        self,
        desired_specs: set[str],
        *,
        use_cache: bool = False,
        callbacks: InstallCallbacks | None = None,
    ) -> bool:
        cb = callbacks or InstallCallbacks(
            progress=lambda *_: None,
            status=lambda s: logger.info(str(s)),
            log=lambda m: logger.info(str(m)),
        )
        pip_installer = PipInstaller(update_status=cb.status, update_log=cb.log, update_progress=cb.progress)

        specs = sorted({str(spec).strip() for spec in (desired_specs or set()) if str(spec).strip()})
        if not specs:
            cb.status("Nothing to sync")
            cb.progress(100)
            return True

        with tempfile.TemporaryDirectory(prefix="neuromita-uv-sync-") as tmpdir:
            req_path = os.path.join(tmpdir, "requirements-sync.txt")
            lock_path = os.path.join(tmpdir, "requirements-sync.lock")

            with open(req_path, "w", encoding="utf-8") as f:
                f.write("\n".join(specs) + "\n")

            compile_cmd = [pip_installer.script_path, "-m", "uv", "pip", "compile", req_path, "-o", lock_path]
            sync_cmd = [pip_installer.script_path, "-m", "uv", "pip", "sync", lock_path]
            if not use_cache:
                compile_cmd.append("--no-cache-dir")
                sync_cmd.append("--no-cache-dir")

            cb.status("Compiling sync lockfile")
            cb.progress(10)
            if not pip_installer._run_pip_process(compile_cmd, "uv pip compile"):
                return False

            cb.status("Syncing embedded Python environment")
            cb.progress(60)
            if not pip_installer._run_pip_process(sync_cmd, "uv pip sync"):
                return False

        cb.progress(100)
        cb.status("uv pip sync completed")
        return True
