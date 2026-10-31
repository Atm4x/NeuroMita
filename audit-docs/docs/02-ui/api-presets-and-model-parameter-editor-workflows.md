# API-пресеты: пользовательские операции, каталог моделей и редактор параметров

**Scope:** ACTIVE GUI workflows, условно доступные провайдеры/учётные записи. Срез Python `releases` 38172493. Источники: `src/controllers/gui/api_settings/`, `src/ui/settings/api_settings/`, `src/services/` API; это **описание функций**, не предложение сохранять PyQt-контроллеры.

## Пресеты и независимые идентичности

Пользователь работает с двумя разными сущностями: **provider template** (протокол, стандартные поля и возможности) и **custom preset** (собственное имя, URL, модель, ключи, параметры, fallback/routing). Выбор строки пресета для редактирования не равен смене активного global/character provider для генерации. `ApiSettingsController` хранит выбранный `current_preset_id`, загруженную копию, dirty snapshot, async serial для reload и `_pending_select_id` для выбора после save: `src/controllers/gui/api_settings/controller.py:24-71`; `presets_mixin.py:31-336`.

Поддерживаются создание из шаблона, копирование, переименование, удаление, перемещение вверх/вниз, drag reorder, выбор, редактирование и сохранение. `controller.py:140-176` содержит прямую привязку actions; `editor_mixin.py:492-753` — операции и async persistence. `NewPresetDialog` принимает имя и template и проверяет введённые значения (`src/ui/settings/api_settings/dialogs/new_preset_dialog.py:11-100`). Функционально важны persisted ID/order, template inheritance, original-vs-editing snapshot и независимая default selection.

## Правки, dirty state и сохранение

Поля редактора: имя, endpoint, URL проверки, модель, API key/visibility, резервные ключи и распределение, привязка к provider/template и protocol, per-preset model parameters, OpenRouter routing, ordered fallbacks, protocol overrides/transforms. `src/controllers/gui/api_settings/editor_mixin.py:30-162,208-363`; `controller.py:143-180`; [core configuration](../01-functional/provider-configuration.md).

Редактор держит `_snapshot` сохранённого состояния, а не отправляет изменения HTTP-клиенту при каждом вводе. «Отмена» восстанавливает срез: имя, URL, model, credentials, reserve keys, template/protocol, per-model settings, routing и fallback chain (`editor_mixin.py:438-490`). «Сохранить» сначала проверяет model form, формирует новый payload и асинхронно отправляет в `ApiPresetService.save_custom`; при успехе обновляет имя/модель в списке, snapshot, снимает dirty, выполняет ранее отложенный переход (`:492-532`). Ошибка validation не должна быть принята за сохранённые настройки. Дополнительные confirmation/dirty branch при смене пресета: `presets_mixin.py:145-335`.

Наличие fallback chain в preset означает выбор **запасного пресета при определённой ошибке**; сам интерфейс цепочки не гарантирует, что два провайдера были вызваны для одного сообщения. Runtime response и rotation описаны в [LLM request lifecycle](../03-runtime/llm-requests.md).

## Проверка подключения и каталог моделей

Пользователь может отдельно: проверить credentials/test URL, открыть список моделей, выбрать модель для поля preset, а для account-based protocol — открыть окно аккаунтов и запросить модели под выбранной авторизацией. Эти действия живут в `src/controllers/gui/api_settings/test_mixin.py:15-214`, а не в generation request. `ModelsLoadedDialog` получает нормализованные модели и metadata, позволяет фильтровать/сортировать видимые строки и показывает при наличии контекстное окно, тип free/paid, pricing, rate limits, latency/tokens-per-second (`src/ui/settings/api_settings/dialogs/models_loaded_dialog.py:38-116,288-465`). «Использовать» возвращает выделенный **model id**, а «Копировать» записывает TSV текущей видимой таблицы в clipboard (`:467-492`). UI model metadata может отсутствовать или устареть; тест HTTP200/model listing не подтверждает полноценную генерацию.

Различать `account identity`, `preset identity`, `model identifier`, `provider protocol`, `catalog metadata` и `selected current row`. В списке моделей сортировка цены/лимитов использует числовые сортировочные значения, показ цены — отдельный формат; пустые metadata не следует заполнить придуманными числами. Все remote API данные в этом проходе анализировались только как код обработки, реальных подключений не было.

## Редактор модельных параметров (schema declaration)

`ModelSettingsForm` загружает schema и per-preset document, показывает поля по типам/ограничениям и их enabled/values; формирует документ и сообщает validation issues (`src/ui/settings/api_settings/model_settings_form.py:68-289`). В отличие от этого, `ModelParametersDialog` редактирует **само определение полей** только у данного пресета, не изменяя его wire dialect. Представления: список полей, индивидуальный редактор, JSON-редактор всего определения (`src/ui/settings/api_settings/dialogs/model_parameters_dialog.py:21-105`). Поддерживает add/remove, название/описание на языке редактора, path с точечной нотацией, тип `number|integer|boolean|string|array|object`, default, numeric min/max, JSON enum (`:105-245`). Перед сменой выделения commit выполняется с validation; несовместимое значение удерживает старую строку. Для Gemini `generationConfig` добавляется к path, но в UI скрывается (`:129-185`). Save отдаёт валидированное определение, Cancel — без записи.

Это означает **два контракта**: настройка значения/включённости конкретного параметра и декларация нового допустимого параметра. Сохранённая декларация должна отдельно проверяться на запрещённые wire roots, типы, диапазоны, особенности dialect; UI не является источником последней безопасности. Подробные compiler constraints: [provider configuration](../01-functional/provider-configuration.md).

## Редактор message pipeline

Кнопка protocol processing открывает одноразовую рабочую копию `base_transforms/current_transforms/catalog`, позволяет переставлять transform stages и применить только после Apply. Protocol catalog диктует, доступно ли изменение pipeline. Описание dialog и отличие `base` от `initial` — [dialogs](dialog-interaction-and-background-task-contracts.md); wire result — [message transforms](../01-functional/message-transforms.md). Не сводить transformation pipeline, model-parameter schema и fallback chain в одну настройку: они действуют на разных этапах обращения к модели.

## Состояния и внешние эффекты

`idle → loading preset → editing/dirty → validating → saving → saved|failed`; отдельно `test loading → connection result|error`, `model catalog loading → models table|error`, `account sign-in → account status|failure`. Асинхронные операции должны предотвращать подмену выбранного пресета поздним результатом старого запроса. Для генерации используется сохранённый effective projection, а не произвольный partially edited QWidget state. Экспорт/импорт presets и пользовательских model schemas документируются как core functionality; наличие конкретной кнопки для каждого из них в GUI отдельно требует reachability proof.

## Future parity checklist

Создание/копирование/rename/delete/reorder с сохранением ID; смена выбранного пресета при несохранённых полях; async-save и последующий pending selection; отсутствие key masking как псевдошифрования; независимая работа test URL; аккаунты и model list; filter/sort/copy/choose catalog; редактирование values и metadata schema; JSON validation; Gemini path mapping; non-editable template; pipeline add/reorder/apply/cancel; fallback/routing; человеческие сообщения о недоступных credentials.

**Не проведено:** графический E2E в Qt, подключение к API, авторизация, фактический import/export через GUI. Не следует считать эти кейсы закрытыми тестами только на основании текущей статической спецификации.
