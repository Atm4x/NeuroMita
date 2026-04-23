from __future__ import annotations

import os

from PyQt6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from core.backends import Backend
from core.events import Events
from main_logger import logger
from managers.backend_manager import BackendManager
from managers.settings_manager import CollapsibleSection, SettingsManager
from utils import getTranslationVariant as _
from utils.uv_sync import UvSync


def setup_package_management_controls(gui, parent_layout):
    section = CollapsibleSection(_("Управление пакетами", "Package Management"), gui, icon_name="fa6s.box-open")
    parent_layout.addWidget(section)

    info_block = QWidget(section.content)
    info_layout = QVBoxLayout(info_block)
    info_layout.setContentsMargins(0, 0, 0, 0)
    info_layout.setSpacing(4)

    active_backend_label = QLabel()
    detected_backend_label = QLabel()
    libs_path_label = QLabel(os.path.abspath("Lib"))
    libs_path_label.setObjectName("Subtle")
    libs_path_label.setWordWrap(True)

    info_layout.addWidget(active_backend_label)
    info_layout.addWidget(detected_backend_label)
    info_layout.addWidget(QLabel(_("Каталог пакетов:", "Packages directory:")))
    info_layout.addWidget(libs_path_label)
    restart_note = QLabel(
        _("После смены backend лучше перезапустить приложение.", "Restarting the app after switching backend is recommended.")
    )
    restart_note.setWordWrap(True)
    restart_note.setObjectName("Subtle")
    info_layout.addWidget(restart_note)
    section.add_widget(info_block)

    cache_row = QWidget(section.content)
    cache_layout = QHBoxLayout(cache_row)
    cache_layout.setContentsMargins(0, 0, 0, 0)
    cache_layout.setSpacing(8)

    cache_checkbox = QCheckBox(_("Использовать кеш пакетов", "Use package cache"))
    cache_checkbox.setChecked(bool(SettingsManager.get("PKG_USE_CACHE", False)))
    cache_checkbox.toggled.connect(lambda checked: SettingsManager.set("PKG_USE_CACHE", bool(checked)))
    cache_layout.addWidget(cache_checkbox)
    cache_layout.addStretch()
    section.add_widget(cache_row)

    buttons_row = QWidget(section.content)
    buttons_layout = QVBoxLayout(buttons_row)
    buttons_layout.setContentsMargins(0, 0, 0, 0)
    buttons_layout.setSpacing(6)

    row_top = QHBoxLayout()
    row_bottom = QHBoxLayout()
    row_top.setSpacing(6)
    row_bottom.setSpacing(6)

    btn_activate_cuda = QPushButton(_("Активировать CUDA", "Activate CUDA"))
    btn_activate_onnx = QPushButton(_("Активировать ONNX", "Activate ONNX"))
    btn_reinstall = QPushButton(_("Переустановить active backend", "Reinstall active backend"))
    btn_uv_sync = QPushButton(_("Синхронизировать через uv", "Sync with uv"))
    btn_refresh = QPushButton(_("Обновить статус", "Refresh status"))

    for button in (btn_activate_cuda, btn_activate_onnx, btn_reinstall, btn_uv_sync, btn_refresh):
        button.setObjectName("SecondaryButton")

    row_top.addWidget(btn_activate_cuda)
    row_top.addWidget(btn_activate_onnx)
    row_bottom.addWidget(btn_reinstall)
    row_bottom.addWidget(btn_uv_sync)
    row_bottom.addWidget(btn_refresh)
    buttons_layout.addLayout(row_top)
    buttons_layout.addLayout(row_bottom)
    section.add_widget(buttons_row)

    def refresh_labels():
        active_backend = BackendManager.active().value
        detected_backend = BackendManager.detect().value
        active_backend_label.setText(
            _("Активный backend: ", "Active backend: ") + active_backend
        )
        detected_backend_label.setText(
            _("Обнаруженный backend: ", "Detected backend: ") + detected_backend
        )
        btn_activate_cuda.setEnabled(active_backend != Backend.CUDA.value)
        btn_activate_onnx.setEnabled(active_backend != Backend.ONNX.value)

    def _emit_install_task(title: str, initial_status: str, runner):
        gui.event_bus.emit(
            Events.Install.RUN_WITH_UI,
            {
                "kind": "packages",
                "item_id": "packages",
                "task_id": f"packages:{title.lower().replace(' ', '_')}",
                "title": title,
                "initial_status": initial_status,
                "timeout_sec": 3600.0,
                "meta": {"kind": "packages", "item_id": "packages"},
                "runner": runner,
            },
        )

    def activate_backend(target: Backend):
        _emit_install_task(
            _("Переключение backend", "Switching backend"),
            _("Подготовка backend...", "Preparing backend..."),
            lambda *args, **kwargs: BackendManager.build_activate_plan(target),
        )

    def reinstall_active_backend():
        _emit_install_task(
            _("Переустановка backend", "Reinstalling backend"),
            _("Подготовка переустановки...", "Preparing reinstall..."),
            lambda *args, **kwargs: BackendManager.build_install_plan(BackendManager.active(), force=True),
        )

    def run_uv_sync():
        def runner(*args, **kwargs):
            callbacks = kwargs.get("callbacks")
            use_cache = bool(SettingsManager.get("PKG_USE_CACHE", False))
            desired_specs = BackendManager.desired_specs(BackendManager.active())
            return UvSync().apply(desired_specs, use_cache=use_cache, callbacks=callbacks)

        _emit_install_task(
            _("uv pip sync", "uv pip sync"),
            _("Подготовка синхронизации...", "Preparing sync..."),
            runner,
        )

    btn_activate_cuda.clicked.connect(lambda: activate_backend(Backend.CUDA))
    btn_activate_onnx.clicked.connect(lambda: activate_backend(Backend.ONNX))
    btn_reinstall.clicked.connect(reinstall_active_backend)
    btn_uv_sync.clicked.connect(run_uv_sync)
    btn_refresh.clicked.connect(refresh_labels)

    try:
        refresh_labels()
    except Exception as ex:
        logger.warning(f"Failed to initialize package management labels: {ex}")
