"""
UvSync — per-extra hardlink installer driven by [tool.neuromita.extras] from pyproject.toml.

Replaces the global `uv pip install --target Lib/` approach with per-extra isolation:
each extra group goes into packages/<target>/.lib/site-packages/ via
`uv pip compile` + `uv pip install --target --link-mode=hardlink`.
"""

from __future__ import annotations

import gc
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections import deque
from typing import Deque, List, Optional, Tuple

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        tomllib = None  # type: ignore[assignment]

try:
    from main_logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

try:
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QCoreApplication, QThread
    _PYQT_AVAILABLE = True
except ImportError:
    _PYQT_AVAILABLE = False
    QApplication = None  # type: ignore[assignment,misc]
    QCoreApplication = None  # type: ignore[assignment]
    QThread = None  # type: ignore[assignment]


class UvSync:
    """Synchronise packages/<target>/.lib/site-packages/ for each extra group."""

    # ------------------------------------------------------------------ timeouts
    STALL_INFO_SEC  = 10
    STALL_HINT_SEC  = 60
    TIMEOUT_SEC     = 7_200_000   # effectively unlimited
    NO_ACTIVITY_SEC = 3_600_000

    # ------------------------------------------------------------------ regexes
    _RE_PCT = re.compile(r'(\d{1,3})\s?%')
    _RE_PAIR = re.compile(
        r'(?P<done>\d+(?:\.\d+)?)\s*(?P<dunit>[KMGTP]?i?B|B)\s*/\s*'
        r'(?P<total>\d+(?:\.\d+)?)\s*(?P<tunit>[KMGTP]?i?B|B)',
        re.IGNORECASE,
    )
    _ANSI_RE = re.compile(r'\x1b(?:\[.*?[@-~]|\].*?(?:\x1b\\|\x07))')

    # ------------------------------------------------------------------ inner state
    class _RunState:
        def __init__(self, description: str, cmd: List[str]):
            self.description = description
            self.cmd = cmd
            self.cmd_str_low = " ".join(cmd).lower()
            self.start = time.time()
            self.last_activity = self.start
            self.last_status_emit = self.start
            self.last_status_message: Optional[str] = None
            self.percent: int = 0
            self.history: Deque[tuple[float, int]] = deque(maxlen=180)
            self.history.append((self.start, 0))
            self.error_seen: bool = False
            self.is_pytorch_install: bool = (
                ("download.pytorch.org" in self.cmd_str_low)
                or ("torch" in self.cmd_str_low and "install" in self.cmd_str_low)
            )
            self.torch_hint_logged: bool = False

    # ================================================================== init

    def __init__(self, update_status=None, update_log=None, update_progress=None):
        self.python_exe  = os.environ.get("NEUROMITA_PYTHON", sys.executable)
        self.base_dir    = os.environ.get("NEUROMITA_BASE_DIR", os.getcwd())
        self.pyproject_path = os.path.join(self.base_dir, "pyproject.toml")
        self._state_path    = os.path.join(self.base_dir, ".uv-state.json")

        self.update_status   = update_status   or (lambda m: logger.info(f"STATUS: {m}"))
        self.update_log      = update_log      or (lambda m: logger.info(f"LOG: {m}"))
        self.update_progress = update_progress or (lambda *_: None)

    # ================================================================== public API
    
    def apply(self, desired: set[str]) -> bool:
        desired_list = self._order_extras(desired)
        if not desired_list:
            self._save_state_atomic([])
            return True

        if not os.path.isfile(self.pyproject_path):
            self.update_log(f"pyproject.toml not found: {self.pyproject_path}")
            return False

        use_torch_cu128 = "backend-nvidia" in set(desired_list)
        torch_index_url = "https://download.pytorch.org/whl/cu128"
        pypi_index_url = "https://pypi.org/simple"

        req_dir = os.path.join(self.base_dir, ".uv")
        os.makedirs(req_dir, exist_ok=True)

        compiled_req = os.path.join(req_dir, "requirements.compiled.txt")
        sync_req = os.path.join(req_dir, "requirements.txt")

        compile_cmd = [
            self.python_exe, "-m", "uv", "pip", "compile",
            self.pyproject_path,
            "--python", self.python_exe,
            "--quiet",
            "-o", compiled_req,
        ]
        if use_torch_cu128:
            compile_cmd += ["--index-url", torch_index_url, "--extra-index-url", pypi_index_url]
        for e in desired_list:
            compile_cmd += ["--extra", e]

        if not self._run(compile_cmd, "compile"):
            return False

        try:
            compiled_ref = compiled_req.replace("\\", "/")
            with open(sync_req, "w", encoding="utf-8") as f:
                if use_torch_cu128:
                    f.write(f"--index-url {torch_index_url}\n")
                    f.write(f"--extra-index-url {pypi_index_url}\n")
                f.write("pip\nsetuptools\nuv\n")
                f.write(f"-r {compiled_ref}\n")
        except Exception as exc:
            self.update_log(f"Failed to write sync requirements: {exc}")
            return False

        sync_cmd = [
            self.python_exe, "-m", "uv", "pip", "sync",
            sync_req,
            "--python", self.python_exe,
        ]
        if not self._run(sync_cmd, "sync"):
            return False

        self._save_state_atomic(desired_list)
        return True

    def dry_run(self, desired: set[str]) -> dict:
        desired_list = self._order_extras(desired)
        if not desired_list:
            return {"ok": True, "actions": []}

        req_dir = os.path.join(self.base_dir, ".uv")
        os.makedirs(req_dir, exist_ok=True)

        compiled_req = os.path.join(req_dir, "requirements.compiled.txt")
        sync_req = os.path.join(req_dir, "requirements.txt")

        compile_cmd = [
            self.python_exe, "-m", "uv", "pip", "compile",
            self.pyproject_path,
            "--python", self.python_exe,
            "--quiet",
            "-o", compiled_req,
        ]
        for e in desired_list:
            compile_cmd += ["--extra", e]

        if not self._run(compile_cmd, "compile (dry_run)"):
            return {"ok": False, "actions": [{"extras": desired_list, "changes": "compile failed"}]}

        try:
            with open(compiled_req, "r", encoding="utf-8", errors="ignore") as f:
                compiled_text = f.read()
            with open(sync_req, "w", encoding="utf-8") as f:
                f.write("pip\nsetuptools\nuv\n")
                if compiled_text and not compiled_text.endswith("\n"):
                    compiled_text += "\n"
                f.write(compiled_text or "")
        except Exception as exc:
            return {"ok": False, "actions": [{"extras": desired_list, "changes": f"write requirements failed: {exc}"}]}

        sync_cmd = [
            self.python_exe, "-m", "uv", "pip", "sync",
            sync_req,
            "--python", self.python_exe,
            "--dry-run",
        ]
        ok, output = self._run_capture(sync_cmd, "sync (dry-run)")
        return {"ok": ok, "actions": [{"extras": desired_list, "changes": (output.strip() or "(no changes)")}]} 

    def _addsitedir_prepend(self, path: str) -> None:
        if not path or not os.path.isdir(path):
            return
        try:
            import site
            site.addsitedir(path)
        except Exception:
            if path not in sys.path:
                sys.path.append(path)
        try:
            while path in sys.path:
                sys.path.remove(path)
            sys.path.insert(0, path)
        except Exception:
            pass
        try:
            import importlib
            importlib.invalidate_caches()
        except Exception:
            pass


    @staticmethod
    def _order_extras(extras) -> list[str]:
        def _k(name: str):
            if name == "core":
                return (0, name)
            if name.startswith("backend-"):
                return (1, name)
            if name.startswith("rvc-"):
                return (2, name)
            if name.startswith("asr-"):
                return (3, name)
            return (9, name)
        return sorted([str(e) for e in (extras or [])], key=_k)
    # ================================================================== state helpers

    def _load_extras_map(self) -> dict[str, str]:
        """Resolve extras -> target_rel.

        Priority:
        1) [tool.neuromita.extras] if present (custom mapping)
        2) fallback: [project.optional-dependencies] keys -> "packages"
        """
        if tomllib is None:
            logger.warning("tomllib/tomli not available; cannot read pyproject.toml extras map.")
            return {}
        if not os.path.isfile(self.pyproject_path):
            logger.warning(f"pyproject.toml not found at {self.pyproject_path}")
            return {}

        try:
            with open(self.pyproject_path, "rb") as f:
                data = tomllib.load(f)

            tool_map = data.get("tool", {}).get("neuromita", {}).get("extras", {})
            result: dict[str, str] = {}

            if isinstance(tool_map, dict) and tool_map:
                for name, val in tool_map.items():
                    if isinstance(val, dict) and "target" in val:
                        result[str(name)] = str(val["target"])
                    elif isinstance(val, str):
                        result[str(name)] = val
                return result

            opt = data.get("project", {}).get("optional-dependencies", {})
            if isinstance(opt, dict) and opt:
                for extra_name in opt.keys():
                    result[str(extra_name)] = "packages"
                return result

            return {}
        except Exception as exc:
            logger.warning(f"Failed to parse extras map from pyproject.toml: {exc}")
            return {}

    def _load_state(self) -> list[str]:
        """Read .uv-state.json -> list of active extras. Empty list if missing."""
        if not os.path.isfile(self._state_path):
            return []
        try:
            with open(self._state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return list(data.get("extras", []))
        except Exception as exc:
            logger.warning(f"Failed to read .uv-state.json: {exc}")
            return []

    def _save_state_atomic(self, extras: list[str]) -> None:
        """Write .uv-state.json atomically via tmp + os.replace."""
        payload = json.dumps({"extras": sorted(extras)}, indent=2, ensure_ascii=False)
        tmp_path = self._state_path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(payload)
            os.replace(tmp_path, self._state_path)
        except Exception as exc:
            logger.error(f"Failed to write .uv-state.json: {exc}")
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    # ================================================================== run helpers

    def _run(self, cmd: List[str], description: str) -> bool:
        """Run *cmd*, stream output through callbacks. Returns True iff exit code == 0."""
        state = self._RunState(description, cmd)
        env   = self._prepare_env()

        self.update_status(description)
        self.update_log("Выполняем: " + " ".join(cmd))

        use_pty, PtyProcess = self._detect_pty()
        ok, ret = False, -1

        if use_pty and PtyProcess is not None and os.name == "nt":
            ok, ret = self._run_with_winpty(cmd, env, state, PtyProcess)
            if not ok:
                ok, ret = self._run_with_pipes(cmd, env, state)
        else:
            ok, ret = self._run_with_pipes(cmd, env, state)

        elapsed = time.time() - state.start
        self.update_status(f"{description} — завершено за {self._fmt_hms(elapsed)}")

        if not ok or ret != 0:
            err_msg = f"ОШИБКА: процесс завершился с кодом {ret}. Проверьте лог выше."
            if not state.error_seen:
                self.update_log(err_msg)
            logger.error(f"uv завершился с ошибкой, код {ret}. Команда: {cmd}")
            return False

        self.update_progress(100)
        self.update_log(f"uv завершился успешно (код {ret})")
        return True

    def _run_capture(self, cmd: List[str], description: str) -> tuple[bool, str]:
        """Run *cmd* and return (success, combined_stdout) without streaming callbacks."""
        env = self._prepare_env()
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                encoding="utf-8",
                errors="ignore",
                env=env,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return result.returncode == 0, result.stdout or ""
        except Exception as exc:
            logger.error(f"_run_capture({description}) failed: {exc}")
            return False, str(exc)

    def _rmtree_retry(self, path: str) -> bool:
        """Remove *path* directory tree with retries (port of old _manual_remove)."""
        if not os.path.exists(path):
            return True
        retries = 5
        wait = [0.5, 1, 2, 3, 5]
        for attempt in range(retries):
            try:
                shutil.rmtree(path, ignore_errors=False)
                if not os.path.exists(path):
                    self.update_log(f"Каталог {path} удалён.")
                    return True
            except Exception as exc:
                logger.warning(f"Не удалось удалить {path} (попытка {attempt+1}/{retries}): {exc}")
                gc.collect()
                time.sleep(wait[attempt])
        try:
            shutil.rmtree(path, ignore_errors=True)
        except Exception:
            pass
        if os.path.exists(path):
            logger.error(f"Не удалось удалить каталог {path} после всех попыток.")
            self.update_log(f"ОШИБКА: не удалось удалить {path}")
            return False
        self.update_log(f"Каталог {path} удалён после нескольких попыток.")
        return True

    # ================================================================== process runner

    def _prepare_env(self) -> dict:
        env = os.environ.copy()
        env.setdefault("PIP_PROGRESS_BAR",   "on")
        env.setdefault("PYTHONIOENCODING",    "utf-8")
        env.setdefault("PYTHONUTF8",          "1")
        env.setdefault("NO_COLOR",            "1")
        env.setdefault("CLICOLOR",            "0")
        env.setdefault("FORCE_COLOR",         "0")
        env.setdefault("PY_COLORS",           "0")
        env.setdefault("TERM",                "dumb")
        return env

    def _detect_pty(self) -> Tuple[bool, Optional[object]]:
        is_windows   = os.name == "nt"
        uv_tty_env   = os.environ.get("UV_TTY")
        if uv_tty_env == "0":
            return False, None

        PtyProcess = None
        if is_windows:
            try:
                from pywinpty import PtyProcess as _PtyProcess  # type: ignore[import]
                PtyProcess = _PtyProcess
            except Exception:
                try:
                    import winpty  # type: ignore[import]
                    PtyProcess = winpty.PtyProcess
                except Exception:
                    PtyProcess = None

        if uv_tty_env == "1":
            return PtyProcess is not None, PtyProcess

        return PtyProcess is not None, PtyProcess

    def _process_line(self, state: _RunState, line: str):
        if not line:
            return
        clean = self._clean_line(line.rstrip())
        if not clean:
            return

        low = clean.lower()
        if any(k in low for k in ("error", "ошибка", "failed", "traceback", "exception", "critical")):
            logger.error(clean)
            self.update_log(clean)
            state.error_seen = True
        else:
            m = self._RE_PCT.search(clean)
            if m:
                try:
                    pct = max(0, min(100, int(m.group(1))))
                    if pct > state.percent:
                        state.percent = min(99, pct)
                        self.update_progress(state.percent)
                        state.history.append((time.time(), state.percent))
                except Exception:
                    pass

            m2 = self._RE_PAIR.search(clean)
            if m2:
                try:
                    d = float(m2.group("done"))  * self._unit_mul(m2.group("dunit"))
                    T = float(m2.group("total")) * self._unit_mul(m2.group("tunit"))
                    if T > 0:
                        pct2 = int(round(d / T * 100))
                        if pct2 > state.percent:
                            state.percent = min(99, max(0, pct2))
                            self.update_progress(state.percent)
                            state.history.append((time.time(), state.percent))
                except Exception:
                    pass

            self.update_log(clean)

        state.last_activity = time.time()

    def _update_status_if_needed(self, state: _RunState):
        now = time.time()
        if now - state.last_status_emit < 0.5:
            return

        eta_txt = ""
        if len(state.history) >= 2 and state.percent >= 3:
            t0, p0 = state.history[0]
            dt = now - t0
            dp = state.percent - p0
            if dt > 0 and dp > 0:
                eta_sec = int(max(0.0, (100.0 - state.percent)) / (dp / dt))
                eta_txt = f" (ETA {self._fmt_hms(eta_sec)})"

        stalled_sec = int(now - state.last_activity)
        msg = f"{state.description} — {state.percent}%"
        if eta_txt:
            msg += eta_txt
        elif stalled_sec >= self.STALL_INFO_SEC:
            msg += f" (нет вывода {stalled_sec} с, процесс работает)"

        if msg != state.last_status_message:
            self.update_status(msg)
            state.last_status_message = msg

        if (state.is_pytorch_install
                and stalled_sec >= self.STALL_HINT_SEC
                and not state.torch_hint_logged):
            self.update_log(
                "Похоже, идёт загрузка больших бинарников PyTorch. "
                "Это может занимать длительное время без вывода."
            )
            state.torch_hint_logged = True

        state.last_status_emit = now

    def _pump_events(self):
        if not _PYQT_AVAILABLE:
            return
        app = QCoreApplication.instance()
        if app and QThread.currentThread() == app.thread():
            QApplication.processEvents()

    def _terminate_process(self, proc, reason: str):
        try:
            self.update_log(reason)
            proc.terminate()
            time.sleep(0.5)
            if proc.poll() is None:
                proc.kill()
        except Exception:
            pass

    def _run_with_pipes(self, cmd: List[str], env: dict, state: _RunState) -> Tuple[bool, int]:
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                encoding="utf-8",
                errors="ignore",
                bufsize=1,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                env=env,
            )
        except FileNotFoundError:
            self.update_log("ОШИБКА: не найден интерпретатор Python.")
            self.update_status(state.description + " — ошибка.")
            return False, -1
        except Exception as exc:
            self.update_log(f"ОШИБКА запуска subprocess: {exc}")
            self.update_status(state.description + " — ошибка.")
            return False, -1

        q_out: queue.Queue[str] = queue.Queue()
        q_err: queue.Queue[str] = queue.Queue()

        def _reader(pipe, q):
            try:
                for line in iter(pipe.readline, ""):
                    q.put(line.rstrip())
            finally:
                try:
                    pipe.close()
                except Exception:
                    pass

        threading.Thread(target=_reader, args=(proc.stdout, q_out), daemon=True).start()
        threading.Thread(target=_reader, args=(proc.stderr, q_err), daemon=True).start()

        while proc.poll() is None:
            while not q_out.empty():
                self._process_line(state, q_out.get_nowait())
            while not q_err.empty():
                self._process_line(state, q_err.get_nowait())

            self._update_status_if_needed(state)

            now = time.time()
            if now - state.last_activity > self.NO_ACTIVITY_SEC:
                self._terminate_process(proc, "Процесс неактивен слишком долго, прерываем.")
                self.update_status(state.description + " — прервано по таймауту неактивности.")
                return False, -1
            if now - state.start > self.TIMEOUT_SEC:
                self._terminate_process(proc, "Таймаут процесса истёк, прерываем.")
                self.update_status(state.description + " — прервано по общему таймауту.")
                return False, -1

            self._pump_events()
            time.sleep(0.03)

        while not q_out.empty():
            self._process_line(state, q_out.get_nowait())
        while not q_err.empty():
            self._process_line(state, q_err.get_nowait())

        return True, (proc.returncode or 0)

    def _run_with_winpty(self, cmd: List[str], env: dict, state: _RunState, PtyProcess) -> Tuple[bool, int]:
        try:
            try:
                cmdline = subprocess.list2cmdline(cmd)
            except Exception:
                import shlex
                cmdline = " ".join(shlex.quote(c) if " " in c else c for c in cmd)
            pty = PtyProcess.spawn(cmdline)
        except Exception as exc:
            logger.warning(f"PTY-режим недоступен или ошибка запуска PTY: {exc}")
            return False, -1

        buffer = ""
        while pty.isalive():
            try:
                chunk = pty.read(4096)
            except Exception:
                chunk = ""

            if chunk:
                if isinstance(chunk, bytes):
                    try:
                        chunk = chunk.decode("utf-8", errors="ignore")
                    except Exception:
                        chunk = chunk.decode("cp1251", errors="ignore")
                buffer += chunk
                parts = re.split(r'(\r|\n)', buffer)
                buffer = ""
                acc = ""
                for tok in parts:
                    if tok in ("\r", "\n"):
                        line = acc.strip()
                        if line:
                            self._process_line(state, line)
                        acc = ""
                    else:
                        acc += tok
                buffer = acc

            self._update_status_if_needed(state)

            now = time.time()
            if now - state.last_activity > self.NO_ACTIVITY_SEC:
                try:
                    pty.close(force=True)
                except Exception:
                    pass
                self.update_log("Процесс неактивен слишком долго, прерываем.")
                self.update_status(state.description + " — прервано по таймауту неактивности.")
                return False, -1
            if now - state.start > self.TIMEOUT_SEC:
                try:
                    pty.close(force=True)
                except Exception:
                    pass
                self.update_log("Таймаут процесса истёк, прерываем.")
                self.update_status(state.description + " — прервано по общему таймауту.")
                return False, -1

            self._pump_events()
            time.sleep(0.03)

        ret = pty.exitstatus or 0
        return True, ret

    # ================================================================== static helpers

    @staticmethod
    def _unit_mul(unit: str) -> int:
        u = unit.upper()
        dec  = {"B": 1, "KB": 1_000, "MB": 1_000**2, "GB": 1_000**3, "TB": 1_000**4, "PB": 1_000**5}
        bin_ = {"KIB": 1024, "MIB": 1024**2, "GIB": 1024**3, "TIB": 1024**4, "PIB": 1024**5}
        return bin_.get(u, dec.get(u, 1))

    @staticmethod
    def _fmt_hms(seconds: float) -> str:
        seconds = int(max(0, seconds))
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

    @classmethod
    def _clean_line(cls, s: str) -> str:
        if not s:
            return ""
        return cls._ANSI_RE.sub("", s).replace("\x1b", "")
