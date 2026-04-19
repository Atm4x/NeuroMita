from __future__ import annotations

import os
import re
import subprocess
import traceback

try:
    from main_logger import logger
except Exception:
    import logging
    logger = logging.getLogger(__name__)


def _cow_write(path: str, new_text: str) -> bool:
    with open(path, "r", encoding="utf-8") as f:
        old_text = f.read()
    if old_text == new_text:
        return False
    os.unlink(path)
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_text)
    return True


def _iter_site_packages(base_dir: str, active: list[str], extras_map: dict) -> list[str]:
    sp = os.path.join(base_dir, "packages")
    return [sp] if os.path.isdir(sp) else []


def _apply_fairseq_patch(site_packages: str) -> None:
    config_path = os.path.join(site_packages, "fairseq", "dataclass", "configs.py")
    if not os.path.exists(config_path):
        return
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            source = f.read()
        patched = re.sub(r"metadata=\{(.*?)help:", r'metadata={\1"help":', source)
        if _cow_write(config_path, patched):
            logger.success("Патч успешно применён к fairseq/dataclass/configs.py")
    except Exception:
        logger.warning("Не удалось применить патч fairseq", exc_info=True)

    audio_path = os.path.join(site_packages, "tts_with_rvc", "lib", "audio.py")
    if not os.path.exists(audio_path):
        return
    try:
        with open(audio_path, "r", encoding="utf-8") as f:
            source = f.read()
        patched = re.sub(
            r"\bimport ffmpeg\b",
            'import importlib\nffmpeg = importlib.import_module("ffmpeg")',
            source,
        )
        if _cow_write(audio_path, patched):
            logger.success("Патч успешно применён к tts_with_rvc/lib/audio.py")
    except Exception:
        logger.warning("Не удалось применить патч tts_with_rvc audio.py", exc_info=True)


def _apply_triton_patches(site_packages: str) -> None:
    triton_dir = os.path.join(site_packages, "triton")
    if not os.path.isdir(triton_dir):
        return

    build_py_path = os.path.join(triton_dir, "runtime", "build.py")
    if os.path.exists(build_py_path):
        try:
            with open(build_py_path, "r", encoding="utf-8") as f:
                source = f.read()
            patched = re.sub(
                r'cc\s*=\s*os\.path\.join\(\s*sysconfig\.get_paths\(\)\s*\[\s*"platlib"\s*\]\s*,\s*"triton"\s*,\s*"runtime"\s*,\s*"tcc"\s*,\s*"tcc\.exe"\s*\)',
                'cc = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tcc", "tcc.exe")',
                source,
            )
            patched = patched.replace(
                'cc_cmd = [cc, src, "-O3", "-shared", "-fPIC", "-Wno-psabi", "-o", out]',
                'cc_cmd = [cc, src, "-O3", "-shared", "-Wno-psabi", "-o", out]',
            )
            if _cow_write(build_py_path, patched):
                logger.success("Патчи применены к triton/runtime/build.py")
        except Exception:
            logger.warning("Не удалось применить патч triton/runtime/build.py", exc_info=True)

    windows_utils_path = os.path.join(triton_dir, "windows_utils.py")
    if os.path.exists(windows_utils_path):
        try:
            with open(windows_utils_path, "r", encoding="utf-8") as f:
                source = f.read()
            patched = source.replace(
                "output = subprocess.check_output(command, text=True).strip()",
                "output = subprocess.check_output(\n"
                "            command, text=True, creationflags=subprocess.CREATE_NO_WINDOW, close_fds=True, "
                "stdin=subprocess.DEVNULL, stderr=subprocess.PIPE\n"
                "        ).strip()",
            )
            if _cow_write(windows_utils_path, patched):
                logger.success("Патч применён к triton/windows_utils.py")
        except Exception:
            logger.warning("Не удалось применить патч triton/windows_utils.py", exc_info=True)

    compiler_path = os.path.join(triton_dir, "backends", "nvidia", "compiler.py")
    if os.path.exists(compiler_path):
        try:
            with open(compiler_path, "r", encoding="utf-8") as f:
                source = f.read()
            patched = source.replace(
                'version = subprocess.check_output([_path_to_binary("ptxas")[0], "--version"]).decode("utf-8")',
                'version = subprocess.check_output([_path_to_binary("ptxas")[0], "--version"], creationflags=subprocess.CREATE_NO_WINDOW, stderr=subprocess.PIPE, close_fds=True, stdin=subprocess.DEVNULL).decode("utf-8")',
            )
            if _cow_write(compiler_path, patched):
                logger.success("Патч применён к triton/backends/nvidia/compiler.py")
        except Exception:
            logger.warning("Не удалось применить патч triton/backends/nvidia/compiler.py", exc_info=True)

    cache_py_path = os.path.join(triton_dir, "runtime", "cache.py")
    if os.path.exists(cache_py_path):
        try:
            with open(cache_py_path, "r", encoding="utf-8") as f:
                source = f.read()
            patched = source.replace(
                'temp_dir = os.path.join(self.cache_dir, f"tmp.pid_{pid}_{rnd_id}")',
                'temp_dir = os.path.join(self.cache_dir, f"tmp.pid_{str(pid)[:5]}_{str(rnd_id)[:5]}")',
            )
            if _cow_write(cache_py_path, patched):
                logger.success("Патч применён к triton/runtime/cache.py")
        except Exception:
            logger.warning("Не удалось применить патч triton/runtime/cache.py", exc_info=True)


def apply_runtime_patches(base_dir: str, active: list[str], extras_map: dict) -> None:
    for site_packages in _iter_site_packages(base_dir, active, extras_map):
        try:
            _apply_fairseq_patch(site_packages)
            _apply_triton_patches(site_packages)
        except Exception:
            logger.warning(f"Runtime patch failed for {site_packages}:\n{traceback.format_exc()}")
