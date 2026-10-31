# Токен-бюджет, стоимость запросов и model metadata

**Статус:** ACTIVE (показ контекста/учёт usage), CONDITIONAL (динамические provider pricing). **Ревизия:** Python `CodeNow.zip` / historical releases `38172493`; ZIP без Git history. **Метод:** статическое чтение `src/managers/{context_counter,model_pricing_manager}.py`, `src/controllers/model_controller.py` и UI view. Реальные LLM/models HTTP не вызывались. Эта область отсутствовала как самостоятельная capability в предыдущем функциональном каталоге.

## CAP-TOKEN-001 — оценка объёма текущего контекста

**Источники:** `src/managers/context_counter.py:11-147`; `src/controllers/model_controller.py:983-1074`; `src/ui/windows/app_window_base.py:908-975`; `src/controllers/gui/sandbox_page_view_model.py:250-272`.

**Назначение и сценарий:** UI показывает объём сообщения перед отправкой и приблизительное заполнение окна модели. Backend `ModelController._build_current_context_messages()` берёт deep copy **последнего сохранённого request snapshot** для `(character_id, "chat")` и считает его токены, не выполняя генерацию prompt DSL и не вызывая сборку истории заново. Число актуально только для этого snapshot, не обязано совпадать с фактическим следующим запросом после изменения настроек/истории.

`ContextCounter` пытается инициализировать `tiktoken` для фиксированного `gpt-4o-mini`, при отсутствии/ошибке использует `heuristic = max(chars/4,words*1.3)+non_ascii*0.5`. Это оценка, а не биллинговая гарантия, даже если точный tokenizer для `gpt-4o-mini` доступен: другой провайдер/модель может токенизировать текст иначе. Подсчёт по содержимому messages, tool_calls JSON; картинки пропускаются, потому что image tokens provider-specific; роль/метаданные сообщения отдельно не тарифицируются (`context_counter.py:79-147`).

`known_model_context_length` сопоставляет имя модели по substrings в заданном порядке (Gemini/GPT/Claude/DeepSeek/Qwen...), используется для UI context window при отсутствии metadata и сохранённом default `MAX_MODEL_TOKENS=32000`; явное отличающееся от default пользовательское значение имеет приоритет (`model_controller.py:1037-1055`). Этот fallback **не определяет фактический лимит срезания истории** (`model_pricing_manager.py:18-64`).

## CAP-PRICE-001 — pricing metadata, кэш и provider semantics

**Источники:** `src/managers/model_pricing_manager.py:67-359`, `src/presets/provider_host_metadata.py:1-21`, `src/controllers/model_controller.py:992-1154`.

`ModelPricingManager.resolve_for_preset(preset)` выполняется без HTTP на вызывающем потоке: возвращает cache hit/stale/None и запускает supervised background thread для `openrouter_default` или `openai_compatible_default` (`:174-228`). Запрашивает полученный из preset URL `/v1/models` с bearer либо предоставленными headers, timeout=3s; ожидает `data` или `models` список и **точно совпадающий** `id` (`:229-316`). Ключ кэша — **`(protocol_id, api_model)`**, TTL на успех 3600 s, на `None` 30 s, _inflight дедуплицирует запросы. На shutdown manager отменяет supervised owner tasks и закрывает свой transport (`:156-172`).

`ModelPricingInfo` хранит context length, max completion, цену prompt, completion, request, reasoning, cached input read/write, currency и source provenance. `estimate_usage_cost` вычитает cached/read+write tokens из noncached prompt, суммирует доступные компоненты и fixed per-request charge. Частичный pricing metadata может дать частичную estimated cost — цена не называется гарантированно точной (`:96-153`).

`_normalize_openai_compat_pricing_units` делит значения на 1e6 **только для host с `chutes.ai`**; inference валюты для `proxyapi.ru` и `kodikrouter.ru` ставит RUB, иначе explicit currency / USD (`model_pricing_manager.py:76-93,318-320`; `provider_host_metadata.py`). Это текущие provider-specific adapter rules, не универсальная политика перевода валют и не финансовый API. При смене provider API URL формат pricing следует пересмотреть.

### Тонкий риск identity cache

В ключ **не входят** API host, custom endpoint, account/tenant и currency. Два разных OpenAI-compatible сервера с одинаковым `api_model`/`protocol_id` могут получить чужой cached price до обновления либо после него. Это следует напрямую из `resolve_for_preset:185-203`; фактическое столкновение не воспроизводилось. Новый контур должен определять `source provider identity` по всей информации, влияющей на цену и окно, а не только model ID.

## CAP-PRICE-002 — estimated input cost vs actual last response

**Источник:** `src/controllers/model_controller.py:992-1154, 1914-1958, 2181,2393,2556`, `src/ui/windows/app_window_base.py:908-975`, `src/controllers/gui/sandbox_page_view_model.py:250-272`.

1. **Перед запросом** `estimated_context_tokens` = count по cached request snapshot, цена = provider metadata `prompt_cost_per_token * tokens`. Если metadata отсутствует, явная `cfg.token_cost_input > 0` даёт пользовательскую RUB estimate per 1000 tokens; иначе cost `None` (не фальсифицируется как free). Валюта и источник отдельно в результате (`model_controller.py:1009-1031`).
2. **После ответа** `LLMResponse.usage` содержит actual provider-reported counts/cost. При отсутствии price в usage `ModelPricingInfo.estimate_usage_cost` создаёт fallback для stored history snapshot + last-token stats; настоящий usage.cost имеет приоритет (`:1110-1143, 1914-1958`). Статистика сохраняет `actual_model`, `actual_provider`, `cost_source` и token breakdown.
3. **Показ:** основной chat UI отрисовывает оценку и bar (5-сегментный, цвета при ≥50%/≥85%) отдельно от **прошлого запроса** `prompt/completion/total`, показывает стоимость только если она известна (`app_window_base.py:908-975`). В Sandbox `refresh_budget` читает settings `MAX_MODEL_TOKENS`, а не `max_context_tokens` из оценки, и приводит отсутствующую цену к `0.0` (`sandbox_page_view_model.py:250-272`) — UI модели имеют разную семантику одного «budget».

### Состояние и границы качества

- `_last_token_stats` является полем единственного `ModelController` без character-scoped key (`model_controller.py:196,1032,1097`). При переключении персонажа context estimate переходит на другой character ID, но **last actual usage** остаётся от последней глобальной генерации. UI пишет «прошлый запрос» и может быть допустим global convention, однако такой scope должен быть явно определён при новом проектировании.
- Event `GET_TOKEN_STATS` возвращает весь snapshot, `GET_CURRENT_CONTEXT_TOKENS` только estimate. `CALCULATE_COST` преобразует unknown/None в `0.0` (`:1145-1154`), хотя rich statistics возвращает `None` и UI может скрывать цену. Клиенты этого legacy event могут спутать unknown и free, поэтому для паритета нужно зафиксировать точную семантику потребителя.
- Сетевое получение цен неблокирующее, но **свежесть не гарантирована**: stale cache может быть показан до завершения refresh; ошибочный fetch `None` кэшируется 30 s, даже если прежде была stale usable info (`model_pricing_manager.py:190-220`). Это functional behavior, не просто performance optimization.

## Требования для нового Core (без выбора Rust реализации)

- `REQ-TOKEN-001`: token estimate явно содержит provenance `tokenizer/model/heuristic`, snapshot identity и непокрытые modality; не представлять estimate как точную provider quota.
- `REQ-TOKEN-002`: хранить отдельно estimated context window / effective generation-history budget / actual provider usage; manual context override не маскировать model metadata без правила приоритета.
- `REQ-PRICE-001`: pricing request не блокирует критическую UI/event loop, явно показывает freshness/unknown/source/currency; cached identity включает endpoint/provider, model/version и account scope, если цена зависит от него.
- `REQ-PRICE-002`: estimated prompt, provider actual cost, locally computed fallback и per-request pricing считаются отдельными provenance, без смешивания currencies.
- `REQ-PRICE-003`: last usage scope (global/character/session/turn) задокументирован, отображение Sandbox и chat не конфликтует; zero ≠ unknown.

**Проверки:** два сервера с одинаковым `model` и разными ценами; dynamic URI change; cache hit/miss/negative; non-ASCII estimate; image-only request; user override vs provider reported context; cached token deduction; unknown price; switching current character between responses; timeout/failure с предыдущим stale cache.

**Rust alternatives:** специализированный tokenizer (или heuristic), HTTP клиент и state cache необходимо исследовать позже. Нельзя требовать `tiktoken` в Rust Core как пакет только из факта Python import. **Уверенность:** CONFIRMED ветви; INFERRED риск price identity, scoped last token stats; реальная provider data и UI на машине не проверялись.
