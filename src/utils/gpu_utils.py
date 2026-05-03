# src/utils/gpu_utils.py
import subprocess
import platform
import os
import re
import threading
import time
from core.backends import Backend, vendor_to_backend
from main_logger import logger

_GPU_VENDOR_LOCK = threading.Lock()
_GPU_VENDOR_CACHE: str | None = None
_GPU_VENDOR_TS = 0.0
_GPU_VENDOR_TTL_SEC = 120.0


def check_gpu_provider() -> str:
    """
    Возвращает вендора GPU как строку: "NVIDIA", "AMD" или "CPU".
    Никогда не возвращает None.

    На Windows пытается определить NVIDIA/AMD через WMIC, затем через PowerShell.
    Если определить не удалось — возвращает "CPU".
    """

    global _GPU_VENDOR_CACHE, _GPU_VENDOR_TS

    now = time.time()
    with _GPU_VENDOR_LOCK:
        if (now - float(_GPU_VENDOR_TS or 0.0)) < float(_GPU_VENDOR_TTL_SEC or 120.0) and _GPU_VENDOR_CACHE:
            return _GPU_VENDOR_CACHE

    # тестовые принудительные режимы
    if os.environ.get('TEST_AS_AMD', '').upper() == 'TRUE':
        with _GPU_VENDOR_LOCK:
            _GPU_VENDOR_CACHE = "AMD"
            _GPU_VENDOR_TS = now
        return "AMD"

    if os.environ.get('TEST_AS_NVIDIA', '').upper() == 'TRUE':
        with _GPU_VENDOR_LOCK:
            _GPU_VENDOR_CACHE = "NVIDIA"
            _GPU_VENDOR_TS = now
        return "NVIDIA"

    if platform.system() != "Windows":
        with _GPU_VENDOR_LOCK:
            _GPU_VENDOR_CACHE = "CPU"
            _GPU_VENDOR_TS = now
        return "CPU"

    def parse_output(output: str) -> str | None:
        out = (output or "").upper()
        if "NVIDIA" in out:
            return "NVIDIA"
        if "AMD" in out or "RADEON" in out:
            return "AMD"
        return None

    vendor: str | None = None

    # 1) WMIC
    try:
        output = subprocess.check_output(
            "wmic path win32_VideoController get name",
            shell=True,
            text=True,
            stdin=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=2.0
        ).strip()

        vendor = parse_output(output)
        if vendor:
            with _GPU_VENDOR_LOCK:
                _GPU_VENDOR_CACHE = vendor
                _GPU_VENDOR_TS = now
            return vendor

    except FileNotFoundError:
        pass
    except subprocess.TimeoutExpired:
        pass
    except subprocess.CalledProcessError:
        pass
    except Exception:
        pass

    # 2) PowerShell
    try:
        command = [
            "powershell",
            "-Command",
            "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"
        ]
        output = subprocess.check_output(
            command,
            stdin=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=2.5
        ).strip()

        vendor = parse_output(output)
        if vendor:
            with _GPU_VENDOR_LOCK:
                _GPU_VENDOR_CACHE = vendor
                _GPU_VENDOR_TS = now
            return vendor

    except subprocess.TimeoutExpired:
        pass
    except Exception:
        pass

    # fallback: стабильно возвращаем CPU
    with _GPU_VENDOR_LOCK:
        _GPU_VENDOR_CACHE = "CPU"
        _GPU_VENDOR_TS = now
    return "CPU"


def get_cuda_devices():
    if check_gpu_provider() != "NVIDIA":
        return []

    try:
        output = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=index,name",
                "--format=csv,noheader",
            ],
            stdin=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=2.5,
        ).strip()

        devices = []
        for line in (output or "").splitlines():
            raw = str(line or "").strip()
            if not raw:
                continue
            index_part = raw.split(",", 1)[0].strip()
            if index_part.isdigit():
                devices.append(f"cuda:{index_part}")
        return devices
    except Exception as e:
        logger.info(f"Не удалось определить CUDA устройства через nvidia-smi: {e}")
        return []


def get_gpu_name_by_id(device_id):
    if not isinstance(device_id, str) or not device_id.startswith("cuda:"):
        return None

    try:
        match = re.match(r"cuda:(\d+)", device_id)
        if not match:
            return None
        index = int(match.group(1))

        output = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=index,name",
                "--format=csv,noheader",
            ],
            stdin=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=2.5,
        ).strip()

        for line in (output or "").splitlines():
            raw = str(line or "").strip()
            if not raw or "," not in raw:
                continue
            idx_raw, name_raw = raw.split(",", 1)
            if idx_raw.strip().isdigit() and int(idx_raw.strip()) == index:
                name = name_raw.strip()
                return name or None
        return None
    except Exception as e:
        logger.info(f"Ошибка при получении имени GPU через nvidia-smi для {device_id}: {e}")
        return None


def recommended_backend() -> Backend:
    return vendor_to_backend(check_gpu_provider())
