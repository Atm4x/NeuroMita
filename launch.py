"""
Локальный лаунчер для PyCharm (в .gitignore).
1. Собирает fast-билд (build.py)
2. Если requirements.txt изменился — запускает uv pip install
3. Запускает игру
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).parent


def load_env(env_path: Path) -> dict:
    env = {}
    if not env_path.exists():
        return env
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip()
    return env


env = load_env(PROJECT_DIR / "build.env")
BUILD_MODE = (env.get("BUILD_MODE", "fast") or "fast").strip().lower()

OUTPUT_DIR = Path(env.get("BUILD_OUTPUT_DIR", str(PROJECT_DIR / "build_output")))

# Путь к python игры — можно переопределить через LAUNCH_PYTHON в build.env
_default_python = str(OUTPUT_DIR / "libs" / "python" / "python.exe")
GAME_PYTHON = Path(env.get("LAUNCH_PYTHON", _default_python))

# ACTIVE_BACKEND / BACKEND / NEUROMITA_BACKEND / GPU_VENDOR can be set in build.env or env vars.


def detect_backend() -> str:
    try:
        result = subprocess.run(
            ["nvidia-smi", "-L"],
            capture_output=True,
            text=True,
            timeout=2.0,
        )
        if result.returncode == 0 and "NVIDIA" in (result.stdout or "").upper():
            return "CUDA"
    except Exception:
        pass

    try:
        result = subprocess.run(
            [
                "powershell",
                "-Command",
                "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name",
            ],
            capture_output=True,
            text=True,
            timeout=2.5,
        )
        output = (result.stdout or "").upper()
        if "NVIDIA" in output:
            return "CUDA"
        if "AMD" in output or "RADEON" in output:
            return "ONNX"
    except Exception:
        pass

    return "ONNX"


def resolve_backend() -> str:
    raw = (
        env.get("ACTIVE_BACKEND")
        or env.get("BACKEND")
        or env.get("NEUROMITA_BACKEND")
        or env.get("GPU_VENDOR")
        or os.environ.get("ACTIVE_BACKEND")
        or os.environ.get("BACKEND")
        or os.environ.get("NEUROMITA_BACKEND")
        or os.environ.get("GPU_VENDOR")
        or ""
    ).strip().upper()

    mapping = {
        "CUDA": "CUDA",
        "NVIDIA": "CUDA",
        "NVIDIA-SMI": "CUDA",
        "ONNX": "ONNX",
        "AMD": "ONNX",
        "CPU": "ONNX",
        "DIRECTML": "ONNX",
    }
    if raw:
        return mapping.get(raw, detect_backend())
    return detect_backend()


ACTIVE_BACKEND = resolve_backend()
BUILD_MODE_FOR_BUILD = "full" if BUILD_MODE == "full_delete" else BUILD_MODE

REQ_FILE = OUTPUT_DIR / "requirements.txt"
HASH_FILE = OUTPUT_DIR / ".req_hash"
SETTINGS_FILE = OUTPUT_DIR / "Settings" / "settings.json"
BACKEND_MARKER = OUTPUT_DIR / "Lib" / ".backend"
LIB_DIR = OUTPUT_DIR / "Lib"
BOOTSTRAP_IMPORTS = (
    "pydantic",
    "pydantic_core",
    "typing_extensions",
    "annotated_types",
    "dotenv",
    "uvicorn",
)


def file_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def requirements_changed() -> bool:
    if not REQ_FILE.exists():
        return False
    current = file_hash(REQ_FILE)
    if HASH_FILE.exists() and HASH_FILE.read_text().strip() == current:
        return False
    return True


def bootstrap_deps_missing() -> bool:
    if not GAME_PYTHON.exists():
        return True

    env_vars = os.environ.copy()
    env_vars.pop("VIRTUAL_ENV", None)
    existing_pythonpath = env_vars.get("PYTHONPATH", "").strip()
    env_vars["PYTHONPATH"] = str(LIB_DIR) if not existing_pythonpath else str(LIB_DIR) + os.pathsep + existing_pythonpath

    probe = (
        "import importlib.util, json; "
        f"mods={list(BOOTSTRAP_IMPORTS)!r}; "
        "missing=[m for m in mods if importlib.util.find_spec(m) is None]; "
        "print(json.dumps(missing, ensure_ascii=False))"
    )
    result = subprocess.run(
        [str(GAME_PYTHON), "-c", probe],
        cwd=OUTPUT_DIR,
        env=env_vars,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("Не удалось проверить bootstrap-зависимости, считаю их отсутствующими.")
        if result.stderr:
            print(result.stderr.strip())
        return True

    missing_raw = (result.stdout or "").strip()
    try:
        missing = json.loads(missing_raw) if missing_raw else []
    except Exception:
        print(f"Не удалось разобрать результат проверки bootstrap-зависимостей: {missing_raw}")
        return True

    if missing:
        print(f"Отсутствуют bootstrap-зависимости: {', '.join(str(item) for item in missing)}")
        return True
    return False


def save_hash():
    HASH_FILE.write_text(file_hash(REQ_FILE))


def resolve_uv_executable() -> Path | None:
    direct_uv = OUTPUT_DIR / "libs" / "python" / "Scripts" / "uv.exe"
    if direct_uv.exists():
        return direct_uv

    cache_root = OUTPUT_DIR / "libs" / ".uv-cache"
    if cache_root.exists():
        found = sorted(cache_root.rglob("uv.exe"))
        if found:
            return found[-1]
    return None


def ensure_uv_command() -> list[str]:
    uv_exe = resolve_uv_executable()
    if uv_exe is not None:
        return [str(uv_exe)]

    print("uv.exe не найден, устанавливаю uv в embedded Python...")
    run([str(GAME_PYTHON), "-m", "pip", "install", "uv", "--no-cache-dir"], cwd=OUTPUT_DIR)

    uv_exe = resolve_uv_executable()
    if uv_exe is not None:
        return [str(uv_exe)]
    return [str(GAME_PYTHON), "-m", "uv"]


def ensure_launch_settings():
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)

    data = {}
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}

    if not isinstance(data, dict):
        data = {}

    data["ACTIVE_BACKEND"] = ACTIVE_BACKEND
    data.setdefault("PKG_USE_CACHE", False)
    SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")

    print(f"ACTIVE_BACKEND={ACTIVE_BACKEND} записан в {SETTINGS_FILE}")


def remove_output_dir_if_needed():
    if BUILD_MODE != "full_delete":
        return

    print("=" * 50)
    print("Шаг 0: полный сброс build output")
    print("=" * 50)
    print(f"Режим full_delete включён, удаляю папку: {OUTPUT_DIR}")

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
        print("Папка build output удалена.")
    else:
        print("Папка build output отсутствует, удалять нечего.")


def run(cmd: list, cwd: Path = None, extra_env: dict | None = None):
    print(f"\n>>> {' '.join(str(c) for c in cmd)}")
    env_vars = os.environ.copy()
    env_vars.pop("VIRTUAL_ENV", None)
    env_vars["NEUROMITA_ACTIVE_BACKEND"] = ACTIVE_BACKEND
    existing_pythonpath = env_vars.get("PYTHONPATH", "").strip()
    env_vars["PYTHONPATH"] = str(LIB_DIR) if not existing_pythonpath else str(LIB_DIR) + os.pathsep + existing_pythonpath
    if extra_env:
        env_vars.update(extra_env)
    result = subprocess.run(cmd, cwd=cwd, env=env_vars)
    if result.returncode != 0:
        print(f"Ошибка (код {result.returncode}), прерываю.")
        sys.exit(result.returncode)


if __name__ == "__main__":
    remove_output_dir_if_needed()

    # 1. Сборка
    print("=" * 50)
    print(f"Шаг 1: сборка ({BUILD_MODE_FOR_BUILD})")
    print("=" * 50)
    run(
        [sys.executable, str(PROJECT_DIR / "build.py")],
        extra_env={"BUILD_MODE": BUILD_MODE_FOR_BUILD},
    )

    # 2. Обновление базовых зависимостей если нужно
    if requirements_changed() or bootstrap_deps_missing():
        print("=" * 50)
        print("Шаг 2: requirements.txt изменился — обновляю базовые зависимости")
        print("=" * 50)
        print(f"Backend для проверки: {ACTIVE_BACKEND}")
        uv_cmd = ensure_uv_command()
        run(
            uv_cmd + [
                "pip",
                "install",
                "--python",
                str(GAME_PYTHON),
                "--target",
                str(LIB_DIR),
                "-r",
                str(REQ_FILE),
                "--no-cache-dir",
            ],
            cwd=OUTPUT_DIR,
        )
        save_hash()
    else:
        print("\nШаг 2: requirements.txt не изменился и bootstrap-зависимости на месте — пропускаю.")

    print("=" * 50)
    print("Шаг 2.1: фиксирую backend для запуска")
    print("=" * 50)
    ensure_launch_settings()

    # 3. Запуск игры (с перезапуском после автообновления)
    # Exit code 42 означает что updater применил обновление и нужен рестарт.
    game_cmd = [str(GAME_PYTHON), "NeuroMita.pyz"]
    while True:
        print("=" * 50)
        print("Шаг 3: запуск игры")
        print("=" * 50)
        print(f"\n>>> {' '.join(str(c) for c in game_cmd)}")
        game_env = os.environ.copy()
        game_env["NEUROMITA_ACTIVE_BACKEND"] = ACTIVE_BACKEND
        game_env["VIRTUAL_ENV"] = ""
        game_env["PYTHONPATH"] = str(LIB_DIR) + (os.pathsep + game_env["PYTHONPATH"] if game_env.get("PYTHONPATH") else "")
        result = subprocess.run(game_cmd, cwd=OUTPUT_DIR, env=game_env)
        if result.returncode == 42:
            print("\nОбновление применено, перезапускаю...")
        elif result.returncode != 0:
            print(f"Ошибка (код {result.returncode}), прерываю.")
            sys.exit(result.returncode)
        else:
            break
