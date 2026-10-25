"""MIME-тип картинки и data-URL в одном месте.

Раньше все точки приложения маркировали любые байты как ``image/jpeg``:
PNG из буфера обмена и вложений уезжал провайдеру под чужим типом. Gemini
сверяет mime с содержимым, поэтому такой запрос мог быть отбит или
обработан не так, как ожидалось.

Тип определяется по сигнатуре байтов — это единственный источник правды для
data-URL. Незнакомую сигнатуру не выдаём за JPEG молча: пишем один раз в лог
и оставляем разумный тип, чтобы UI умел отрисовать превью.
"""
from __future__ import annotations

import base64
import threading
from typing import Optional, Tuple

from main_logger import logger

PNG = "image/png"
JPEG = "image/jpeg"
WEBP = "image/webp"
GIF = "image/gif"
BMP = "image/bmp"
TIFF = "image/tiff"
AVIF = "image/avif"

DEFAULT_IMAGE_MIME = JPEG

_reported_unknown: set[str] = set()
_report_lock = threading.Lock()


def _report_unknown_signature(header: bytes) -> None:
    signature = header[:12].hex()
    with _report_lock:
        if signature in _reported_unknown:
            return
        _reported_unknown.add(signature)
    logger.warning(
        "[image_assets] Неизвестная сигнатура изображения (%s): тип не определён, "
        "отправляем как %s.",
        signature,
        DEFAULT_IMAGE_MIME,
    )


def detect_image_mime(data: bytes, *, fallback: str = DEFAULT_IMAGE_MIME) -> str:
    """MIME по сигнатуре байтов. Незнакомая сигнатура — ``fallback`` + лог."""
    if not data:
        return fallback
    header = bytes(data[:16])
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return PNG
    if header.startswith(b"\xff\xd8\xff"):
        return JPEG
    if header.startswith((b"GIF87a", b"GIF89a")):
        return GIF
    if header.startswith(b"BM"):
        return BMP
    if header.startswith((b"II*\x00", b"MM\x00*")):
        return TIFF
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return WEBP
    if len(header) >= 12 and header[4:8] == b"ftyp":
        brand = header[8:12]
        if brand in (b"avif", b"avis"):
            return AVIF
        if brand in (b"heic", b"heix", b"hevc", b"mif1", b"msf1"):
            return "image/heic"
    _report_unknown_signature(header)
    return fallback


def image_bytes_to_data_url(data: bytes, *, fallback: str = DEFAULT_IMAGE_MIME) -> str:
    """data-URL с настоящим MIME вместо всегдашнего ``image/jpeg``."""
    raw = bytes(data or b"")
    payload = base64.b64encode(raw).decode("ascii")
    mime = detect_image_mime(raw, fallback=fallback)
    return f"data:{mime};base64,{payload}"


def split_data_url(url: str) -> Optional[Tuple[str, str]]:
    """``(mime, base64)`` для base64-data-URL. Всё остальное — ``None``.

    Раньше провайдеры резали строку по первой запятой, поэтому обычная
    ссылка с запятой превращалась в «изображение» с мусором вместо данных.
    """
    text = str(url or "").strip()
    if not text.startswith("data:"):
        return None
    header, separator, payload = text.partition(",")
    if not separator:
        return None
    meta = header[len("data:"):]
    if ";base64" not in meta.lower():
        return None
    mime = meta.split(";", 1)[0].strip().lower() or "application/octet-stream"
    return mime, payload


__all__ = [
    "AVIF",
    "BMP",
    "DEFAULT_IMAGE_MIME",
    "GIF",
    "JPEG",
    "PNG",
    "TIFF",
    "WEBP",
    "detect_image_mime",
    "image_bytes_to_data_url",
    "split_data_url",
]
