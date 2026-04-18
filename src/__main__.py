### main.py

import os
import sys


from dotenv import load_dotenv
ENV_FILENAME = "features.env" 
loaded = load_dotenv(dotenv_path=ENV_FILENAME)

backend = os.environ.get("NEUROMITA_BACKEND", "cpu")
bootstrap_members = ["core"]

current_file = os.path.abspath(__file__)
if current_file.lower().endswith(".pyz"):
    base_dir = os.path.dirname(current_file)
else:
    base_dir = os.path.dirname(os.path.dirname(current_file))

for member in bootstrap_members:
    sp = os.path.join(base_dir, "packages", member, ".lib", "site-packages")
    if os.path.isdir(sp) and sp not in sys.path:
        sys.path.insert(0, sp)



import pydantic.fields
import uvicorn
import re

from main_logger import logger
from _version import __version__
def create_startup_banner(title: str, version: str) -> str:
    version_info = f"Version {version}"
    
    padding = 6
    
    content_width = max(len(title), len(version_info)) + padding
    
    if content_width % 2 != 0:
        content_width += 1
        
    top_border = f"╔{'═' * content_width}╗"
    bottom_border = f"╚{'═' * content_width}╝"
    
    empty_line = f"║{' ' * content_width}║"
    title_line = f"║{title.center(content_width)}║"
    version_line = f"║{version_info.center(content_width)}║"
    
    # Собираем и возвращаем финальный баннер
    return (
        f"{top_border}\n"
        f"{empty_line}\n"
        f"{title_line}\n"
        f"{version_line}\n"
        f"{empty_line}\n"
        f"{bottom_border}"
    )


banner = create_startup_banner("NeuroMita", __version__)
logger.success(f"\n\n{banner}\n\n")



os.environ["WHISPER_ONNX_DEBUG"]="1"
if loaded:
    logger.notify(f"Переменные окружения успешно загружены из файла: {ENV_FILENAME}")
else:
    logger.notify(f"Файл окружения '{ENV_FILENAME}' не найден по пути: {ENV_FILENAME}. Используются системные переменные или значения по умолчанию.")

# region Для исправления проблем с импортом динамично подгружаемых пакетов:
import timeit
import pickletools
import logging.config
import fileinput
from win32 import win32file
import pyworld
import cProfile
import filecmp
import soxr

try:
    import google.api_core
    import google.auth
    from google.cloud import storage
    from google.protobuf import empty_pb2
    import google.protobuf.wrappers_pb2
except Exception as e:
    logger.warning(f"{e}")
import xml.dom


import modulefinder
import sunau
import xml.etree
import xml.etree.ElementTree
import os

# os.environ["TEST_AS_AMD"] = "TRUE"

if os.environ.get("VERBOSE_TRITON_LOGS", "0") == "1":
    os.environ["TORCH_LOGS"] = "+dynamo"
    os.environ["TORCHDYNAMO_VERBOSE"] = "1"
    
os.environ.setdefault("UV_LINK_MODE", "hardlink")

#region Переменные для путей
import json
try:
    import tomllib
except ImportError:
    import tomli as tomllib



os.environ["NEUROMITA_BASE_DIR"] = base_dir
os.environ.setdefault("NEUROMITA_PROMPTS_DIR", os.path.join(base_dir, "Prompts"))
os.environ.setdefault("NEUROMITA_HISTORIES_DIR", os.path.join(base_dir, "Histories"))
os.environ.setdefault("NEUROMITA_MODELS_DIR", os.path.join(base_dir, "Models"))
os.environ.setdefault("NEUROMITA_CHECKPOINTS_DIR", os.path.join(base_dir, "checkpoints"))
local_python = os.path.join(base_dir, "libs", "python", "python.exe")
os.environ.setdefault("NEUROMITA_PYTHON", local_python if os.path.exists(local_python) else sys.executable)
os.environ.setdefault("NEUROMITA_BACKEND", "cpu")

pyproject = os.path.join(base_dir, "pyproject.toml")
extras_map = {}
if os.path.exists(pyproject):
    with open(pyproject, "rb") as f:
        data = tomllib.load(f)
    extras_map = data.get("tool", {}).get("neuromita", {}).get("extras", {})

state_path = os.path.join(base_dir, ".uv-state.json")
active = []
if os.path.exists(state_path):
    with open(state_path, "r", encoding="utf-8") as f:
        active = json.load(f).get("extras", [])

def _order_key(extra_name):
    if extra_name == "core":
        return (0, extra_name)
    if extra_name.startswith("backend-"):
        return (1, extra_name)
    if extra_name.startswith("rvc-"):
        return (2, extra_name)
    if extra_name.startswith("asr-"):
        return (3, extra_name)
    return (4, extra_name)

for extra in sorted(active, key=_order_key):
    info = extras_map.get(extra)
    if not info:
        continue
    sp = os.path.join(base_dir, info["target"], ".lib", "site-packages")
    if os.path.isdir(sp) and sp not in sys.path:
        sys.path.insert(0, sp)
#endregion


logger.info(f"Базовая директория: {os.environ['NEUROMITA_BASE_DIR']}")
logger.info(f"Prompts: {os.environ['NEUROMITA_PROMPTS_DIR']}")
logger.info(f"Histories: {os.environ['NEUROMITA_HISTORIES_DIR']}")
logger.info(f"Checkpoints: {os.environ['NEUROMITA_CHECKPOINTS_DIR']}")
logger.info(f"Python: {os.environ['NEUROMITA_PYTHON']}")
logger.info(f"Активные uv extras: {active}")

try:
    from updater import check_for_updates as _check_for_updates
    _check_for_updates(base_dir=base_dir, logger=logger)
except Exception as _upd_err:
    logger.warning(f"Update check failed: {_upd_err}")

from utils.patches import apply_runtime_patches
apply_runtime_patches(base_dir, active, extras_map)

import onnxruntime

from PyQt6.QtWidgets import QApplication


def ensure_project_root():
    project_root_file = os.path.join(os.environ["NEUROMITA_BASE_DIR"], '.project-root')
    
    if not os.path.exists(project_root_file):
        open(project_root_file, 'w').close()
        logger.info(f"Файл '{project_root_file}' создан.")

ensure_project_root()



# Установка

# Теперь делаю файлом с папкой, так как антивирусы ругаются)
#pyinstaller --name NeuroMita --noconfirm --console --add-data "Prompts/*;Prompts" --add-data "Prompts/**/*;Prompts" Main.py

# Скакать между версиями g4f
#pip install --upgrade g4f==0.4.7.7
#pip install --upgrade g4f==0.4.8.3
#pip install --upgrade g4f

#"""
#Тестово, потом надо будет вот это вернуть
#pyinstaller --name NeuroMita --noconfirm --add-data "Prompts/*;Prompts" --add-data "%USERPROFILE%\AppData\Local\Programs\Python\Python313\Lib\site-packages\emoji\unicode_codes\emoji.json;emoji\unicode_codes  --add-data "Prompts/**/*;Prompts" Main.py
#"""



# Старый вариант
#pyinstaller --onefile --name NeuroMita --add-data "Prompts/*;Prompts" --add-data "Prompts/**/*;Prompts" Main.py

# Не забудь рядом папку промптов и ffmpeg

import threading

from ui.windows.main_view import ChatGUI
from controllers.main_controller import MainController
from core.events import get_event_bus
from main_logger import logger
from PyQt6.QtWidgets import QApplication
import sys

if __name__ == "__main__":
    logger.success("Функция main() запущена")
    try:
        app = QApplication(sys.argv)
        logger.info("QApplication создан")

        if sys.platform == 'win32':
            import ctypes
            myappid = 'mycompany.myproduct.subproduct.version' 
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

        # Создаем пустой объект для контроллера
        logger.info("Создаю MainController...")
        controller = MainController(None)
        logger.info("MainController создан")

        # Инициализация сборщика данных для дообучения
        try:
            from managers.finetune_collector import FineTuneCollector
            FineTuneCollector.instance = FineTuneCollector()
            logger.info("FineTuneCollector инициализирован")
        except Exception as _ft_init_err:
            logger.warning(f"FineTuneCollector не инициализирован: {_ft_init_err}")
    
        logger.info("Создаю ChatGUI...")
        main_win = ChatGUI(controller.settings)  # Передаем controller  settings
        logger.info("ChatGUI создан")
        
        # Обновляем ссылку на реальный view в контроллере
        controller.update_view(main_win)

        main_win.load_chat_history()
        
        
        logger.info("Показываю главное окно...")
        main_win.show()
        logger.info("Запускаю app.exec()...")

        
        # При завершении приложения останавливаем систему событий
        app.aboutToQuit.connect(lambda: get_event_bus().shutdown())
        
        sys.exit(app.exec())
    except Exception as e:
        logger.error(f"Ошибка в main(): {e}", exc_info=True)
        raise
