from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication, QPushButton

from controllers.gui import rag_memory_controller
from controllers.gui.rag_install_view_model import RagInstallViewModel
from controllers.gui.settings_data_prefetch import RAG_CE_STATUS, RAG_EMBED_STATUS
from ui.gui_templates import create_button_group


def test_reranker_refresh_button_uses_install_view_model_and_bypasses_cached_status():
    app = QApplication.instance() or QApplication([])
    host = SimpleNamespace(
        **{
            name: lambda *_args: True
            for name in (
                "validate_positive_integer",
                "validate_positive_integer_or_zero",
                "validate_float_0_to_1",
                "validate_float_positive",
                "validate_float_positive_or_zero",
            )
        }
    )
    cache = Mock()
    cache.get.return_value = {"backend": "stale"}
    statuses = {
        RAG_EMBED_STATUS: {"backend": "Ready", "index": "Up to date"},
        RAG_CE_STATUS: {
            "backend": "Ready",
            "model": "BAAI/bge-reranker-v2-m3",
            "loaded": "Loaded in memory",
        },
    }

    def request(_target, key, _worker, apply, **_kwargs):
        apply(statuses[key])

    cache.request.side_effect = request
    view_model = RagInstallViewModel(settings_data=cache)
    try:
        with (
            patch("ui.gui_templates.create_settings_section") as create_section,
            patch.object(rag_memory_controller, "_attach_embed_downloader"),
            patch.object(rag_memory_controller, "_attach_ce_downloader"),
        ):
            rag_memory_controller.build_rag_section(
                host,
                None,
                [],
                rag_preset_view_model=object(),
                embed_provider_view_model=object(),
                rag_install_view_model=view_model,
            )
        config = create_section.call_args.args[3]
        reranker_start = next(
            i for i, item in enumerate(config)
            if item.get("key") == "RAG_CROSS_ENCODER_ENABLED"
        )
        buttons = next(
            item["buttons"] for item in config[reranker_start:]
            if item.get("type") == "button_group"
        )

        # Execute directly first so a regression raises instead of reaching Qt's excepthook.
        buttons[0]["command"]()
        frame = create_button_group(host, None, buttons)
        try:
            frame.findChild(QPushButton).click()
            app.processEvents()
        finally:
            frame.deleteLater()

        assert [call.args[1] for call in cache.request.call_args_list] == [
            RAG_EMBED_STATUS, RAG_CE_STATUS, RAG_EMBED_STATUS, RAG_CE_STATUS,
        ]
        assert all(call.kwargs["force"] is True for call in cache.request.call_args_list)
        assert view_model.state.embeddings.backend == "Ready"
        assert view_model.state.embeddings.index == "Up to date"
        assert view_model.state.reranker.model == "BAAI/bge-reranker-v2-m3"
        assert view_model.state.reranker.loaded == "Loaded in memory"
    finally:
        view_model.close()
