# HTTP client ownership, сетевые ошибки и retry semantics

**Capability:** `CAP-NETWORK-001—003`. **Статус:** ACTIVE / CONDITIONAL. Основной транспорт текущего Python Core — синхронный `httpx.Client` за per-service registry, с явным typed error normalizer. Это **поведение сегодня**, а не предписание сделать синхронный Rust HTTP layer. Не запускались реальные URL, сокеты и provider endpoints.

## CAP-NETWORK-001: service-bound HTTP client

**Источник:** `src/core/networking/http_clients.py:17-237`; consumers перечислены далее.

`HttpClientRegistry.acquire(service_id)` нормализует nonempty service ID в lowercase, под `RLock` создаёт один `httpx.Client` или переиспользует уже зарегистрированный и увеличивает счётчик references (`:102-130`). `ManagedHttpClient` — handle, не владеющий собственным TCP pool непосредственно; `release` уменьшает счётчик, закрывает фактический клиент при нуле (`:23-92,188-200`). `registry.close()` закрывает множество client objects (deduplicated по identity), запрещает дальнейшие acquisitions; shared singleton закрывается через `atexit` (`:201-237`).

**Неочевидные границы:**

- `client_options`/`client_factory` применяются **только на первой регистрации service ID**. Повторная выдача handle того же ID не сверяет options, а явный другой client приводит к ValueError (`:114-128`). Identity сервиса — фактически identity pool/config, что надо понимать при нескольких endpoint accounts. Нельзя молча копировать по одному global client без ясной network policy.
- `ManagedHttpClient.close()` идемпотентен, но сам клиент закрывается при последнем handle, поэтому **другая ongoing operation**, держащая ссылку на underlying client из `_client()` после снятия lock, может встретить закрытие в середине запроса, если lifecycle их не координирует. Это **INFERRED potential concurrency risk**, не доказанный defect: надо искать реальные concurrent release paths (`:131-186,188-223`).
- Registry предоставляет `request`, `build_request`, `send`, context-managed `stream`, `raise_for_status`. При `stream()` context manager удерживает `httpx` response до выхода (`:171-186`); release реестра может с этим конфликтовать при ошибочном shutdown ownership.
- `get/post` не вызывают `raise_for_status` автоматически; HTTP4xx/5xx преобразуются в `HttpResponseError` **только при отдельном** `ManagedHttpClient.raise_for_status` либо при downstream обработке. Сценарий `200 + неправильная схема JSON` лежит вообще вне сетевой классификации.

**Подтверждённые потребители через imports:** `LLMHttpClient` (`handlers/llm_providers/http_transport.py:11,99-121`), Gemini/OpenAI embeddings, remote voice, news, chess online engine, FFmpeg installer, prompt downloader, updater, web-read/google-search. `rg -n 'shared_http_client_registry' src --glob '*.py'` выявляет также тестовые references; это не исчерпывающий список неявных HTTP users (`requests`, `aiohttp`, SDK clients`). Указанные потребители отличаются retry/privacy/idempotency, их нельзя автоматически свести к общей «повтори всё» политике.

## CAP-NETWORK-002: ошибки и диагностическое представление

**Источник:** `src/core/networking/errors.py:13-374`; тесты `src/utils/Testing/test_http_client_registry.py:16-119` (читались, не выполнялись).

`classify_network_error(service_id, exc, method?, url?)` сохраняет service/phase/status/retryable и выдаёт подклассы `NetworkRequestError`, доступные для UI/telemetry через `to_payload`. Таблица фактических ветвей:

| Источник | Код / фаза | Retryable в классификаторе | Ограничение |
|---|---|---|---|
| InvalidURL, UnsupportedProtocol | `network.url.invalid` / configuration | false | URL может быть syntactically valid, но недоступен политикой конкретного provider |
| TLS certificate failure | `network.tls.certificate` / connect | false | SSL validation не отключается автоматически |
| Другой TLS handshake | `network.tls.handshake` / connect | false | Detail sanitization bounded |
| HTTPStatusError | `http.status` / response | true для 408/409/425/429/500/502/503/504 | Retryability не означает безопасное повторение side effect |
| Connect/Pool Timeout | `network.timeout.connect|pool` / соответствующая фаза | true | Запрос не обязательно попал на сервер |
| Read/Write Timeout | `network.timeout.read|write` | false | Read timeout может наступить после выполненной сервером операции |
| DNS/connect/proxy | `network.dns|connect` / connect | true | Резолвинг DNS heuristics требует реального cross-platform test |
| TransportError | `network.{connect,pool,read,write,protocol,transport}` | true только для connect/pool/read | Прерывание чтения не гарантирует idempotency |
| Unknown | `network.request` / request | false по умолчанию | Конкретная причина остаётся в detail/log |

`NetworkRequestError.__post_init__` вызывает `sanitize_url`: удаляет credentials в `userinfo`/fragment, маскирует известные query keys (`token`, `key`, `api_key`, `access_token`, `password` и др.), сохраняет path и несекретные query параметры (`errors.py:13-24,72-91,94-122`). `detail` нормализуется и заменяет ряд ключей через regex, затем режется до 500 символов (`:319-329`). **Не доказано**, что sanitizer покрывает все возможные пользовательские secret keys, произвольные bearer headers или token в path. Нельзя считать `to_payload` автоматически безопасным для открытой telemetry/upload без policy.

## CAP-NETWORK-003: отдельный LLM timeout contract

**Источник:** `src/handlers/llm_providers/http_transport.py:25-95,98-...`, [протокольные состояния](openai-protocol-state-machines.md), [LLM requests](llm-requests.md).

`LLMTimeoutPolicy.for_request` имеет пять измерений: `connect`, `write`, `read`, `pool`, `attempt_deadline`. Default total — 240 s; loopback соединение получает короткий connect/pool budget (до 5 s), не-loopback — 30/10 s. При JSON payload ≥512 KiB write budget увеличивается: до 120–180 s, ограничено total; маленький payload до 60 s. Значения можно переопределить через `req.extra.http_*timeout_seconds`, но `_positive_float` контролирует invalid input. Эти budgets **не** равны гарантии физической отмены server inference. Cancellation token и `register_cancellable_resource` — отдельный stage в HTTP adapter; общий `HttpClientRegistry` сам по себе cancel transport не делает.

Сохранить функциональный смысл: endpoint/locality-specific connect, payload-sensitive upload, pool wait, read/stream idle, deadline каждой попытки и absolute turn deadline, а также status classification и UI language. Не копировать численные constants без замеров реального failure budget / product decision, но не терять разные состояния.

## Требования к новой реализации / потенциальная переорганизация

- `REQ-NET-001`: открываемые HTTP ресурсы имеют явного владельца и определённые shutdown/stream-in-flight guarantees; сервисный pool config не меняется скрыто при повторном acquire того же ID.
- `REQ-NET-002`: нормализованный error contract сохраняет category, retryability, phase, HTTP status, user-facing message, sanitised diagnostic identity; не выдаёт raw credentials.
- `REQ-NET-003`: retry определяется конкретной операцией и уровнем её idempotency, а не только `network_error.retryable=true`. Для POST/tool-calling/installer downloads обязательны отдельные policy/continuation contracts.
- `REQ-NET-004`: LLM timeout policy различает connect/write/read/pool/attempt/turn cancellation; streaming response освобождает resources и не допускает позднюю публикацию после отмены.

**Проверки:** `httpx.MockTransport` fixture для DNS/TLS/timeout/read-stream/HTTP status, race close-with-active-stream, repeated service ID with incompatible options, redaction query/path/userinfo/header, provider request cancellation. Тест `test_http_client_registry.py` читался только; результаты его запуска не утверждаются.

## Что осталось

- Просмотреть по consumers точные lifecycle/close() callbacks (module-level acquisitions могут жить до interpreter exit), request idempotency для отдельных fetch/edit/update APIs и retry-after header.
- Точный cross-process policy Python AI worker и Rust HTTP client: worker может иметь свой независимый transport и сетевой cache, не нужно смешивать их экземпляры.
- Исследование TLS pinning/proxy/offline режимов, custom certificates, HTTP/2 backend compatibility, частичных streamed responses и передаваемых secret metadata. Эти вопросы нельзя закрыть только по центральному `http_clients.py`.
