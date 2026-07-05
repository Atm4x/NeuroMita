# src/managers/tools/builtin/wikipedia_search.py
import json

import requests

from managers.tools.base import Tool
from managers.settings_manager import SettingsManager
from main_logger import logger

_MAX_EXTRACT = 800
_DEFAULT_LANG = "ru"
_UA = "NeuroMita/1.0 (https://github.com/VinerX/NeuroMita)"


class WikipediaSearchTool(Tool):
    name = "wikipedia_search"
    description = (
        "Ищет статьи в Википедии и возвращает краткие выжимки (intro) с ссылками. "
        "Быстро и бесплатно закрывает фактические вопросы (кто/что/когда). "
        "Для актуальных событий лучше web_search."
    )

    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Тема или название статьи"},
            "max_results": {
                "type": "integer",
                "description": "Сколько статей вернуть",
                "minimum": 1,
                "maximum": 5,
                "default": 3,
            },
            "lang": {
                "type": "string",
                "description": "Язык Википедии: ru, en и т.п. По умолчанию из настроек.",
            },
        },
        "required": ["query"],
    }

    def run(self, query: str, max_results: int = 3, lang: str = None, **_) -> str:
        query = (query or "").strip()
        if not query:
            return "[wikipedia_search] Пустой запрос"

        try:
            max_results = max(1, min(int(max_results), 5))
        except (TypeError, ValueError):
            max_results = 3

        primary = (lang or SettingsManager.get("WIKIPEDIA_LANG", _DEFAULT_LANG) or _DEFAULT_LANG).strip().lower()
        # Языки для попытки: заданный + запасной (ru<->en), без дублей.
        langs = [primary] + [l for l in (_DEFAULT_LANG, "en") if l != primary]

        for lg in langs:
            try:
                results = self._query(lg, query, max_results)
            except Exception as e:
                logger.warning(f"[wikipedia_search] lang={lg} ошибка: {type(e).__name__}: {e}")
                continue
            if results:
                return json.dumps(results, ensure_ascii=False, indent=2)

        return "[wikipedia_search] Ничего не найдено"

    def _query(self, lang: str, query: str, max_results: int) -> list:
        url = f"https://{lang}.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": query,
            "gsrlimit": max_results,
            "prop": "extracts|info",
            "exintro": 1,
            "explaintext": 1,
            "inprop": "url",
            "redirects": 1,
        }
        resp = requests.get(url, params=params, timeout=12, headers={"User-Agent": _UA})
        resp.raise_for_status()
        data = resp.json()

        pages = ((data.get("query") or {}).get("pages") or {})
        # Сохраняем порядок релевантности из index, который отдаёт generator=search.
        items = sorted(pages.values(), key=lambda p: p.get("index", 10**6))

        out = []
        for p in items:
            title = p.get("title") or ""
            page_url = p.get("fullurl") or p.get("canonicalurl") or ""
            extract = (p.get("extract") or "").strip()
            if len(extract) > _MAX_EXTRACT:
                extract = extract[:_MAX_EXTRACT].rstrip() + " …"
            if not title and not extract:
                continue
            out.append({"title": title, "url": page_url, "summary": extract})
        return out
