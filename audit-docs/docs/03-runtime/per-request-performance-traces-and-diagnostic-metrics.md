# Производительность отдельного запроса: сквозные trace и наблюдаемые стадии

**Статус:** ACTIVE, преимущественно diagnostic/observability, не обязательная часть пользовательского UI. **CAP-DIAG-TRACE-001/002.** Источник `src/core/performance_trace.py`, активные emitters в `src/controllers/chat_controller.py`, `src/controllers/model_controller.py`, `src/controllers/audio_controller.py`, `src/controllers/speech_controller.py`, `src/managers/llm_request_runner.py`, `src/managers/tools/tool_manager.py`.

## Функциональный смысл

NeuroMita измеряет не только общее время ответа LLM: один логический запрос связывает ожидание worker, ожидание lock персонажа, retrieval, сборку prompt, сетевые HTTP очереди, first stream event / first visible text, структурную обработку, запись истории, запрос TTS, готовый голос и воспроизведение. ASR имеет собственный trace от capture/text-ready до передачи текста владельцу. Результат — отдельные трассы с `trace_id`, источником, стадиями, отметками, статусом завершения и вычисленными метриками.

Это **другой артефакт**, чем сохранённый prompt/context JSON, история сообщений и dataset. Trace предназначен для измерения стадий и diagnosing slow path без копирования пользовательских prompts в telemetry.

## Жизненный цикл

1. `PerformanceTraceStore.start(source, trace_id?)` возвращает действующий trace или создаёт новый; default ID случайный. `src/controllers/chat_controller.py` начинает trace desktop generation; модель получает request.trace_id, другие подсистемы берут его из payload.
2. `mark` сохраняет момент с именем; `mark_once` защищает одиночное событие first-visible-text; `span` измеряет длительность конкретного участка и фиксирует результат `success`/`error`.
3. Межпоточная передача идентификатора допускает продолжение trace в generation worker, asyncio/http runner, event callbacks, speech pipeline и GUI presentation.
4. `finish(trace_id,status,error_stage,error_type)` закрывает trace, завершает открытые span со статусом unfinished, переносит снимок в bounded finished deque. Повторное завершение уже отсутствующего ID возвращает None.
5. Снимки живых и завершённых запросов доступны через `snapshot`, `recent`, `active`, а `summary` строит avg/median/p95/max для именованных метрик и span durations. Старые активные трассы после **600s отсутствия активности** при следующем store access закрываются как abandoned (нет выделенного background timer).

`PerformanceTraceStore` хранит **не более 100 завершённых traces** по умолчанию, но это ограничение процесса и диагностической памяти, не сохранение между запусками. `recent` и summary доступны по API модуля, но публичная GUI-страница с полной таблицей метрик по просмотренным потребителям **не подтверждена**.

## Семантика отдельных метрик

| Наблюдение | Начало и конец | Какое поведение подтверждает |
|---|---|---|
| `generation_pool_wait_ms` | `generation.enqueued` → `generation.worker_started` | Время до взятия generation worker |
| `character_lock_wait_ms` | `generation.character_lock_wait_started` → `...acquired` | Ожидание сериализации запросов персонажа |
| `first_stream_event_ms` | trace start → `response.first_stream_event` | Первое событие канала, не обязательно видимый текст |
| `first_visible_text_ms` | trace start → `response.first_visible_text` | Первая отображаемая часть ответа |
| `llm_total_ms` | Сумма span `llm.total` | Время фактических provider phases, может включать tool follow-up |
| `llm_first_event_ms` | начало конкретного LLM span → первое событие внутри span | Event latency самого провайдера без предгенерационного времени |
| `llm_http_pool_wait_ms` | пары `llm.http_enqueued` → `...started` по attempt/provider/model | Ожидание HTTP semaphore/pool |
| `tts_total_ms` | `tts.synthesis` / `tts.telegram` spans | Генерация голоса по локальному/удалённому пути |
| `playback_start_ms` | trace start → `audio.playback_started` | Относительное время начала проигрывания |
| `full_pipeline_ms` | trace start → finish | End-to-end техническая длительность до статуса finish |

В метриках `first_stream_event` и `first_visible_text` не следует заменять одну на другую: stream event может означать reasoning/status/event without text. `first_visible_text` от старта trace включает queue+preprocessing, а `llm_first_visible_text_ms` (если есть) — от начала LLM span.

## Конфиденциальность и область гарантии

Функция `_safe_attributes` отбрасывает поля с именами, содержащими `prompt/input/output/content/argument/secret/token/password/api_key/url` (исключение для числовых count/chars/ms/sec metrics). Строки других имён ограничиваются 160 символами; это allow-by-convention hygiene, **не** формальная гарантия отсутствия персональных сведений в произвольном атрибуте. Ошибка телеметрии не должна срывать пользовательский запрос: почти все операции trace best-effort и ловят исключения.

## Требования для паритета, без выбора Rust-техники

Для нового Core оставить различие **queue wait → prompt/retrieval → external HTTP → provider streaming → structured processing → persistence → voice production → playback → finished**. `trace_id` должен описывать одну логическую операцию даже при смене потоков/процессов; границы AI worker и Unity потребуют отдельной correlation policy. Содержимое разговора не должно копироваться в метрики. Это обоснование функционального контракта наблюдаемости, а не рекомендация перенести текущие классы `PerformanceTraceStore`.

## Evidence и ограничения

- `src/core/performance_trace.py:24-65,86-360,362-565`: метрики, store и aggregate.
- `src/controllers/chat_controller.py:540,618,653,779,982-1114`: desktop dialogue, UI/text latency.
- `src/controllers/model_controller.py:1346-2416`: lock, RAG, prompt, LLM, structured, persistence.
- `src/controllers/audio_controller.py:131-407`, `src/controllers/speech_controller.py:957-1085`: TTS/playback, ASR delivery.
- `src/managers/llm_request_runner.py:464-474`: HTTP timing.
- `src/utils/Testing/test_performance_trace.py`, `test_performance_trace_integration.py`: исходные fixture scenarios; в данном проходе не исполнялись.

Не обнаружено подтверждённого durable export/retention и реального пользовательского GUI для summary; не проверялись GPU/native latency traces и cross-process remote telemetry. Отсутствие UI в просмотренных местах не доказывает невозможность доступа через другой consumer.
