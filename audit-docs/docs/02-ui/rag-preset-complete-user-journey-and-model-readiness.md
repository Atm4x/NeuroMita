# RAG Presets: полный пользовательский путь от выбора до проверки моделей (Pass 12)

**Статус:** ACTIVE GUI path для Settings/RAG, с CONDITIONAL выходом в инсталлятор моделей. **Источники:** `src/ui/settings/rag_preset_widget.py:34-186`, `src/ui/settings/rag_preset_presentation.py:9-84`, `src/controllers/gui/rag_preset_view_model.py:37-245`, `src/managers/rag/pipeline/config.py:20-121`, `src/managers/rag/install_spec.py`. Это функциональный контракт, не проект ViewModel Rust.

## CAP-RAG-PRESET-001 — что является пресетом

Встроены **четыре** pipeline preset (`managers/rag/pipeline/config.py:29-75`):

| Preset | Эффекты на механизм поиска |
|---|---|
| `Keyword+FTS only` | keyword и SQLite FTS; vector, reranker и graph disabled |
| `Keyword+FTS+Inline Graph` | FTS/keyword плюс inline graph extraction и графовый поиск; vector/reranker disabled |
| `Vector+FTS (Qwen3 0.6B)` | включён vector search с Qwen3 Embedding 0.6B, keyword+FTS, reranker disabled |
| `Vector+FTS+Reranker (Qwen3)` | vector+keyword+FTS, cross-encoder Qwen3 0.6B, two-stage combine, top K 75, alpha 0.68 |

Пресеты содержат **частичные словари** настроек: применение не обязано сбрасывать все остальные значения RAG к default. Список в combo объединяет встроенные, пользовательские и специальный `Custom`. `Custom` — индикатор непредопределённой конфигурации, его нельзя применять или удалить как persisted template. Библиотека отдельно реализует `match_pipeline_preset` для распознавания текущей конфигурации по значениям, даже если выбран `Custom` (`config.py:98-121`); UI state и распознанный pipeline — разные представления.

## CAP-RAG-PRESET-002 — сценарии и переходы

| Действие пользователя | Переход и данные | Последствия / отрицательная ветвь |
|---|---|---|
| Открыть RAG-настройки | `ActivateRagPresets` → загрузка встроенных и `RAG_PIPELINE_USER_PRESETS` из JSON | Из `RAG_PIPELINE_PRESET` формируется `selected`; неизвестное имя превращается в `Custom` |
| Выбрать имя | `SelectRagPreset(name)` → запись ключа `RAG_PIPELINE_PRESET` → обновление UI | **Сам выбор** не переписывает настройки всех pipeline ключей; для этого требуется Apply |
| Применить | `RequestApplyRagPreset` → `ConfirmApplyRagPreset` | Модальное окно имеет **три** действия: Apply / Save current & Apply / Cancel, default Cancel |
| Save current & Apply | Ввод имени сохранения → `ApplyRagPreset(name, save_current_as=saved)` | Сначала сохраняется snapshot текущих `RAG_DEFAULTS` в user-preset JSON; только после успешного сохранения применяется выбранный пресет |
| Apply | `ApplyRagPreset(name)` → `get_pipeline_preset_settings` → `settings.update()` для каждого ключа → записывает selected preset | Если затронута embedding модель/производные ключи, выполняется `sync_legacy_settings_to_preset` для совместимости |
| Save As | Имя в `QInputDialog` → `SaveRagPreset(name)` | Сохраняет snapshot всех `RAG_DEFAULTS`, включая допустимые `None`, в `RAG_PIPELINE_USER_PRESETS`; выбранное имя обновляется |
| Delete | `RequestDeleteRagPreset` → `ConfirmDeleteRagPreset` → `DeleteRagPreset` | Удаляются только пользовательские; встроенные и `Custom` защищены, выбранное сбрасывается в `Custom` |
| Применение с отсутствующими моделями | `busy=True` + `run_latest('rag-preset-model-status', missing_model_targets)` → `OfferMissingRagModels` | При Yes выполняется `InstallMissingRagModels`, постановка соответствующих targets в installer; при No выбранные настройки уже применены, готовность моделей не подменяется install success |

`RagPresetState` явно содержит `names`, `selected`, `can_apply`, `can_delete`, `busy`, а GUI блокирует действия при `busy`; `SettingsService.subscribe` refresh через `_post_ui` поддерживает изменения, внесённые другим участком приложения (`rag_preset_view_model.py:45-119`). Ошибка чтения JSON пользовательских пресетов приводит к пустому набору в UI; это граница наблюдаемой функции без обязательного расследования старого кода.

## CAP-RAG-PRESET-003 — чем «выбран» отличается от «готов»

1. Пресет фиксирует значения retrieval-параметров и модельных ID. Он **не устанавливает** embedder/cross-encoder синхронно.
2. После Apply запускается отдельная проверка отсутствующих HF-артефактов. Это асинхронная операция, в которой latest-result ownership не должен позволять старому результату перезаписать новую selection state.
3. Инсталляция отсутствующих target выполняется через очередь отдельно от сохранения пресета. Наличие карточки и статус installed/ready — не одно значение.
4. Использование RAG в конкретном диалоге подчинено независимо включению retrieval, лимитам и конкретному character scope; UI Apply не является доказательством успешного ответа LLM с найденным контекстом.

## Обязательные требования к новому продукту

- `REQ-RAG-PRESET-001`: сохранить четыре встроенных режимa и пользовательские snapshot presets с partial settings semantics, не переносить устаревший Python контроллер или его структуру.
- `REQ-RAG-PRESET-002`: выбрать имя, сохранить текущие значения, применить к активным настройкам, удалить пользовательский preset — четыре разные операции; built-in и `Custom` не удаляются/не перезаписываются.
- `REQ-RAG-PRESET-003`: модальное действие Apply имеет ровно три исхода: Apply, Save current & Apply, Cancel; не считать Confirm success окончательной готовностью моделей.
- `REQ-RAG-PRESET-004`: после применения проверить отсутствующие модели и предложить **добавление в очередь**, показывая перечень; отказ от загрузки не эквивалентен отказу применить настройки.

## Evidence и валидация

Адресный offline test: `PYTHONPATH=src python -m pytest -q src/utils/Testing/test_rag_preset_view_model.py` → **4 passed** (2026-10-31 UTC). Проверены built-ins listing, сохранение nullable значения, применение pipeline с synchronised stub для status и сброс в `Custom` после удаления. **Не тестировались в этом прогоне:** настоящий Qt modal, интеграция с installer, скачивание HuggingFace модели, GPU inference, параллельные изменения settings.

Связано: [реестр RAG UI-параметров](memory-rag-registered-settings-source-index.md), [протокол очереди AI install](../01-functional/installable-component-probe-and-operation-contracts.md), [retrieval](../01-functional/rag-query-fusion-reranking-and-result-contracts.md).
