"""
Локальный лаунчер для PyCharm.
1. Собирает билд через build.py.
2. Запускает новый uv-workspace скрипт для выбранного backend.
"""
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).parent


def load_env(env_path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not env_path.exists():
        return env
    with env_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip()
    return env


def run(cmd: list[str], cwd: Path | None = None) -> int:
    print(f"\n>>> {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, cwd=cwd)
    return result.returncode


def fail(code: int) -> None:
    print(f"Ошибка (код {code}), прерываю.")
    sys.exit(code)


if __name__ == "__main__":
    env = load_env(PROJECT_DIR / "build.env")
    output_dir = Path(env.get("BUILD_OUTPUT_DIR", str(PROJECT_DIR / "build_output")))
    backend = env.get("NEUROMITA_BACKEND") or env.get("GPU_VENDOR", "cpu")
    backend = backend.strip().lower()
    if backend in {"none", "default"}:
        backend = "cpu"

    scripts = {
        "nvidia": "run_nvidia.cmd",
        "amd": "run_amd.cmd",
        "cpu": "run_cpu.cmd",
    }
    script_name = scripts.get(backend)
    if script_name is None:
        print(f"Неизвестный backend {backend!r}. Используй nvidia, amd или cpu.")
        sys.exit(2)

    print("=" * 50)
    print("Шаг 1: сборка")
    print("=" * 50)
    code = run([sys.executable, str(PROJECT_DIR / "build.py")], cwd=PROJECT_DIR)
    if code != 0:
        fail(code)

    script_path = output_dir / script_name
    if not script_path.exists():
        print(f"Скрипт запуска не найден: {script_path}")
        sys.exit(2)

    print("=" * 50)
    print(f"Шаг 2: запуск backend={backend}")
    print("=" * 50)
    while True:
        code = run(["cmd", "/c", str(script_path)], cwd=output_dir)
        if code == 42:
            print("\nОбновление применено, перезапускаю...")
            continue
        if code != 0:
            fail(code)
        break
