"""
Локальный лаунчер для PyCharm (в .gitignore).
1. Собирает fast-билд (build.py)
2. Если requirements.txt изменился — запускает uv pip install
3. Запускает игру
"""
import hashlib
import json
import os
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

OUTPUT_DIR = Path(env.get("BUILD_OUTPUT_DIR", str(PROJECT_DIR / "build_output")))

# Путь к python игры — можно переопределить через LAUNCH_PYTHON в build.env
_default_python = str(OUTPUT_DIR / "libs" / "python" / "python.exe")
GAME_PYTHON = Path(env.get("LAUNCH_PYTHON", _default_python))

# ACTIVE_BACKEND / BACKEND / GPU_VENDOR can be set in build.env or env vars.


def resolve_backend() -> str:
    raw = (
        env.get("ACTIVE_BACKEND")
        or env.get("BACKEND")
        or env.get("GPU_VENDOR")
        or os.environ.get("ACTIVE_BACKEND")
        or os.environ.get("BACKEND")
        or os.environ.get("GPU_VENDOR")
        or ""
    ).strip().upper()

    mapping = {
        "CUDA": "CUDA",
        "NVIDIA": "CUDA",
        "ONNX": "ONNX",
        "AMD": "ONNX",
        "CPU": "ONNX",
        "DIRECTML": "ONNX",
    }
    return mapping.get(raw, "ONNX")


ACTIVE_BACKEND = resolve_backend()

REQ_FILE = OUTPUT_DIR / "requirements.txt"
HASH_FILE = OUTPUT_DIR / ".req_hash"
SETTINGS_FILE = OUTPUT_DIR / "Settings" / "settings.json"
BACKEND_MARKER = OUTPUT_DIR / "Lib" / ".backend"
LIB_DIR = OUTPUT_DIR / "Lib"


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
    return any(
        not candidate.exists()
        for candidate in (
            LIB_DIR / "pydantic",
            LIB_DIR / "pydantic_core",
        )
    )


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


def run(cmd: list, cwd: Path = None):
    print(f"\n>>> {' '.join(str(c) for c in cmd)}")
    env_vars = os.environ.copy()
    env_vars.pop("VIRTUAL_ENV", None)
    env_vars["NEUROMITA_ACTIVE_BACKEND"] = ACTIVE_BACKEND
    existing_pythonpath = env_vars.get("PYTHONPATH", "").strip()
    env_vars["PYTHONPATH"] = str(LIB_DIR) if not existing_pythonpath else str(LIB_DIR) + os.pathsep + existing_pythonpath
    result = subprocess.run(cmd, cwd=cwd, env=env_vars)
    if result.returncode != 0:
        print(f"Ошибка (код {result.returncode}), прерываю.")
        sys.exit(result.returncode)


if __name__ == "__main__":
    # 1. Сборка
    print("=" * 50)
    print("Шаг 1: сборка (fast)")
    print("=" * 50)
    run([sys.executable, str(PROJECT_DIR / "build.py")])

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
