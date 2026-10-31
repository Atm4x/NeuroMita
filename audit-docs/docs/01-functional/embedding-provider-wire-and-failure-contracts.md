# Embedding providers: local worker, OpenAI-compatible API и Gemini batch API

**Цель:** восстановить три реально зарегистрированных режима получения embedding vectors для RAG, не смешивая Core request routing с Python AI inference. **Статус:** `CONDITIONAL` по выбранному `RAG_EMBED_PRESET_ID` и сети/установке worker. Source snapshot: `CodeNow.zip`.

## CAP-EMBED-PROVIDER-001 — общая граница

`src/handlers/embedding_providers/registry.py:11-81` связывает три стабильных provider type: `local`, `openai_compat`, `gemini`. Другие значения дают `EmbeddingProviderError`, а не молча выбирают локальный provider. `EmbeddingRequest` (`base.py:11-35`) хранит **упорядоченный** массив `texts`, `is_query`, model/url/key, резервные ключи, headers, query_prefix, hints `dimensions` и `extra`. Выход — массив L2-normalized float32 vectors или `None` на позициях неудачных записей. Реальный вызов из RAG проходит `src/managers/rag/embedding.py:55-63`: resolved config → request → selected provider. Смена provider preset и переиндексация — разные операции.

## CAP-EMBED-PROVIDER-002 — local Python AI

`src/handlers/embedding_providers/local_provider.py:13-45` не загружает `sentence_transformers` в Rust/Core transport, а лениво импортирует `handlers.ai_engine.rag_client.get_embeddings`. `model_id` получается из `api_url` (HF path/id) либо `model`, `query_prefix` применяется к поисковому запросу, задаётся optional batch size. Недоступный AI worker возвращает `None` по каждому тексту, а не исключение наружу. Вывод для новой версии: **remote-worker request** с сохранением positional alignment и model identity; inference остаётся Python.

## CAP-EMBED-PROVIDER-003 — OpenAI-compatible HTTP `/embeddings`

`src/handlers/embedding_providers/openai_compat_provider.py:25-119`: endpoint берётся из preset, к нему при необходимости добавляется `/embeddings`; API key не обязателен (локальные совместимые серверы), но если задан — Bearer header. В payload `model`, массив `input`, `encoding_format='float'`, optional `dimensions`. Только для `is_query` конкатенируется `query_prefix`. Ответ `{data:[{index,embedding},...]}` сортируется по `index`, vectors нормализуются L2. Endpoint с полным `/embeddings` не должен удваивать suffix.

Повторные попытки — по сетевым ошибкам и `408,429,500,502,503,504`, по умолчанию `max_retries=3` + initial attempt, `timeout_sec=60`, exponential delay / `Retry-After` при распознаваемом значении. При retry key выбирается циклически из основного + reserve keys (`:38-119`). **Сохранить функциональное различие между partial row и total failure:** протокол может вернуть меньше data entries, и current adapter не всегда возвращает строго длину входа (это факт текущей реализации, не требование сохранять этот недостаток). Новый функциональный контракт должен явно задавать positional result, не копируя случайную форму short response.

## CAP-EMBED-PROVIDER-004 — Gemini `batchEmbedContents`

`src/handlers/embedding_providers/gemini_provider.py:44-257`: доступен при основном/резервных ключах; по умолчанию `text-embedding-004`; запросы разбиваются на батчи до 100 текстов. URL `.../models/{model}:batchEmbedContents`, для каждого текста `content.parts[0].text`, `taskType` зависит от `is_query`: `RETRIEVAL_QUERY` vs `RETRIEVAL_DOCUMENT`. Credential передаётся в заголовке `x-goog-api-key`, а не query URL; error logger redacts ключи.

При `reserve_keys_distribute` стартовый key index меняется по кругу между батчами под lock, тогда как при выключенном флаге каждый batch начинает с первого ключа (`:99-107,163-186`). Retry statuses и параметры совпадают по смыслу с OpenAI-compatible, но на 429/5xx ключ вращается по `initial_index+attempt`, с `Retry-After` либо backoff (`:188-257`). Результат `embeddings[].values` конвертируется в float32, L2-normalized; недостающие позиции дополняются `None`. Это протокольно иной API, не generic OpenAI adapter.

## Входы, выходы, владение

| Контракт | Core | Отдельный Python AI | External API |
|---|---|---|---|
| Выбор provider/preset, model identity, query/document distinction | ✔ | — | — |
| Запрос локальных vectors и lifecycle worker | Подготовить/маршрутизировать | Выполняет inference | — |
| OpenAI/Gemini HTTP policy, ключи, retry, timeout | Опциональный HTTP клиент | Не обязателен для cloud embeddings | Отдаёт vectors |
| Persistent vector storage, source IDs, поисковые кандидаты | ✔ | — | — |
| Токенизация модели/encoder/ML preprocessing | В описании запроса, не inference | ✔ при local | Провайдер при remote |

**Недостаточно подтверждено:** live API совместимость, тайминги, модельные размерности, качество русского поиска, сценарии с перебоями резервных ключей, AI worker end-to-end. Все протоколы выше подтверждены статикой, реальных сетевых тестов не было.

**Acceptance fixtures:** пустые входы, неправильный type, 3 text → 3 positional outputs с `None` для missing, query/document разных task_type и prefix, локальный worker недоступен, Gemini >100 texts, HTTP retry/429/key rotation, index reordering, change embedding model без немедленной потери старых vectors.
