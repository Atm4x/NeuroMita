# Провайдерские wire-контракты: Gemini, Responses и ChatGPT Plan

**Фаза:** продолжение Python-аудита, 2026-10-30. **Статус:** CONDITIONAL (конкретная ветка определяется выбранным preset/протоколом). **Источник:** поставленные Python-исходники `CodeNow.zip`, ревизия по предыдущему checkpoint `releases` / `38172493fa0d1caf1a5225bc1c559f095f18bb7a`; Git metadata в ZIP не позволяет независимо проверить SHA. **Проверка:** статическая, без внешних HTTP-запросов.

## Назначение, входы, границы

Это не три отдельных генератора диалоговой бизнес-логики: провайдерский слой преобразует snapshot `LLMRequest` (messages, model, capabilities, native/unified parameters, stream, tools, headers, endpoint, cancellation) в wire-запрос и интерпретирует ответ как `LLMResponse` либо типизированную `LLMProviderError`. Policy retry/fallback живёт выше в request runner; HTTP transport не определяет пользовательское состояние истории. Проверенные реализации: `src/handlers/llm_providers/gemini_provider.py:27-581`, `chatgpt_plan_provider.py:19-191`, `http_transport.py:26-203`, `chatgpt_plan_protocol.py:12-65`. Общий OpenAI-compatible/Responses flow описан также в `../01-functional/provider-configuration.md` и `llm-requests.md`.

## Gemini: сериализация

- `gemini_provider.py:56-64`: для stream URL переписывает `:generateContent` на `:streamGenerateContent`, добавляя `alt=sse`, если query не задаёт его явно; nonstream URL сохраняет.
- `:66-117`: модель, имя которой содержит `gemma` и не содержит `gemini`, считается не поддерживающей `system_instruction`. Начальные system parts в этом случае вставляются с `[SYSTEM INFO]` в первый user message либо отдельный user message перед историей. Для остальных моделей начальные system parts передаются как отдельный `system_instruction`.
- `:131-192`: system-блоки *после* начала диалога сохраняют своё положение через user parts с tag. `assistant` переводится в `model`, прочие роли в `user`. Content допускает text, inline JPEG base64 из `image_url`, functionCall/functionResponse; незнакомые блоки превращаются в placeholder (не молча удаляются). MIME type жёстко `image/jpeg`, даже если data URI имеет иной MIME: потенциальная несовместимость изображений, а не доказанный runtime-дефект.
- `:295-365`: при наличии `native_parameters` `generationConfig` берётся непосредственно из их subtree; иначе unified параметры конвертируются (temperature, max_tokens→maxOutputTokens, presence/frequency penalty, topP, topK). Model profile задаёт allowlist/exclusions, thinking transport `level`/`budget`, диапазон и disabled budget (`:194-293`). Structured output требует caps `structured_output` и `native_structured_output` плюс разрешения model profile: `responseMimeType=application/json`, опционально `responseJsonSchema`; `gemini_prompt` оставляет JSON через prompt без schema.
- `:327-340`: отсутствие contents создаёт синтетическое `Generate an appropriate reaction.`; если последнее сообщение не `user`, код **переименовывает его роль в `user`** и маркирует текст `[SYSTEM INFO]`. Это семантически не то же самое, что добавление user-сообщения, и должно стать отдельным compatibility test.

## Gemini: ответ и ошибки

`gemini_provider.py:365-417`: transport POST; status != 200 нормализуется через `build_provider_error` и делегируется runner. `:419-466`: non-stream читает *первого* candidate, разделяет `thought` и обычные text parts, при отсутствии текста возвращает `"..."`; usage извлекается из `usageMetadata`. `:468-552`: stream принимает SSE `data` либо JSON text stream в зависимости от `Content-Type`; невалидный JSON, chunk неправильного типа и payload.error дают ошибку, а не частично успешный результат; body обрабатывается с проверкой cancellation. `:554-581`: cached token count включён в prompt tokens, не прибавляется вторично; thoughtsTokenCount→reasoning tokens. **Открыто:** candidates safety/filtering, отсутствие первого candidate/parts, behavior при trailing non-JSON; нужны тесты на wire fixtures и real responses.

## ChatGPT Plan (условный account-backed transport)

`chatgpt_plan_provider.py:32-143`: строго допустим только endpoint `https://api.openai.com/v1/responses`; redirect запрещён, wire stream принудителен даже при non-stream UI; выбирается `ResponsesPolicy.siwc()`, access token поставляет account service. Caller headers фильтруются: нельзя подменить Authorization, Host, Content-Type, Accept, Cookie и Proxy-Authorization. HTTP errors получают provider code, status, `x-request-id` и retryability; quota exhausted, eligibility, capability, authorization scope не считаются временными, некоторые usage-unavailable ошибки временные. `:124-139`: при stream-error после начала body retry запрещён, что предотвращает повторение потенциально исполненного tool-call. `chatgpt_plan_protocol.py:23-48` compatibility facade принимает **не более одного** advertised tool call, требует JSON object arguments и упаковывает результат в application structured segments. Утверждать, что удалённая subscription-схема сейчас поддерживается, по исходникам нельзя.

`chatgpt_plan_auth.py:74-113,132-218`: account store требует Windows DPAPI, файловый межпроцессный lock, distinct signed_in/plan_usage_enabled/usage_state; revoke best-effort, локальные токены стираются и при неудаче remote revocation. `:53-69` валидирует issuer/audience/nonce/expiration/subject. Текущая Windows-привязка — **условие реализации**, а не универсальное функциональное требование Rust Core.

## Общий HTTP и отмена

`http_transport.py:50-77`: default total 240 секунд, local loopback connect 5s против remote 30s, отдельные connect/write/read/pool budgets; payload ≥512 KiB получает увеличенный write timeout. `:94-163`: `httpx.Client` из service registry, ответ запрашивается stream=True даже для non-stream, затем тело дочитывается и закрывается на ошибке; headers-received и cancellable response регистрируются отдельно. `:190-203`: `http2` используется лишь при установленном `h2`, иначе HTTP/1.1; `trust_env=True`, pooling 16/8. `LLMTimeoutPolicy.attempt_deadline` лишь хранит значение; отдельное фактическое deadline enforcement нужно проверять в request runner.

## Функциональные инварианты / требование к Rust (не проектирование)

1. Одна и та же immutable модель запроса и последовательность transforms должны давать проверяемую одинаковую wire-проекцию; не переносить меняющиеся role workaround как общий нормализатор истории.
2. Не смешивать transport failure, HTTP rejection, validation, stream parsing, cancellation и remote quota. Все должны приходить в верхний orchestration с явным исходом и retry disposition.
3. При stream с видимым body нельзя слепо повторять потенциально исполненные операции; cancellation должна закрывать response.
4. Distinguish UI stream vs wire stream; native structured schema vs prompt-guided structured; signed-in account vs capability to send a concrete inference.
5. Зафиксировать goldens для image parts, positioned system blocks, trailing model, multiple candidates, malformed stream, quota/401/429, delayed cancellation, tool calls.

## Статус исследования

**CONFIRMED по коду:** локальные conversion/URL/error/usage/cancellation правила выше. **UNRESOLVED:** remote contract/effective permissions, provider migration snapshots, live streaming behavior; ни endpoint, ни credentials не использовались. Не выбирать окончательную архитектуру на основе этих реализационных деталей.
