# План: улучшение поиска в NeuroMita

Ветка: `feat/gemini-google-search`. Каждая порция = отдельный коммит + пуш в `origin`.

## Контекст

Поиск нужен Мите, чтобы отвечать на фактические/актуальные вопросы. Сейчас есть три
механизма (см. также [CLAUDE.md](CLAUDE.md), раздел про tools):

- `web_search` — DuckDuckGo через `ddgs` (бесплатно, качество среднее).
- `web_reader` — чтение страниц через Jina (`r.jina.ai`).
- `google_search` — Google Custom Search JSON API (нужен ключ + CSE id).
- **встроенный поиск модели (grounding)** — Gemini `google_search` / OpenRouter web-плагин
  (сделано в этой ветке, флаг `NATIVE_WEB_SEARCH`).

Проблема: чистый скрейп (DDG) душат анти-боты, официальные API платные и урезанные.
Цель — дать несколько альтернатив с автофолбэком, приоритет — бесплатным/keyless вариантам.

## Ландшафт альтернатив (справочно)

**1. Поиск внутри LLM (grounding):** Gemini (бесплатная квота), Perplexity Sonar (платно,
подключается как OpenAI-совместимый провайдер), OpenAI web_search, xAI Grok Live Search.

**2. API «под LLM» (ключ, чистая выдача):** Tavily (free 1000/мес ⭐), Brave Search API
(free ~2000/мес, свой индекс), Exa (нейросемантика), Serper.dev (дёшево, реальный Google SERP),
SerpAPI/Kagi (дороже).

**3. Self-host / keyless:** SearXNG (свой мета-поиск ⭐), Jina `s.jina.ai`, Mojeek,
Yandex XML (актуально для рус.), ddgs/DDG (уже есть).

**4. Специализированные (не веб-поиск, но часто нужнее):** Wikipedia/Wikidata API (бесплатно,
без лимитов ⭐), Open-Meteo (погода, keyless), новости, курсы валют.

⚠️ Bing Web Search API закрыт Microsoft (ретайр 2025) — не рассматриваем.

## Сделано (в этой ветке)

- [x] **P0.** Встроенный поиск модели по галке `NATIVE_WEB_SEARCH` (обобщённый флаг).
      Gemini `google_search` + OpenRouter web-плагин; fallback на prompt-JSON для Gemini 2.x,
      где grounding несовместим со structured output.
- [x] **P1.** Источники grounding в чате: `LLMResponse.sources` → `StructuredOutputPanel`
      (`SourcesBlock` с кликабельными ссылками). Gemini `groundingMetadata` + OpenRouter
      `annotations`.
- [x] **P2.** Надёжный `web_search` (DDG): свежая сессия на вызов, регион `ru-ru`, фолбэк
      бэкендов + бэкофф, устойчивый парсинг, `timelimit`, обрезка сниппетов.

## Порции к реализации

Порядок: от простого/самодостаточного к более крупному. Каждая — коммит+пуш.

- [x] **P3. Wikipedia-тул** (keyless, быстрые факты).
      `wikipedia_search`: MediaWiki API (`generator=search` + intro-extracts), язык из
      настроек `WIKIPEDIA_LANG` (ru) с фолбэком на en, обрезка выжимки. Зарегистрирован,
      галка `TOOL_ENABLED_wikipedia_search` в UI.

- [x] **P4. SearXNG-бэкенд для `web_search`** (главный апгрейд качества без ключей).
      `WEB_SEARCH_SEARXNG_URL` — если задан, `web_search` идёт в SearXNG (`/search?format=json`,
      маппинг region→language, safesearch, time_range) как приоритетный источник, при
      ошибке/пусто откатывается на DDG-цепочку. Поле URL в UI. Публичные инстансы часто
      блокируют JSON для ботов — фича для своего/доверенного инстанса.

- [ ] **P5. Tavily-тул** (opt-in, ключ; лучшее качество за деньги/free-tier).
      Новый `tavily_search` тул: `api.tavily.com/search`, ключ `TAVILY_API_KEY`.
      Регистрация + галка `TOOL_ENABLED_tavily` + поле ключа в UI. Автоскип без ключа.

- [ ] **P6. Единый формат выдачи + доку** (полировка).
      Привести `google_search` к общему формату (`link` → `url`), краткий раздел в
      `docs/` про варианты поиска и как их включить. Обновить CLAUDE.md при необходимости.

## Архитектурные заметки

- Добавление тула: класс в `src/managers/tools/builtin/` → экспорт в `builtin/__init__.py`
  → `ToolManager.register()` → имя в `_ALL_TOOLS_LIST` и `_DEFAULT_TOOL_ENABLED`
  (`model_controller.py`) → галка `TOOL_ENABLED_<name>` в `model_interaction_settings.py`.
- Тулы читают настройки через `SettingsManager.get(key, default)`.
- Ключи/URL хранить как обычные настройки; тул без ключа должен возвращать понятную ошибку,
  а не падать.
- Приоритет — не плодить провайдеров без надобности: SearXNG встраиваем в существующий
  `web_search`, а не отдельным тулом; Tavily — отдельным (другой контракт/ключ).
