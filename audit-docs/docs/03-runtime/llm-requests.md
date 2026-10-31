# LLM requests: попытки, fallback, deadlines

**Capability:** `CAP-LLM-003`. **Статус:** ACTIVE. Источники: `src/managers/llm_request_runner.py:77 run`, `:174 _run_on_preset`, `:440 _call_with_timeout`; `src/managers/api_preset_resolver.py:182 resolve_chain`; `src/managers/provider_manager.py:23 ProviderManager`; `src/handlers/llm_providers/streaming.py:28 StreamDeadlinePolicy`, `:65 StreamSupervisor`, `:94 StreamEventChannel`.

## Назначение и сценарий

Выполнить диалоговый или utility запрос с выбранными параметрами, повторить допустимые сбои, переключить preset fallback, обеспечить bounded waiting и cancellation. Входы: messages, preset id, request builder, max_attempts, retry_delay, request_timeout, cancellation и error correlation. Выход: LLMResponse либо cancellation exception; ошибки типизированы как LLMProviderError.

## Пресеты, ключи, routing

Resolver получает main + его список fallbacks, максимум 6 entries, пропускает некорректные/неразрешимые entries и дубликаты пары preset/model. Это не рекурсивный обход fallbacks каждого fallback. Model override задаётся на entry. Preset содержит protocol/dialect/provider, headers/transforms/capabilities, URL/model/key/reserve keys/native parameters и overrides.

Каждая попытка заново строит request с rotated key и согласованными auth headers/query. Без distribute_keys attempt-1 задаёт индекс ключа; с distribution начальный индекс меняется между запросами и дальнейшие attempts продолжают от него. Counters keyed preset name; конкурентная корректность этих общих dictionaries ещё не подтверждена.

ProviderManager регистрирует ChatGPTPlanProvider, ResponsesProvider, GeminiProvider и CommonProvider; импорт каждого может fail независимо. Shared HTTP transport создаётся с HTTP2 enabled. OpenAI provider route переходит к common, Responses dialect с common/openai — к responses. Enforcement может отключать streaming, в том числе при несовместимости native tools; message preprocessing и transforms выполняются до provider call.

Фактически predefined protocols: mistral_default, openrouter_default, openai_compatible_default, openai_responses_default, chatgpt_plan_default, lmstudio_default, aiio_default, google_gemini_default (`src/presets/api_protocols.py`). Это каталог текущей реализации, не утверждение о внешней доступности сервисов и не полный пользовательский registry.

## Правила повторов

Runner проходит presets по порядку, внутри каждого attempts. Успех — response без error_message и с text либо tool_calls. Non-retryable error прекращает attempts текущего preset, но не обязательно весь fallback chain. `_abort_chain` останавливает всю цепочку при отдельно определённых условиях.

Для timeout retry допустим до начала body при wire stream либо до получения headers для nonstream. Если stream body уже началось и есть failure, цепочка прекращается, даже когда ещё нет meaningful text. Это защищает от повторной генерации после принятой части ответа. Конкретная физическая доставка тела и stream events исследуется в adapters.

Retry delay = max(configured delay, provider retry-after, 0), ограниченный LLM_MAX_RETRY_DELAY_SECONDS (fallback 120). Между попытками учитываются shutdown/cancellation. Ошибка build_request использует отдельное ожидание shutdown_event и не проверяет operation cancellation во время всего ожидания — отдельный cancellation gap.

Terminal failure сообщает friendly error, console details, provider payload и message/character correlation, если переданы. StreamEventChannel получает fail. Request validation требует provider/url/model и ключ у официальных openai/gemini endpoints при текущей эвристике localhost; generic common может работать без ключа.

## Deadlines и физическая остановка

Provider call идёт в отдельный LLM_HTTP pool, не в generation worker напрямую. Saturation не создаёт бесконечную очередь. Nonstream ждёт future с polling до deadline. Wire stream использует first meaningful event, idle after meaningful event и maximum duration; policy for_request ограничивает значения effective attempt deadline. Значения dataclass defaults сами по себе не означают реальные runtime timeouts.

Timeout cancel-ит request token, пытается отменить Future, ждёт grace 0.1—1 s, затем может abandon daemon worker и заменить slot до лимита retired workers. Это логическое прекращение ожидания; Python thread не уничтожается принудительно. При user cancellation future также отменяется/abandon. Требуется проверить HTTP close callbacks и late event suppression в transport.

## Поток событий

StreamEventChannel имеет request id, increasing sequence, started/terminal и active provider label. При fallback label обновляется, канал сохраняется. complete публикует usage/completed; fail — failure metadata. Повторный terminal игнорируется, emit после terminal запрещён. Ошибка callback логируется и consumer отсоединяется без аварии provider.

## Состояние, UI и эффекты

Attempt errors/abort_chain хранятся thread-local, shutdown_event общий. ChatModel дополнительно хранит global last-error fallback; влияние на параллельные diagnostics требует проверки. Runner пишет optional debug dumps; ChatModel сохраняет request snapshot всегда для context viewer, независимо от finetune setting. Финальный ответ может создавать finetune sample, если collection включён.

## Требования к новой системе

Сохранить configurable retry/key rotation/fallback, классификацию ошибок, связь UI errors с message и запрет неявного рестарта после stream body. Разделить operation deadline, attempt deadline, idle deadline и physical resource termination. Сохранять bounded resource consumption даже при некооперативном provider. Retry должен быть частью предметного request policy, а не общей утилитой, повторяющей любые побочные эффекты.

Rust alternatives ещё не исследованы. Само наличие async/Drop не гарантирует отмену удалённой генерации или rollback: контракт HTTP endpoint и момент принятия side effect остаются отдельными условиями.

## Неисследованное

Provider adapters/auth/OAuth/transform registry, SSE buffering/tool deltas, RequestCancellation transport callbacks, key rotation synchronization, exact timeout calculation, native parameter merge, context snapshot persistence и sensitive data handling. Не объявлять provider audit завершённым.
