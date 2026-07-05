# src/managers/tools/builtin/tavily_search.py
import json

import requests

from managers.tools.base import Tool
from managers.settings_manager import SettingsManager
from main_logger import logger

_API_URL = "https://api.tavily.com/search"
_MAX_SNIPPET = 500


class TavilySearchTool(Tool):
    name = "tavily_search"
    description = (
        "Поиск в интернете через Tavily — API, заточенный под ИИ: чистые релевантные выжимки "
        "и (опционально) готовый краткий ответ. Точнее web_search, но требует API-ключ."
    )

    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Поисковый запрос"},
            "max_results": {
                "type": "integer",
                "description": "Количество результатов",
                "minimum": 1,
                "maximum": 15,
                "default": 5,
            },
            "search_depth": {
                "type": "string",
                "description": "basic — быстро/дёшево, advanced — глубже и точнее.",
                "enum": ["basic", "advanced"],
            },
        },
        "required": ["query"],
    }

    def run(self, query: str, max_results: int = 5, search_depth: str = None, **_) -> str:
        query = (query or "").strip()
        if not query:
            return "[tavily_search] Пустой запрос"

        api_key = str(SettingsManager.get("TAVILY_API_KEY", "") or "").strip()
        if not api_key:
            return "[tavily_search] Ошибка: не задан TAVILY_API_KEY."

        try:
            max_results = max(1, min(int(max_results), 15))
        except (TypeError, ValueError):
            max_results = 5
        depth = search_depth if search_depth in ("basic", "advanced") else "basic"
        include_answer = bool(SettingsManager.get("TAVILY_INCLUDE_ANSWER", True))

        payload = {
            "query": query,
            "max_results": max_results,
            "search_depth": depth,
            "topic": "general",
            "include_answer": include_answer,
        }

        try:
            resp = requests.post(
                _API_URL,
                json=payload,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"[tavily_search] сеть/API: {e}")
            return f"[tavily_search] Ошибка сети или API: {e}"
        except Exception as e:
            logger.error(f"[tavily_search] неизвестная ошибка: {e}")
            return f"[tavily_search] Неизвестная ошибка: {e}"

        out = {}
        answer = (data.get("answer") or "").strip()
        if answer:
            out["answer"] = answer

        results = []
        for r in (data.get("results") or []):
            if not isinstance(r, dict):
                continue
            url = r.get("url") or ""
            if not url:
                continue
            content = (r.get("content") or "").strip()
            if len(content) > _MAX_SNIPPET:
                content = content[:_MAX_SNIPPET].rstrip() + " …"
            results.append({
                "title": (r.get("title") or "").strip() or url,
                "url": url,
                "snippet": content,
            })

        if not results and not answer:
            return "[tavily_search] Ничего не найдено"

        out["results"] = results
        return json.dumps(out, ensure_ascii=False, indent=2)
