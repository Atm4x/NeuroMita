# src/managers/tools/builtin/web_search.py
import json
import time

import requests
from ddgs import DDGS

from managers.tools.base import Tool
from managers.settings_manager import SettingsManager
from main_logger import logger

_MAX_SNIPPET = 400
_DEFAULT_REGION = "ru-ru"
# Цепочка фолбэка: сперва агрегирующий auto, затем явные наборы движков.
# Валидные движки ddgs: bing, brave, google, mojeek, wikipedia, yandex.
_BACKEND_CHAIN = ["auto", "google, bing, brave", "mojeek, yandex, wikipedia"]

_SAFESEARCH_SEARX = {"off": 0, "moderate": 1, "on": 2}
_TIMELIMIT_SEARX = {"d": "day", "w": "week", "m": "month", "y": "year"}


class WebSearchTool(Tool):
    name = "web_search"
    description = (
        "Ищет в интернете (мета-поиск по нескольким движкам сразу) и возвращает JSON-список "
        "результатов: title, url, snippet. Для чтения полного текста страницы используй web_reader."
    )

    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Поисковый запрос"},
            "max_results": {
                "type": "integer",
                "description": "Максимальное количество результатов",
                "minimum": 3,
                "maximum": 20,
                "default": 5,
            },
            "timelimit": {
                "type": "string",
                "description": "Свежесть результатов: d — день, w — неделя, m — месяц, y — год. Пусто = без ограничения.",
                "enum": ["d", "w", "m", "y"],
            },
            "region": {
                "type": "string",
                "description": "Регион поиска вида ru-ru, us-en. По умолчанию берётся из настроек.",
            },
        },
        "required": ["query"],
    }

    def run(self, query: str, max_results: int = 5, timelimit: str = None, region: str = None, **_) -> str:
        query = (query or "").strip()
        if not query:
            return "[web_search] Пустой запрос"

        try:
            max_results = max(3, min(int(max_results), 20))
        except (TypeError, ValueError):
            max_results = 5

        region = region or SettingsManager.get("WEB_SEARCH_REGION", _DEFAULT_REGION) or _DEFAULT_REGION
        safesearch = str(SettingsManager.get("WEB_SEARCH_SAFESEARCH", "off") or "off")
        timelimit = timelimit if timelimit in ("d", "w", "m", "y") else None

        # Приоритетный источник — SearXNG (если задан инстанс), иначе DDG-цепочка.
        searxng_url = str(SettingsManager.get("WEB_SEARCH_SEARXNG_URL", "") or "").strip()
        failed = False
        results = []
        if searxng_url:
            try:
                results = self._search_searxng(searxng_url, query, max_results, region, safesearch, timelimit)
            except Exception as e:
                failed = True
                logger.warning(f"[web_search] SearXNG '{searxng_url}' -> {type(e).__name__}: {e}; фолбэк на DDG")

        if not results:
            results, ddg_failed = self._search_with_fallback(query, max_results, region, safesearch, timelimit)
            failed = failed or ddg_failed

        formatted = self._format(results)

        if not formatted:
            if failed:
                return "[web_search] Поиск временно недоступен (сеть/лимит). Стоит попробовать позже."
            return "[web_search] Ничего не найдено"

        return json.dumps(formatted, ensure_ascii=False, indent=2)

    def _search_with_fallback(self, query, max_results, region, safesearch, timelimit):
        """Возвращает (results, any_hard_error). Свежая DDGS-сессия на каждую попытку."""
        any_error = False
        for attempt, backend in enumerate(_BACKEND_CHAIN):
            try:
                with DDGS() as ddgs:
                    res = ddgs.text(
                        query,
                        region=region,
                        safesearch=safesearch,
                        timelimit=timelimit,
                        max_results=max_results,
                        backend=backend,
                    )
                if res:
                    return res, any_error
                logger.info(f"[web_search] backend='{backend}': пусто, пробуем следующий")
            except Exception as e:
                # Пустой результат в ddgs тоже кидается исключением — не считаем это
                # жёсткой ошибкой, но сетевые/лимитные ошибки помечаем.
                msg = str(e)
                if "No results" not in msg:
                    any_error = True
                logger.warning(f"[web_search] backend='{backend}' -> {type(e).__name__}: {e}")
                time.sleep(0.5 * (attempt + 1))  # мягкий бэкофф между попытками
        return [], any_error

    def _search_searxng(self, base_url, query, max_results, region, safesearch, timelimit):
        """Запрос к SearXNG (JSON API). Возвращает список результатов в формате движка."""
        base = base_url.rstrip("/")
        endpoint = base if base.endswith("/search") else base + "/search"

        # region 'ru-ru' -> language 'ru-RU'; safesearch/timelimit -> формат SearXNG.
        parts = str(region or "").split("-")
        language = f"{parts[0].lower()}-{parts[1].upper()}" if len(parts) == 2 and parts[1] else (parts[0].lower() or "all")

        params = {
            "q": query,
            "format": "json",
            "language": language,
            "safesearch": _SAFESEARCH_SEARX.get(safesearch, 0),
            "categories": "general",
            "pageno": 1,
        }
        if timelimit in _TIMELIMIT_SEARX:
            params["time_range"] = _TIMELIMIT_SEARX[timelimit]

        resp = requests.get(endpoint, params=params, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        data = resp.json()
        return (data.get("results") or [])[:max_results]

    def _format(self, results):
        out = []
        seen = set()
        for r in results or []:
            if not isinstance(r, dict):
                continue
            url = r.get("href") or r.get("url") or r.get("link") or ""
            if not url or url in seen:
                continue
            seen.add(url)

            snippet = (r.get("body") or r.get("snippet") or r.get("content") or r.get("description") or "").strip()
            if len(snippet) > _MAX_SNIPPET:
                snippet = snippet[:_MAX_SNIPPET].rstrip() + " …"

            out.append({
                "title": (r.get("title") or "").strip() or url,
                "url": url,
                "snippet": snippet,
            })
        return out
