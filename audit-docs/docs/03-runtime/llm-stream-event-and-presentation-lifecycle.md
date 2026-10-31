# Поток LLM: доменные события, текстовые каналы и UI-коалесцирование

**Цель:** описать реализованное наблюдаемое поведение streaming без копирования Python threads/Qt events в Rust-архитектуру. Провайдерский SSE и presentation обновления — разные контракты. Источник — локальный `CodeNow.zip`; live API/E2E не запускались.

## CAP-STREAM-001 — нормализованные события ответа (ACTIVE/CONDITIONAL)

`LLMStreamEvent` содержит `type`, `request_id`, `provider`, `model`, возрастающий `sequence`, `timestamp`, `text`, optional `tool_call_id/tool_name/usage/finish_reason`, а при неудаче — `retryable`, `error_code`, `raw_provider_code` и metadata. Набор событий: `STARTED`, `TEXT_DELTA`, `REASONING_DELTA`, `TOOL_CALL_STARTED/DELTA/COMPLETED`, `USAGE`, `COMPLETED`, `FAILED`. Terminal — только `COMPLETED` или `FAILED`. **Источник:** `src/services/llm_stream.py:7-44`.

`StreamEventChannel` обеспечивает один логический `STARTED` перед содержимым, монотонную sequence и не более одного terminal event. `complete()` предваряет `COMPLETED` usage при его наличии; `fail()` формирует структурированную ошибку. Ошибка consumer callback отключает callback после логирования, не должна трактоваться как успешное получение UI. **Источник:** `src/handlers/llm_providers/streaming.py:90-201`.

## CAP-STREAM-002 — генерация отдельно от показа пользователю (ACTIVE/CONDITIONAL)

`StreamAccumulator` накапливает `text_parts` и `reasoning_parts` отдельно, tool calls — третьим каналом. Накопленные значения используются для финального `LLMResponse`, включая отсутствие видимого текста при наличии tool calls. Он может посылать и typed stream event callback, и совместимый `stream_cb(text, channel)`; `reasoning` не маскируется синтетическим `<think>` в текстовом канале. Provider-specific SSE адаптируется к этой семантике в провайдерском протоколе. **Источник:** `src/handlers/llm_providers/streaming.py:205-311`.

У `ChatController` показ потокового текста возможен лишь при `ENABLE_STREAMING && policy.allow_streaming && policy.echo_to_ui`; флаг `SHOW_THINK_IN_GUI` отдельно управляет reasoning. Часть JSON-structured потока проходит `StructuredJsonStreamFilter`, который преобразует поля JSON в видимый assistant/reasoning и не равен финальному валидатору полного structured response. Смена видимого канала assistant↔think создаёт отдельное событие `PREPARE_STREAM_UI`; UI события отправляются с `EventDelivery.ORDERED`. **Источник:** `src/controllers/chat_controller.py:571-670`.

## CAP-STREAM-003 — ограниченная частота событий UI (ACTIVE/CONDITIONAL)

Для текстовых фрагментов `TextDeltaCoalescer` использует один worker на процесс отдельного stream-показа: собирает части по умолчанию до 25 мс, либо раньше при буфере ≥16 384 символов; `flush` — барьер, ожидающий завершения вызываемого UI emitter (timeout по умолчанию 5 с); `close(flush=True)` пытается выдать хвост и завершить worker за ограниченные 2 с. Consumer error ловится и логируется. Отмена UI stream не должна оставлять видимый «полответа» как окончательно сохранённый completion. **Источники:** `src/services/stream_presentation.py:10-136`; `src/controllers/chat_controller.py:575-668`.

Это механизм **подачи событий представлению**, а не ограничение токенов модели: локальные буферы и 25мс batching не меняют окончательный response content или usage. Новая система может иметь другой scheduling, но parity предполагает сохранение порядка, разграничение think/content, terminal outcome и flush перед сменой UI роли.

## Состояния, ошибки, зависимости и проверка

- **Сценарий:** провайдер начинает поток, присылает reasoning и content; при выключенном think reasoning не показывается, но финальная модель его может учитывать отдельно.
- **Сценарий:** короткие content deltas появляются часто; UI получает объединённые порции, а не обязательный update на каждый token.
- **Сценарий:** reasoning→content требует flush предыдущего вида до `PREPARE_STREAM_UI` нового, иначе части разных ролей смешаются.
- **Сценарий:** tool call может быть отдельным typed event, не является частью видимого текста; завершение и ошибка имеют terminal статус и ownership одного `request_id`.
- **Исход ошибок:** request failure, callback failure, timeout flush/close, cancellation и partial provider stream не должны трактоваться как эквивалентный «ответ завершён».
- **Смежные области:** [системный lifecycle LLM](../01-functional/llm-and-generation.md), [provider protocol](openai-protocol-state-machines.md), [состояния UI](../02-ui/generation-progress-error-and-voice-indicators.md), [performance traces](per-request-performance-traces-and-diagnostic-metrics.md).
- **Контрактные тесты:** `src/utils/Testing/test_llm_http_transport.py:~300-370` проверяет coalescing/flush/close; `test_chat_request_pipeline.py` — границы think/content и visible stream. Наличие кода теста не означает автоматически зелёного всего файла в текущем окружении.

## За рамками и возможная переорганизация

Нужны факты о реальном UX частичных результатов после отмены/сбоя и provider fallback под нагрузкой; отдельная проверка UI E2E. В будущем Rust Core владение request stream и его lifecycle должно быть явным, а UI отображение — отдельной проекцией; конкретные классы `TextDeltaCoalescer`, `StreamEventChannel` и Qt events **не** являются архитектурными требованиями. Никаких исправлений Python не выполнялось.
