# AI Hub: наблюдаемое поведение GUI

Статус: ACTIVE, частичный screen audit. Это описание существующих сценариев, не выбор UI framework для новой системы. [Backend установки](../01-functional/installations.md).

## Навигация и действия

Категории: TTS, голоса персонажей, ASR, RAG, extras/beat synchronization, системное ядро, зависимости. Есть tabs install/settings, текстовый поиск и backend filter all/CUDA/ONNX/CPU. CPU/none cards остаются под любым filter. Поиск включает id/title/description/backend/tags/languages/status message. Supported и ready cards сортируются раньше unsupported. Язык labels вычисляется при render, диалог умеет обновлять локализацию без пересоздания.

Card поддерживает install/update, clean reinstall, uninstall, open settings. Unsupported install запрещён; not recommended спрашивает подтверждение с warning. Clean reinstall спрашивает удалить и скачать заново; uninstall — подтверждение удаления файлов/зависимостей. Из уже занятых компонентов повторное действие блокируется; занятость другим компонентом разрешает enqueue. Нажатие install оптимистично показывает queued до backend admission; ошибка admission отображается в install window.

Если required backend отсутствует, preview confirmation показывает component, hardware, backend, packages и возможность перейти к системному ядру. TTS install может показать one-time voice-assets hint; модель движка и голос персонажа устанавливаются отдельно. В диалоге доступны очистка installer cache, открытие models folder, progress/logs и очередь с cancel queued/running. Реальное открытие folder здесь ещё не проверялось.

## Асинхронные состояния

Первая загрузка может показать metadata без status, затем запускается status pass. Refresh coalesced; UI timeout20s снимает бесконечный spinner, но не гарантирует остановку backend probe. Transient statuses показывают checking и ждут COMPONENT_STATUS; отдельный UI fallback120s убирает checking. Installed event инвалидирует соответствующий компонент, затем запрашивает статусы с возможностью использовать cache остальных. Finished progress100% кратковременный, error оставляет результат для чтения. Queue state содержит running/pending.

App backend readiness и optional installables готовятся перед action; wait backend≤15s и ensure feature≤60s. Это не permission prompt пользователя: обычное ожидание readiness. Admission accepted отображается как queued либо already queued; завершение приходит отдельными events.

## Настройки модели

Settings list включает installed/ready rows текущей категории. Выбор загружает schema/values через run_latest, stale load не должен заменить новую форму. Form имеет loading/load_error/empty/dirty/saving/saved/field errors. Save вызывает catalog validation; failure сохраняет edited values. Reset формы означает вернуть last saved values, не factory defaults. Background row refresh сохраняет dirty form, если компонент остаётся в той же категории.

Навигация category/tab/component и закрытие проверяют unsaved changes; Discard/Cancel, default Cancel. Native hide-on-close тоже проходит эту проверку через confirm_hide_on_close. В SettingsPanel dirty учитывается по form и viewmodel, чтобы delayed signal не терял изменения. При saving смена component блокируется.

Для Fish Speech+ medium+/medium+low есть compile, delete compilation, cache size/metadata/compiled target status и documentation link. Compile может сначала сохранить unsaved device settings, дождаться installables/voice_models readiness, затем запустить операцию; clear-only не требует этих values. Фактические compile backend steps ещё не изучены. Compile completion сопоставляется по model_id и обновляет status.

## Источники и остаток

Прочитаны AIHubViewModel основной файл, AIHubSettingsViewModel целиком; dialog navigation/filter/close/preview/prepare/cancel paths; SettingsPanel unsaved handling; widgets card actions/busy/menu confirmation; constants. Остальные layout/render/queue popup/settings schema renderer, compile backend, integration с WindowManager и тесты GUI не завершены. Визуальный runtime QA не выполнялся. По этому экрану ещё нельзя выбирать Slint/QML: остаются richer widgets, accessibility, localization и другие экраны приложения.

## Pass 13: schema form → component settings outcome

Уточнён route `SchemaForm._fire_change/values` → SettingsPanel intent → AIHubSettingsViewModel → presentation catalog facade → `InstallableCatalogService.save_component_settings` → configurable component. Sources: `ui/windows/ai_hub/schema_renderer.py:118–166,242–360,450+`; `settings_panel.py:398–456`; `ai_hub_settings_view_model.py:48–241,371–420`; `presentation_hub.py:936–943`; `installable_catalog_service.py:545–617`.

- Form собирает значения по schema keys как строки; checkbox/combo/number widgets не делают весь payload строгой domain schema. Locked/enabled и dependent behaviors применяются в renderer; изменение поля обновляет draft/dirty, не вызывает durable component save.
- Save допускается только при selected component, dirty и not saving. `run_exclusive` вызывает catalog save; success обновляет saved_values/dirty/revisions; failure сохраняет draft и раскладывает errors по полям, `_` — global warning. При exception есть отдельный save_failed outcome.
- Catalog ищет configurable component по реальному registry ID, нормализует setting behaviors, валидирует voice devices и optional component.validate_settings, затем вызывает component.save_settings и invalidate(component_id). Это не эквивалент загрузке модели или проверенной inference readiness.
- Schema/load service ловит exception и возвращает []/{} с log. Поэтому empty/no-settings state может означать также swallowed service error; нельзя обещать, что любой storage/loader failure всегда отображается load_error формы.
- **load_settings может записать миграцию:** migrate_voice_device_values сравнивает сохранённый device selection и при изменении вызывает component.save_settings. Открытие страницы не всегда строго read-only для storage. Это отдельно от явного Save draft.
- Reset/Discard возвращает saved snapshot формы, не factory defaults. Same-category catalog refresh сохраняет dirty draft пока selected ID остаётся в списке; component switch при saving отклоняется. Missing component/category change имеет другой path, его live delayed-result сценарии требуют Qt fixture.

Compile/clear ownership и actual initialization теперь уточнены в [per-family матрице](../06-design-input/installables-component-by-component-parity-matrix.md), а WindowManager/skip outcomes — в [modal callback follow-up](dialog-class-reachability-and-action-outcomes.md). Это закрывает прежние source вопросы об этих основных branches, но не UI/hardware E2E.

`REQ-HUB-SETTINGS-001`: draft, validation, storage result и model runtime application различимы; user-facing save errors не теряют draft. `REQ-HUB-SETTINGS-002`: открытие/миграция, Reset to saved, component/category switch, catalog refresh и pending async load имеют определённые эффекты. Будущие проверки: разные schemas/types, invalid device, per-field/global errors, swallowed load failure, delayed response, dirty refresh и missing selected component. В Pass 13 GUI не запускался.
