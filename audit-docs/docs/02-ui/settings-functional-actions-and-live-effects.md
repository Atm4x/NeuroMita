# Настройки: пользовательские действия и live effects вне привязки к QWidget

**Цель:** разделить отображаемые поля, live-подписки, команды и функции Core. Список берётся из активных секций `src/ui/pages/settings/section_registry.py:15-173`. Это дополнение к [navigation](settings-navigation-and-lazy-pages.md) и [key consumer evidence](settings-key-consumer-evidence.md), **не** целевая структура GUI на Rust.

## CAP-UI-ACTION-001 — карта 12 зарегистрированных секций

| Section | Возможности пользователя (подтверждённые источниками) | Характер изменения |
|---|---|---|
| `general` | Выбор видимых разделов settings и панелей Sandbox; приватная маска ключей; локальный TCP IPC toggle/port; оформление chat bubble/size/timestamp; видимость thinking/system/cost; memory profile | Section visibility и Sandbox panels меняются live; privacy является маскированием UI, **не** шифрованием/подавлением network; IPC сервер пересобирается от settings change. `src/ui/settings/general_settings.py:97-322` |
| `language` | Переключение LANGUAGE, локализация, включение собственных translations | Локаль меняет UI; first-run language flow отдельно. `src/ui/settings/language_settings.py:54-118`; [first run](first-run-agreement-language-and-guide-flow.md) |
| `api` | Выбор, создание, копирование, импорт/экспорт, проверка API preset; протокол/endpoint/model, secrets, model parameter schema и discovery | UI preset state → provider settings; проверка сетевого API отдельно; export может включать credentials. `src/ui/settings/api_settings/`, `src/controllers/api_presets_controller.py` |
| `characters` | Выбор настроечного персонажа, prompt-set, provider, настройка данных персонажа, очистка истории/памяти, миграции, dedup, reindex, backup import/export | Settings-selected character **не обязан** совпадать с активным chat character; maintenance запускает асинхронные действия. `src/controllers/gui/character_settings_logic.py:515-2294` |
| `voice` | Выбор voice method/backend, локальные и remote presets, прослушивание/инициализация, RVC/voice assets | Условно доступно после подготовленных Python AI features; remote и local маршруты различаются. `src/ui/settings/voiceover_settings/`; [voice](voice-controls.md) |
| `microphone` | ASR backend/model, физическое устройство/канал, PTT и диагностика/monitor | Локальное audio routing; inference модели условно в Python worker. `src/ui/settings/microphone_settings/`; [ASR](asr-model-gallery-and-settings-workflows.md) |
| `ai_engine` | Обновить hardware snapshot, открыть AI Hub, выбрать shared/split и **отдельно применить**, удалить AI environments через подтверждение | Selector отражает pending выбор; apply запрещён во время busy или при env override; reset затрагивает `Lib/environment`, не `Lib/core`. `src/ui/settings/ai_engine_settings.py:208-260,303-463` |
| `game` | Вкл/откл игровые запросы, мини-игры Chess/SeaBattle, Beat Sync backend и cache | Settings + explicit manual game launch/Beat prep; не все игровые действия — UI options. `src/ui/settings/game_settings.py:417-574`; [games](game-settings-manual-launch-and-beat-cache.md) |
| `models` | Раздельные prompts, retries/timeouts, streaming, schema reasoning, tools, React L2, memory/graph/RAG sections | `TOOLS_ON` gate и per-tool flags; tool result injection mode `both/system/user`; react L1 **не представлен** активным UI. `src/ui/settings/model_interaction_settings.py:6-190` |
| `screen` | Скриншоты рабочего стола, webcam, Unity camera, качество, TTL, события image-description | Источник кадров и последующие LLM-модальности различаются; [capture](screen-camera-image-management-user-contracts.md). `src/ui/settings/screen_analysis_settings.py:23-492` |
| `updates` | Проверить Python/Unity, выбрать канал, обновить, продолжить pending installation, видеть restart/relaunch | Информационный check и применение update — разные сценарии, Python и Unity обновляются отдельно. `src/controllers/gui/updates_settings_controller.py:39-715` |
| `data_collection` | Включить fine-tune capture; рейтинг сообщений; лимит/без лимита; directory picker, просмотр записей, экспорт/очистка | Изменение ограничения может немедленно запускать `EnforceFineTuneLimit`; export Raw/ShareGPT отдельный UI dialog. `src/ui/settings/data_settings.py:90-320` |

## CAP-UI-ACTION-002 — детали, которые легко потерять при портировании интерфейса

### `general`: динамические поля вместо статичного списка

`_build_section_visibility_config` и `_build_sandbox_panels_config` собирают controls из **реестров**, а не из 10 постоянных JSON key (`general_settings.py:60-132`). Изменение visibility влияет на навигацию/панели текущей страницы без перезапуска. `RUNTIME_IPC_ENABLED` и `RUNTIME_IPC_PORT` — самостоятельные параметры; порт валидируется `1024..65535` и доступен при включённом сервере (`general_settings.py:185-225`). `HIDE_PRIVATE` маскирует Telegram/Google keys только при отображении; приватность хранения — другая область (`:162-183`).

### `models`: policy LLM/Tools/React

`model_interaction_settings.py:19-126` разделяет attempts/count, timeouts, streaming, schema CoT, tool gate, шесть per-tool flags (calculator, web_search, google_search, web_reader, memory_search, reminder), max depth и результат tool-role `both/system/user`. `:140-190`: React L2 имеет отдельный enable/provider; React L1 отключён из активного settings UI (комментарий и runtime flag не делают его пользовательской операцией). Запросы с пользовательским входом и реакция на внешнее событие — разные sources.

### `ai_engine`: staged mode selector

`ai_engine_settings.py:303-324,379-463` хранит отдельно текущую применённую топологию и выбранный элемент combobox; `Apply` становится доступной, только если выбор действительно отличается, нет busy/override и известна topology. Override `NEUROMITA_AI_ENGINE_MODE` исключает ручное применение. Удаление AI окружений требует подтверждения, и кнопка не означает мгновенное освобождение работающих worker. Это два разных use case: mode switch и environment reset.

### `data_collection`: policy немедленного ограничения

`data_settings.py:90-200`: включение сборщика, показ rating controls, `FINETUNE_MAX_RECORDS`, `FINETUNE_UNLIMITED`. При уменьшении лимита без unlimited запускается `EnforceFineTuneLimit` (`:172-187`), то есть UI change может иметь storage side effect немедленно; это не только preference. Выбор directory, open export dialog и clear имеют самостоятельные confirmation/worker lifecycles (`:210-320`; [fine tuning](../01-functional/fine-tuning-data-capture-curation-and-export.md)).

### `sandbox.debug`: отдельная capability, не general settings

`src/ui/settings/debug_settings.py:43-183`: выбор `SHOW_STRUCTURED_IN_GUI` (Off/Brief/JSON), `STRUCTURED_EXPANDED_DEFAULT`, `REMOTE_ONLY_STRUCTURED_FIELDS_EXCLUSION_ENABLED`, debug insert system message (либо user с `[Системное]:`), save/load snapshot, просмотр последнего request/response, capture ingress `GENERATE_RESPONSE`. Эти действия доступны из Sandbox, а не из 12 settings categories. Данные генерации/контекст доступны для диагностики, но не должны смешиваться с сохраняемой историей как неподписанные system entries.

## REQ-UI-ACTION и контроль полноты

- `REQ-UI-ACTION-001`: сохранить все двенадцать зарегистрированных групп и активные direct actions без копирования Qt widget tree.
- `REQ-UI-ACTION-002`: различать `read setting`, `edit locally`, `apply command`, `await runtime status`, `persist` и `rollback UI on error`.
- `REQ-UI-ACTION-003`: dynamic key groups строить из реестра, а не из зафиксированного списка литералов; consumer/provenance должен быть привязан к capability.
- `REQ-UI-ACTION-004`: privileged/destructive actions (reset/delete/export credentials, changes in data collection) должны отличаться от harmless preference switches по сценариям подтверждения и последствиям.
- `REQ-UI-ACTION-005`: дополнять matrix Qt E2E/keyboard/accessibility, но не выбирать Slint/Qt на этапе функционального аудита.

**Что ещё не доказано:** полный one-to-one перечень *каждого* вложенного custom widget/диалога (особенно voice, RAG и API dynamic schemas), keyboard shortcuts, live behaviour на Windows. Этот документ делает явной функциональную поверхность всех зарегистрированных секций, но **не подменяет** исчерпывающие tests по каждому control.
