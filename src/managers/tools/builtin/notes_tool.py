# src/managers/tools/builtin/notes_tool.py
"""
NotesTool — постоянное хранилище заметок в песочнице (папка Notes/).

  list   — перечислить заметки
  read   — прочитать заметку (с лимитом строк)
  search — найти строки по подстроке/regex
  create — создать новую заметку
  append — дописать в конец (основной способ накопления)
  edit   — заменить точное вхождение подстроки
  delete — перенести в Notes/.trash/

Модель оперирует ИМЕНАМИ, а не путями: путь целиком строится тут.
Запись атомарна (temp + os.replace) и защищена локом — к тулу ходят
и GUI-поток, и TCP-сервер игры.
"""
from __future__ import annotations

import datetime
import os
import re
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from managers.tools.base import Tool
from main_logger import logger

# ---------- лимиты песочницы -----------------------------------------------

MAX_FILE_BYTES = 1024 * 1024      # 1 МБ на заметку
MAX_FILES = 200                   # заметок в песочнице
MAX_READ_LINES = 400              # потолок для read
DEFAULT_READ_LINES = 200
MAX_SEARCH_HITS = 50

_TRASH_DIR = ".trash"
_EXT = ".md"

# Имя заметки: буквы (вкл. кириллицу), цифры, пробел, _ и -.
# Точки/слэши/двоеточия запрещены — этим отсекаются '..', пути и чужие расширения.
_NAME_RE = re.compile(r"^[\w \-]{1,64}$", re.UNICODE)

# Имена устройств Windows: 'con.md' — это по-прежнему консоль, а не файл.
# Запись в такое имя уходит в устройство и вешает процесс.
_RESERVED = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}


def _notes_dir() -> Path:
    return Path(os.environ.get("NEUROMITA_NOTES_DIR", os.path.abspath("Notes")))


class NoteNameError(ValueError):
    """Имя заметки не прошло валидацию песочницы."""


def _resolve(name: str, *, subdir: str = "") -> Path:
    """
    Имя заметки → абсолютный путь внутри песочницы.

    Валидация по белому списку символов, а не чёрному: '..', '/', '\\',
    ':' и абсолютные пути невозможны by construction. Финальная проверка
    на выход за пределы корня — на случай трюков с символами Unicode.
    """
    raw = (name or "").strip()
    if raw.lower().endswith(_EXT):
        raw = raw[: -len(_EXT)]
    if not _NAME_RE.match(raw):
        raise NoteNameError(
            f"Недопустимое имя заметки '{name}'. "
            f"Разрешены буквы, цифры, пробел, '_' и '-' (до 64 символов), без путей и расширений."
        )
    if raw.strip().rstrip(".").lower() in _RESERVED:
        raise NoteNameError(f"Имя '{name}' зарезервировано системой. Выбери другое.")

    root = _notes_dir().resolve()
    target = (root / subdir / (raw + _EXT)).resolve()
    if not target.is_relative_to(root):
        raise NoteNameError(f"Имя заметки '{name}' выводит за пределы папки заметок.")
    return target


def _ensure_root() -> Path:
    root = _notes_dir()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _count_notes(root: Path) -> int:
    return sum(1 for p in root.glob(f"*{_EXT}") if p.is_file())


def _fmt_size(n: int) -> str:
    return f"{n / 1024:.1f} КБ" if n >= 1024 else f"{n} Б"


class NotesTool(Tool):
    """Заметки Миты: чтение, поиск и запись в песочнице Notes/."""

    name = "notes"
    description = (
        "Persistent notes storage (markdown files in a sandboxed folder). "
        "Use it to remember things across sessions in a file the user can open: "
        "bug reports, TODO lists, observations, lore. "
        "list — show all notes; "
        "read — read a note (use max_lines, notes can be long); "
        "search — find matching lines in one or all notes (prefer this over read to check "
        "whether something is already written down); "
        "create — make a new note (fails if it exists); "
        "append — add text to the end of a note (creates it if missing) — the main way to accumulate entries; "
        "edit — replace an exact substring inside a note; "
        "delete — move a note to trash. "
        "The 'name' is a plain name like 'bugs' or 'todo', never a path or filename."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "read", "search", "create", "append", "edit", "delete"],
                "description": "Action to perform.",
            },
            "name": {
                "type": "string",
                "description": (
                    "Note name without path or extension, e.g. 'bugs'. "
                    "Required for all actions except 'list'. "
                    "For 'search' it is optional: omit to search across all notes."
                ),
            },
            "text": {
                "type": "string",
                "description": "Text to write (required for 'create' and 'append').",
            },
            "query": {
                "type": "string",
                "description": "Substring or regex to look for (required for 'search').",
            },
            "regex": {
                "type": "boolean",
                "description": "Treat 'query' as a regular expression. Default false.",
            },
            "old_text": {
                "type": "string",
                "description": (
                    "Exact existing substring to replace (required for 'edit'). "
                    "Must occur exactly once in the note."
                ),
            },
            "new_text": {
                "type": "string",
                "description": "Replacement for 'old_text' (required for 'edit'). Empty string deletes it.",
            },
            "max_lines": {
                "type": "integer",
                "description": f"Max lines to return for 'read'. Default {DEFAULT_READ_LINES}, cap {MAX_READ_LINES}.",
            },
            "offset": {
                "type": "integer",
                "description": "Line number to start reading from (1-based). Default 1.",
            },
            "timestamp": {
                "type": "boolean",
                "description": "Prefix appended text with the current date/time. Default true for 'append'.",
            },
        },
        "required": ["action"],
    }

    def __init__(self):
        self._lock = threading.RLock()

    # -- dispatch -----------------------------------------------------------

    def run(self, action: str, **kwargs) -> Any:
        action = str(action or "").lower().strip()
        handler = {
            "list": self._list,
            "read": self._read,
            "search": self._search,
            "create": self._create,
            "append": self._append,
            "edit": self._edit,
            "delete": self._delete,
        }.get(action)

        if handler is None:
            return (
                f"[notes] Неизвестное действие '{action}'. "
                f"Используй: list, read, search, create, append, edit, delete."
            )

        with self._lock:
            try:
                _ensure_root()
                return handler(**kwargs)
            except NoteNameError as e:
                return f"[notes] {e}"
            except OSError as e:
                logger.warning(f"[NotesTool] {action} failed: {e}")
                return f"[notes] Ошибка файловой системы: {e}"

    # -- actions ------------------------------------------------------------

    def _list(self, **_) -> str:
        root = _notes_dir()
        notes = sorted(
            (p for p in root.glob(f"*{_EXT}") if p.is_file()),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not notes:
            return "Заметок пока нет."

        lines = ["Заметки (свежие сверху):"]
        for p in notes:
            st = p.stat()
            mtime = datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")
            n_lines = sum(1 for _ in p.open(encoding="utf-8", errors="replace"))
            lines.append(f"  {p.stem} — {n_lines} стр., {_fmt_size(st.st_size)}, изменена {mtime}")
        return "\n".join(lines)

    def _read(self, name: str = None, max_lines: int = None, offset: int = None, **_) -> str:
        if not name:
            return "[notes] Укажи имя заметки (параметр name)."
        path = _resolve(name)
        if not path.exists():
            return f"[notes] Заметка '{name}' не найдена. Посмотри список через action='list'."

        limit = max(1, min(int(max_lines or DEFAULT_READ_LINES), MAX_READ_LINES))
        start = max(1, int(offset or 1))

        all_lines = _read_text(path).splitlines()
        total = len(all_lines)
        chunk = all_lines[start - 1 : start - 1 + limit]
        if not chunk:
            return f"[notes] В заметке '{name}' всего {total} строк, строка {start} за пределами."

        body = "\n".join(f"{start + i}\t{ln}" for i, ln in enumerate(chunk))
        shown_to = start + len(chunk) - 1
        header = f"'{name}', строки {start}–{shown_to} из {total}:"
        footer = ""
        if shown_to < total:
            footer = (
                f"\n[…ещё {total - shown_to} строк. "
                f"Читай дальше с offset={shown_to + 1} или используй search.]"
            )
        return f"{header}\n{body}{footer}"

    def _search(self, query: str = None, name: str = None, regex: bool = False, **_) -> str:
        if not query:
            return "[notes] Укажи, что искать (параметр query)."

        if regex:
            try:
                pat = re.compile(query, re.I | re.UNICODE)
            except re.error as e:
                return f"[notes] Некорректное регулярное выражение: {e}"
            matches = pat.search
        else:
            needle = query.lower()
            matches = lambda s: needle in s.lower()  # noqa: E731

        if name:
            path = _resolve(name)
            if not path.exists():
                return f"[notes] Заметка '{name}' не найдена."
            targets = [path]
        else:
            targets = sorted(p for p in _notes_dir().glob(f"*{_EXT}") if p.is_file())

        hits: List[str] = []
        truncated = False
        for p in targets:
            for i, line in enumerate(_read_text(p).splitlines(), start=1):
                if not matches(line):
                    continue
                if len(hits) >= MAX_SEARCH_HITS:
                    truncated = True
                    break
                hits.append(f"  {p.stem}:{i}\t{line.strip()}")
            if truncated:
                break

        if not hits:
            where = f"в заметке '{name}'" if name else "ни в одной заметке"
            return f"Совпадений с «{query}» {where} не найдено."

        out = [f"Найдено {len(hits)} совпадений с «{query}»:", *hits]
        if truncated:
            out.append(f"[…показаны первые {MAX_SEARCH_HITS}, уточни запрос.]")
        return "\n".join(out)

    def _create(self, name: str = None, text: str = None, **_) -> str:
        if not name:
            return "[notes] Укажи имя заметки (параметр name)."
        path = _resolve(name)
        if path.exists():
            return (
                f"[notes] Заметка '{name}' уже существует. "
                f"Используй action='append', чтобы дописать, или action='edit', чтобы изменить."
            )
        if _count_notes(_notes_dir()) >= MAX_FILES:
            return f"[notes] Достигнут лимит в {MAX_FILES} заметок. Удали ненужные через action='delete'."

        body = text or ""
        if len(body.encode("utf-8")) > MAX_FILE_BYTES:
            return f"[notes] Текст слишком большой (лимит {_fmt_size(MAX_FILE_BYTES)})."

        _atomic_write(path, body if body.endswith("\n") or not body else body + "\n")
        return f"Заметка '{name}' создана."

    def _append(self, name: str = None, text: str = None, timestamp: bool = True, **_) -> str:
        if not name:
            return "[notes] Укажи имя заметки (параметр name)."
        if not text:
            return "[notes] Укажи текст для добавления (параметр text)."

        path = _resolve(name)
        existed = path.exists()
        if not existed and _count_notes(_notes_dir()) >= MAX_FILES:
            return f"[notes] Достигнут лимит в {MAX_FILES} заметок. Удали ненужные через action='delete'."

        current = _read_text(path) if existed else ""
        if current and not current.endswith("\n"):
            current += "\n"

        entry = text.strip()
        if timestamp:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            entry = f"- [{now}] {entry}"

        updated = current + entry + "\n"
        if len(updated.encode("utf-8")) > MAX_FILE_BYTES:
            return (
                f"[notes] Заметка '{name}' достигла лимита {_fmt_size(MAX_FILE_BYTES)}. "
                f"Начни новую или удали лишнее."
            )

        _atomic_write(path, updated)
        verb = "дополнена" if existed else "создана"
        return f"Заметка '{name}' {verb}."

    def _edit(self, name: str = None, old_text: str = None, new_text: str = None, **_) -> str:
        if not name:
            return "[notes] Укажи имя заметки (параметр name)."
        if not old_text:
            return "[notes] Укажи заменяемый текст (параметр old_text)."

        path = _resolve(name)
        if not path.exists():
            return f"[notes] Заметка '{name}' не найдена."

        current = _read_text(path)
        occurrences = current.count(old_text)
        if occurrences == 0:
            return (
                f"[notes] Текст не найден в '{name}'. "
                f"Прочитай заметку (action='read') и укажи old_text точно, символ в символ."
            )
        if occurrences > 1:
            return (
                f"[notes] Текст встречается в '{name}' {occurrences} раз. "
                f"Расширь old_text, чтобы он указывал на одно место."
            )

        updated = current.replace(old_text, new_text or "")
        if len(updated.encode("utf-8")) > MAX_FILE_BYTES:
            return f"[notes] После правки заметка превысит лимит {_fmt_size(MAX_FILE_BYTES)}."

        _atomic_write(path, updated)
        return f"Заметка '{name}' изменена."

    def _delete(self, name: str = None, **_) -> str:
        if not name:
            return "[notes] Укажи имя заметки (параметр name)."
        path = _resolve(name)
        if not path.exists():
            return f"[notes] Заметка '{name}' не найдена."

        trash = _notes_dir() / _TRASH_DIR
        trash.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = trash / f"{path.stem}_{stamp}{_EXT}"
        os.replace(path, dest)
        return f"Заметка '{name}' перенесена в корзину ({_TRASH_DIR}/{dest.name})."
