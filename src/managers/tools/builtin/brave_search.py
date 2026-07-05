# src/managers/tools/builtin/brave_search.py
import json

import requests

from managers.tools.base import Tool
from managers.settings_manager import SettingsManager
from main_logger import logger

_API_URL = "https://api.search.brave.com/res/v1/web/search"
_MAX_SNIPPET = 400
_DEFAULT_REGION = "ru-ru"
_SAFESEARCH_BRAVE = {"off": "off", "moderate": "moderate", "on": "strict"}
_FRESHNESS_BRAVE = {"d": "pd", "w": "pw", "m": "pm", "y": "py"}


class BraveSearchTool(Tool):
    name = "brave_search"
    description = (
        "Поиск в интернете через Brave Search — независимый поисковый индекс (не Google). "
        "Приватный, качество хорошее. Требует API-ключ (есть бесплатный лимит ~2000/мес)."
    )

    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Поисковый запрос"},
            "max_results": {
                "type": "integer",
                "description": "Количество результатов",
                "minimum": 1,
                "maximum": 20,
                "default": 5,
            },
            "freshness": {
                "type": "string",
                "description": "Свежесть: d — день, w — неделя, m — месяц, y — год. Пусто = без ограничения.",
                "enum": ["d", "w", "m", "y"],
            },
        },
        "required": ["query"],
    }

    def run(self, query: str, max_results: int = 5, freshness: str = None, **_) -> str:
        query = (query or "").strip()
        if not query:
            return "[brave_search] Пустой запрос"

        api_key = str(SettingsManager.get("BRAVE_API_KEY", "") or "").strip()
        if not api_key:
            return "[brave_search] Ошибка: не задан BRAVE_API_KEY."

        try:
            max_results = max(1, min(int(max_results), 20))
        except (TypeError, ValueError):
            max_results = 5

        region = str(SettingsManager.get("WEB_SEARCH_REGION", _DEFAULT_REGION) or _DEFAULT_REGION)
        safesearch = str(SettingsManager.get("WEB_SEARCH_SAFESEARCH", "off") or "off")
        parts = region.split("-")
        search_lang = (parts[0] or "ru").lower()
        country = (parts[1].upper() if len(parts) == 2 and parts[1] else "RU")

        params = {
            "q": query,
            "count": max_results,
            "country": country,
            "search_lang": search_lang,
            "safesearch": _SAFESEARCH_BRAVE.get(safesearch, "off"),
        }
        if freshness in _FRESHNESS_BRAVE:
            params["freshness"] = _FRESHNESS_BRAVE[freshness]

        try:
            resp = requests.get(
                _API_URL,
                params=params,
                headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"[brave_search] сеть/API: {e}")
            return f"[brave_search] Ошибка сети или API: {e}"
        except Exception as e:
            logger.error(f"[brave_search] неизвестная ошибка: {e}")
            return f"[brave_search] Неизвестная ошибка: {e}"

        web_results = ((data.get("web") or {}).get("results") or [])
        results = []
        seen = set()
        for r in web_results:
            if not isinstance(r, dict):
                continue
            url = r.get("url") or ""
            if not url or url in seen:
                continue
            seen.add(url)
            snippet = (r.get("description") or "").strip()
            if len(snippet) > _MAX_SNIPPET:
                snippet = snippet[:_MAX_SNIPPET].rstrip() + " …"
            results.append({
                "title": (r.get("title") or "").strip() or url,
                "url": url,
                "snippet": snippet,
            })

        if not results:
            return "[brave_search] Ничего не найдено"

        return json.dumps(results, ensure_ascii=False, indent=2)
