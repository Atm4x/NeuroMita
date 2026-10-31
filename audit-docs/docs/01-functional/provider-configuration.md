# API-провайдеры, пресеты, модели и параметры

**Capabilities:** CAP-API-001—005. **Статус:** ACTIVE/CONDITIONAL. Это core configuration/HTTP orchestration, не локальный inference. Runtime retries/tools/structured effects вынесены в отдельные документы.

## Пользовательские функции

| ID | Возможность | Основной путь |
|---|---|---|
| CAP-API-001 | Создать/выбрать/скопировать/переименовать/удалить/упорядочить API preset | ApiSettingsController/mixins → ApiPresetService |
| CAP-API-002 | Настроить endpoint, API key, reserve keys/distribution, fallback chain и модель | UserPreset + ApiPresetResolver; per-character provider inheritance |
| CAP-API-003 | Проверить подключение и получить/обновить model catalog | GET test endpoint либо account action; model metadata normalization |
| CAP-API-004 | Настроить generation parameters, capabilities и protocol transformations | ModelSettingsService/schema + protocol catalog/pipeline editor |
| CAP-API-005 | Сохранить/перенести preset и parameter definition | Controller import/export API и schema repository; GUI reachability отдельных import/export actions ещё уточняется |

Провайдерский template описывает host/protocol/default models/links/редактируемость endpoint. UserPreset содержит credentials и пользовательское состояние. Только пользовательские presets считаются активными generation targets в default selection; template не является настроенным аккаунтом. GUI preset selection для редактирования и application default preset — разные действия. Dirty form при смене предлагает save/discard/cancel; save асинхронный, failed save не снимает dirty state.

## Identity, inheritance и хранение

ApiPresetsController хранит Settings/api_templates.json и api_presets.json, распознаёт старый presets.json и старые ключи; данные template refresh-ятся из code. Имеются migrations конфликтующих IDs/старых model settings; полный migration fixture audit ещё не выполнен. Custom save строит и проверяет candidate, пишет atomic tmp/fsync/replace; при save failure возвращает предыдущий preset/order. Delete и save_state имеют другие error semantics: delete не проверяет _save_presets outcome перед successful event; save_state меняет object до IO и не откатывает его при отказе.

Preset effective projection объединяет template и user fields, schema/defaults/known-models/routing/fallbacks. Ключ и reserve keys сохраняются в обычном preset JSON, API preset export содержит effective key/reserve keys и schema_override. UI mask key не является encrypted storage. OAuth account store — отдельный защищённый механизм, описан в [account-authentication](account-authentication.md).

Application default LAST_API_PRESET_ID может быть переопределён CHAR_PROVIDER_{character}; вспомогательные функции могут выбирать другой preset. ApiPresetResolver фиксирует protocol/provider/dialect, model/key/url/headers/transforms/capabilities/native parameters. Резервные ключи выбираются по attempt либо распределяются round-robin; ordered fallback chain ограничивает глубину/циклы и может переопределить модель fallback preset. Эти policies уже описаны в [llm-requests](../03-runtime/llm-requests.md); новая система должна сохранить результат, не текущие mutable settings structures.

## Проверка подключения и модели

UI использует отдельный test URL, проверяет HTTP(S); отсутствие test endpoint не запрещает generation в Sandbox. Для API-key provider controller строит auth/headers через ProtocolBuilderService и делает GET (обычно endpoint списка моделей), timeout15 s либо30 s для OpenRouter. HTTP200 JSON может означать connection success даже без обнаруженных моделей. Это не пробная генерация и не доказательство поддержки structured/images/tools.

Model entries нормализуются из provider payload: id/name/context length/pricing/rate limits/host data; могут фильтроваться по template. Каталог хранится в preset. Unknown/missing models не равны отсутствию доступа к ручному model id. Фактические units/актуальность remote metadata не проверены сетью. Некоторые entries/code содержат project-specific synthetic/easter-egg model metadata: нельзя трактовать весь каталог как независимую фактическую спецификацию внешних моделей.

Account provider вместо key/test endpoint использует sign-in/add/select/sign-out/list_models. GUI защищает поздний account status callback serial/protocol check; model catalog failure может оставить signed-in account и предложить отдельное обновление списка. Credentials/account readiness и готовность конкретной model capability различаются.

## Протоколы и параметры

Registered dialects: OpenAI Chat Completions, OpenAI Responses, Gemini generateContent. Protocol catalog связывает dialect с provider/auth/transforms и проектными capabilities. В нём есть generic compatible, OpenRouter/Mistral/LM Studio/Ai.iO/Google/Responses/ChatGPT Plan profiles. Это настройки приложения, не подтверждение актуальных возможностей удалённого сервиса. Изменять transforms можно только при разрешённой template policy; полностью custom preset может переопределять headers/capabilities.

ProtocolBuilderService делает bearer/query/no-auth, template headers+extra headers, URL key substitution. Credentials не создаются magic SDK. Common/Responses/Gemini providers используют общий HTTP transport и собственные serializers/parsers. HTTP/2 через optional h2, иначе HTTP/1.1; per-service pool, environment proxy handling, connect/read/write/pool timeouts, более длинный upload budget для больших payloads. LLM request cancellation регистрирует response как cancellable resource. Полная транспортная отмена/abandoned thread semantics — в llm-requests.

Chat Completions provider при отказе response format может повторить запрос с более мягким format, если capability разрешает. Responses API имеет отдельный adapter и native tool/history contract; ChatGPT Plan принудительно wire-stream даже при иной UI presentation. Gemini сериализует system/content/images отдельно; полные request/stream/usage branches ещё требуют окончания protocol-прохода. Не считать их завершёнными на основании каталога.

ModelSettingsService использует document version1 с schema_id, values, enabled, optional schema_override/support flags/sparse setting. Schema определяет dialect, revision, fields/defaults/constraints и пути native parameters. Types boolean/integer/number/string/array/object, finite numbers, ranges/length/enum, exclusive groups. Только enabled parameters входят в compiled payload; protected roots запрещают подменять model/messages/tools/stream/auth/schema как «параметр генерации». Gemini paths ограничены generationConfig без response schemas.

SchemaRepository объединяет builtin definitions и Settings/APIModelSchemas JSON overrides, проверяет revision/dialect, дубликаты external ID; одна malformed definition может остановить чтение каталога с SchemaError. Import/export и preset-local customization существуют; change_schema переносит значения по совпавшим field IDs. Эта функция позволяет добавлять новые model parameters без изменений HTTP provider code, в пределах допустимых paths. Она основана на собственном JSON schema compiler, а не полном исполнении произвольного Python.

Protocol transforms меняют roles/order/merging перед wire encoding: merge systems, positioned system-to-user, trailing context, alternating roles, ensure last user и другие registered steps. Есть список/параметры/trace before-after, GUI pipeline configuration. Unknown transform пропускается с trace reason. Все implementation details transforms/GUI editor ещё не закрыты; они являются отдельными observable request projections, а не косметикой UI.

## Требования и граница зависимости

Нужны typed preset/template/protocol/model/schema identities, фиксированный request snapshot, валидируемые generation parameters, честные capability/readiness states, отдельные credential stores и видимые persistence failures. Endpoint verification/model catalog/inference request — разные операции. Import/export должен иметь определённый scope credentials и source references. Provider profiles/transforms должны быть reviewable/testable по wire artifact.

По исследованным active paths HTTP clients и форматы реализованы без обязательного SDK каждого provider. Наличие mistralai/nodriver/google-cloud-storage в requirements само по себе не доказывает их участие: поиск src в этом проходе не нашёл production imports этих пакетов. Полный dependency import graph/транзитивность ещё не завершены. Rust alternatives будут сравниваться по функциям HTTP/SSE/schema/crypto/secret storage, не по совпадению названий SDK.

## Доказательства и пределы

Прочитаны ApiPresetsController по initialization/effective projection/save/delete/import/export/test/model/state/current; ApiPresetResolver resolve/chain/rotation; API GUI dirty/save/copy/rename/delete/order/test/account branches; protocol catalog/controller, native tool policy; ModelSettingsService целиком, Schema parse/validate/compile и definition ranges, repository основной catalog/write; LLMHttpClient, Common/Responses provider и OpenAIHTTP generate основной flow. Gemini/transform/full migrations/UI parameter editor остаются с gaps. Пользовательские credentials/settings не открывались, provider requests/login/import/export не выполнялись.
