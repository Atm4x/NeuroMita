"""
Post-hoc image description backfill.

Generates text descriptions for history images that don't have one yet,
using the configured vision provider (IMAGE_DESCRIPTION_PROVIDER).
Mirrors the "reindex missing embeddings" flow (character_settings/logic.run_reindexing_all):
a TaskWorker does the work off the UI thread, a QProgressDialog tracks progress.

Descriptions are written to meta_data.image_descriptions[<detail>] in world.db,
the same field the manual editor in db_viewer writes to (as "manual").
"""
from __future__ import annotations

import json
import os
import sqlite3

from PyQt6.QtWidgets import QProgressDialog, QMessageBox
from PyQt6.QtCore import Qt

from main_logger import logger
from utils import getTranslationVariant as _
from ui.task_worker import TaskWorker
from handlers.image_description_handler import DETAIL_LEVELS, DEFAULT_DETAIL


def _world_db_path() -> str:
    histories_dir = os.environ.get(
        "NEUROMITA_HISTORIES_DIR", os.path.join(os.getcwd(), "Histories")
    )
    return os.path.join(histories_dir, "world.db")


def _normalize_detail(raw) -> str:
    """Map the (possibly localized) detail setting to a canonical key."""
    lvl = str(raw or DEFAULT_DETAIL).strip().lower()
    return lvl if lvl in DETAIL_LEVELS else DEFAULT_DETAIL


def _message_has_description(meta: dict) -> bool:
    dd = meta.get("image_descriptions")
    if isinstance(dd, dict) and any(str(v or "").strip() for v in dd.values()):
        return True
    legacy = meta.get("image_description")
    return isinstance(legacy, str) and bool(legacy.strip())


def _collect_image_paths(meta: dict) -> list[str]:
    paths: list[str] = []
    for part in meta.get("multimodal_parts") or []:
        if not isinstance(part, dict):
            continue
        if part.get("type") not in ("image_url", "image"):
            continue
        url = (part.get("image_url") or {}).get("url", "")
        if url and not str(url).startswith("data:") and not str(url).startswith("http"):
            paths.append(str(url))
    return paths


def _read_image_bytes(path: str) -> bytes | None:
    try:
        if not os.path.exists(path):
            logger.warning(f"[ImageBackfill] file not found: {path}")
            return None
        with open(path, "rb") as f:
            return f.read()
    except Exception as e:
        logger.warning(f"[ImageBackfill] failed to read {path}: {e}")
        return None


class ImageDescriptionBackfillWorker(TaskWorker):
    """Describe every multimodal history message that lacks a description."""

    def __init__(self, settings):
        def _do(*, progress_callback=None):
            from handlers.chat_handler import ChatModel
            from handlers.image_description_handler import ImageDescriptionHandler

            db_path = _world_db_path()
            if not os.path.exists(db_path):
                return {"described": 0, "total": 0, "failed": 0}

            detail = _normalize_detail(settings.get("IMAGE_DESCRIPTION_DETAIL", DEFAULT_DETAIL))

            handler = ImageDescriptionHandler(model=ChatModel(settings), settings=settings)

            conn = sqlite3.connect(db_path)
            try:
                cur = conn.cursor()
                cur.execute(
                    """SELECT id, meta_data FROM history
                       WHERE (meta_data LIKE '%"multimodal_parts"%'
                              OR meta_data LIKE '%"is_multimodal_list"%')
                         AND is_deleted = 0
                       ORDER BY timestamp DESC
                       LIMIT 5000"""
                )
                candidates: list[tuple[int, dict, list[str]]] = []
                for row_id, meta_raw in cur.fetchall():
                    try:
                        meta = json.loads(meta_raw) if meta_raw else {}
                    except Exception:
                        continue
                    if _message_has_description(meta):
                        continue
                    paths = _collect_image_paths(meta)
                    if paths:
                        candidates.append((int(row_id), meta, paths))

                total = len(candidates)
                described = 0
                failed = 0

                if progress_callback:
                    progress_callback(0, max(total, 1))

                for i, (row_id, meta, paths) in enumerate(candidates):
                    images: list[bytes] = []
                    for p in paths:
                        b = _read_image_bytes(p)
                        if b is not None:
                            images.append(b)

                    desc_text = ""
                    if images:
                        try:
                            if len(images) > 1:
                                desc_text = handler.describe_sequence(images)
                            else:
                                parts = handler.describe(images)
                                desc_text = "\n".join(parts) if parts else ""
                        except Exception as e:
                            logger.warning(f"[ImageBackfill] describe failed for id={row_id}: {e}")

                    desc_text = (desc_text or "").strip()
                    # The handler returns "[... unavailable]" placeholders on failure — don't store those.
                    if desc_text and not desc_text.startswith("["):
                        dd = meta.get("image_descriptions")
                        if not isinstance(dd, dict):
                            dd = {}
                        dd[detail] = desc_text
                        meta["image_descriptions"] = dd
                        try:
                            cur.execute(
                                "UPDATE history SET meta_data = ? WHERE id = ?",
                                (json.dumps(meta, ensure_ascii=False), row_id),
                            )
                            conn.commit()
                            described += 1
                        except Exception as e:
                            logger.warning(f"[ImageBackfill] DB update failed id={row_id}: {e}")
                            failed += 1
                    else:
                        failed += 1

                    if progress_callback:
                        progress_callback(i + 1, max(total, 1))

                return {"described": described, "total": total, "failed": failed}
            finally:
                conn.close()

        super().__init__(_do, use_progress=True)


def run_image_description_backfill(gui) -> None:
    """Entry point wired to the 'Describe missing' settings button."""
    settings = getattr(gui, "settings", None)
    if settings is None:
        QMessageBox.warning(gui, _("Ошибка", "Error"),
                            _("Настройки недоступны.", "Settings unavailable."))
        return

    reply = QMessageBox.question(
        gui,
        _("Подтверждение", "Confirmation"),
        _(
            "Сгенерировать описания для всех изображений в истории, у которых их ещё нет?\n\n"
            "Используется vision-провайдер из настроек «Описание изображений».\n"
            "Операция может занять время и потратить токены.",
            "Generate descriptions for all history images that don't have one yet?\n\n"
            "Uses the vision provider from the “Image Description” settings.\n"
            "This may take time and consume tokens."
        ),
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )
    if reply != QMessageBox.StandardButton.Yes:
        return

    gui._img_backfill_worker = ImageDescriptionBackfillWorker(settings)
    gui._img_backfill_cancelled = False

    progress = QProgressDialog(
        _("Описание изображений...", "Describing images..."),
        _("Отмена", "Cancel"),
        0, 100, gui,
    )
    progress.setWindowModality(Qt.WindowModality.WindowModal)
    progress.setMinimumDuration(0)
    progress.setValue(0)
    progress.setAutoClose(False)
    progress.setAutoReset(False)

    def on_progress(curr, total):
        try:
            t = int(total or 0)
            c = int(curr or 0)
            progress.setRange(0, max(t, 1))
            progress.setValue(min(c, max(t, 1)))
            progress.setLabelText(
                _("Обработано: {c} / {t}", "Processed: {c} / {t}").format(c=c, t=t if t else "?")
            )
        except Exception:
            pass

    def on_finished(result):
        if getattr(gui, "_img_backfill_cancelled", False):
            gui._img_backfill_worker = None
            gui._img_backfill_cancelled = False
            return
        progress.close()
        result = result or {}
        described = int(result.get("described", 0))
        total = int(result.get("total", 0))
        failed = int(result.get("failed", 0))
        if total == 0:
            msg = _("Все изображения уже описаны.", "All images already have descriptions.")
        else:
            msg = _(
                "Описано: {d} из {t}. Не удалось: {f}.",
                "Described: {d} of {t}. Failed: {f}.",
            ).format(d=described, t=total, f=failed)
        QMessageBox.information(gui, _("Готово", "Done"), msg)
        gui._img_backfill_worker = None
        gui._img_backfill_cancelled = False

    def on_error(err_msg):
        if getattr(gui, "_img_backfill_cancelled", False):
            gui._img_backfill_worker = None
            gui._img_backfill_cancelled = False
            return
        progress.close()
        QMessageBox.critical(gui, _("Ошибка", "Error"), err_msg)
        gui._img_backfill_worker = None
        gui._img_backfill_cancelled = False

    def on_cancel():
        gui._img_backfill_cancelled = True
        try:
            gui._img_backfill_worker.requestInterruption()
        except Exception:
            pass
        progress.close()

    def on_cancelled():
        gui._img_backfill_worker = None
        gui._img_backfill_cancelled = False

    gui._img_backfill_worker.progress_signal.connect(on_progress)
    gui._img_backfill_worker.finished_signal.connect(on_finished)
    gui._img_backfill_worker.error_signal.connect(on_error)
    gui._img_backfill_worker.cancelled_signal.connect(on_cancelled)
    progress.canceled.connect(on_cancel)

    progress.show()
    gui._img_backfill_worker.start()
