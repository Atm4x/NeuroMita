# Диалоговые окна: подтверждённая достижимость и результаты действий (Pass 12)

**Назначение.** Отделить существование `QDialog`-класса от открываемого пользовательского сценария, а закрытие окна — от завершения операции. Исследована ревизия Python из `CodeNow.zip`; Qt UI и Windows установки не запускались. Статический проход AST охватил 717 Python modules в рабочем `src`, исключая `Lib`, `utils/Testing`, `ui/not_used`.

## CAP-UI-DIALOG-001: WindowManager как пользовательский диспетчер окон

`src/ui/window_manager.py:16-40,61-102,109-130,132-225` хранит конфигурацию для каждого `window_id` (`factory`, `singleton`, `hide_on_close`, `modal`, `on_ready`). Показ/закрытие по сигналам маршалятся в Qt-thread. Повторное открытие singleton использует сохранённый экземпляр, вызывает `on_ready` для нового payload и поднимает окно; hide-on-close не разрушает состояние. Guard `confirm_hide_on_close` позволяет редактору отменить закрытие с несохранёнными данными. Blocking-показ выполняет `exec`, возвращает `choice` при наличии `get_choice`; **это не общий IPC или бизнес-результат любой операции**.

Основной список из `src/controllers/gui/window_composition_controller.py:35-53` (шесть окон):

| window_id | Создание и смысл | Режим, источник |
|---|---|---|
| `ai_hub` | `AIHubDialog` — установка и управление компонентами | singleton, hide, modeless; `:75-88,140-145` |
| `voice_models` | контейнер для панели локальных голосов | singleton, hide, modeless; `:89-96` |
| `asr_glossary` | контейнер моделей распознавания речи | singleton, hide, modeless; `:98-104` |
| `guide` | GuideDialog, смена уровня/раздела/фокуса | singleton, hide, modeless; `:106-120` |
| `vc_redist_dialog` | запрос решения о компонентах Visual C++ Runtime | новый modal каждый раз, blocking; `:122-129`, `src/controllers/gui_controller.py:117-126` |
| `triton_deps_dialog` | предупреждение, opt-in к компиляции Triton/Fish Speech+ | новый modal каждый раз, blocking; `:130-139` |

Седьмой `window_id=protocol_pipeline` регистрируется отдельно контроллером `src/controllers/gui/protocol_pipeline_gui_controller.py:14-44`. В runtime factory использует **`MessageProcessingDialog`**, не одноимённый класс `ProtocolPipelineDialog`. Источник события: `src/controllers/gui/api_settings/controller.py:233-280` → `Events.GUI.SHOW_WINDOW` → `src/controllers/gui/window_manager_controller.py:23-30`. Политика доступа: `pipeline_editable`, протокол и каталог transforms; Apply записывает локальный override и отмечает изменённые поля редактора, **не означает отправку сетевого запроса или мгновенный durable commit**.

## CAP-UI-DIALOG-002: классы QDialog с прямым конструкторным свидетельством

Обнаружено 20 наследников `QDialog`/классов с `Dialog` в базе (синтаксический фильтр; не утверждается полнота всех QWidget-based overlays или `QMessageBox`). Из них 17 имеют прямые вызовы собственных конструкторов в пределах выбранного сканирования; исключение `StyledMessageDialog` создаётся фабрикой в своём модуле и включено в эти 17. Два определены, но **не имеют прямых конструкторных вызовов** (`NewPresetDialog`, `ProtocolPipelineDialog`); `VoiceActionWindow` также не имеет такого вызова. Остальные функции могут создавать обычный `QDialog` без именованного наследника — настоящий all-window gate потребует дополнительной проверки.

| Класс / окно | Подтверждённый caller | Пользовательский результат / граница |
|---|---|---|
| `AIHubDialog` | `window_composition_controller.py:82` | component commands через intent, отдельная очередь и readiness |
| `BackgroundTaskDialog` | `character_settings_logic.py:1830` | наблюдение/запрос отмены долгой операции, не её гарантированная остановка |
| `ContextViewerDialog` | `app_window_base.py:382` | read-only snapshot входов LLM, не изменения persisted dialogue |
| `DbExportDialog` | `character_settings_logic.py:2142,2151` | параметры выбранного/all-character JSON export до worker |
| `DbViewerDialog` | `character_settings_logic.py:1518,1522` | просмотр и ручное редактирование World.db, отдельный контур изменения данных |
| `ExportDialog` | `data_settings.py:423` | экспорт fine-tune samples, **не** World.db |
| `GalleryViewer` | `gallery_page.py:261` | фото/навигация по snapshot выбранных файлов |
| `GuideDialog` | `window_composition_controller.py:107` | walkthrough/locale/deep-link |
| `MessageProcessingDialog` | `protocol_pipeline_gui_controller.py:30` | preview/adjust/reorder protocol message transforms; Apply/Cancel |
| `ModelParametersDialog` | `api_settings/model_settings_controller.py:76` | schema/model parameter edits и validation |
| `ModelsLoadedDialog` | `api_settings/test_mixin.py:176` | каталог обнаруженных моделей + выбор; не сеть в самом диалоге |
| `PromotionDialog` | `modules/Chess/chess_board.py:726` | обязательный выбор фигуры при превращении пешки в шахматах; CONDITIONAL (Chess UI) |
| `StyledMessageDialog` | `ui/dialogs/styled_message.py:91` | отдельная визуальная форма информирования/подтверждения |
| `TritonDependenciesDialog` | `window_composition_controller.py:133` | skip/continue с отдельным подтверждением использования GPU |
| `VCRedistWarningDialog` | `window_composition_controller.py:124` | retry/install/close + документация |
| `VoiceInstallationWindow` | `window_composition_controller.py:150`; `ai_hub/dialog.py:1549` | status/progress/structured log/raw log и reopen; закрытие во время работы скрывает окно |
| `_BackendInstallConfirmationDialog` | `ai_hub/dialog.py:1416` | согласие на план установки backend либо переход на вкладку backend |
| `NewPresetDialog` | нет прямых конструкторных вызовов | **UNRESOLVED/unused UI class**, не требовать без runtime witness |
| `ProtocolPipelineDialog` | нет прямых конструкторных вызовов | не путать с рабочим `MessageProcessingDialog` |
| `VoiceActionWindow` | нет прямых конструкторных вызовов | до выяснения регистрации/вызова **UNRESOLVED**, не считать активной возможностью |

## CAP-UI-DIALOG-003: окна установки как отдельный наблюдаемый workflow

`src/controllers/gui/window_composition_controller.py:147-205` создаёт installation window, маршрутизирует callbacks и открывает его повторно через sidebar `install_logs_requested` (`src/ui/windows/main_window.py:55`, `app_window_base.py:401-402`). `src/ui/windows/voice_action_windows.py:35-245` показывает progress/elapsed/ETA, пакеты, скорость, стадии, диск, обзор и raw output. Показ/скрытие/завершение — разные переходы; закрытие во время установки не является отменой (`_finished`, `finalize`, `closeEvent`). Нельзя без доказательства объединять GUI-host window с очередью установки в один ресурс жизненного цикла.

## Недоказанное и будущие паритетные сценарии

1. Открыть каждый зарегистрированный `window_id` из его фактического действия/события, проверить повторное открытие singleton и восстановление state.
2. Для `protocol_pipeline`: отказ у non-editable template; Apply изменяет pending preset, Cancel сохраняет прежний; output transforms соответствует каталогу и порядку шагов.
3. Для установки: закрытие/повторное открытие логов не прерывает job; terminal completion допускает фактическое закрытие, queue/result не берутся из видимости окна.
4. Для блокирующих voice dialog: разные choices и подтверждение user consent; отсутствие GUI/headless требует иного интерфейса либо документированного ограничения.
5. Дополнить `QMessageBox`/`QInputDialog`/`QFileDialog`, QWidget overlays и dynamic factories, не классифицировать их по одним названиям классов.

**Связано:** [общий dialog lifecycle](dialog-interaction-and-background-task-contracts.md), [API preset editor](api-presets-and-model-parameter-editor-workflows.md), [AI Hub](ai-hub-interaction-traceability-checklist.md), [ASR catalogue](asr-model-gallery-and-settings-workflows.md), [Guide](guide-walkthrough-and-image-focus.md). Исходники только читались; отсутствие runtime Qt тестов явно сохраняется.

## Pass13: от выбора в dialog до изменения Core

Повторно проверены следующие незавершённые границы по текущим исходникам, совпадающим с CodeNow.zip. Это source-level action→handler→outcome, не запуск Qt.

| Действие | Caller → callback → итог | Что не следует обещать |
|---|---|---|
| Apply pipeline | ApiSettingsController._on_configure_pipeline_clicked → SHOW_WINDOW(protocol_pipeline) → зарегистрированный ProtocolPipelineGuiController/MessageProcessingDialog.accepted → on_apply → _protocol_overrides.transforms + _on_field_changed | Apply меняет draft; durable save — отдельный _save_preset_async → ApiPresetService.save_custom. Cancel callback не вызывает |
| Редактировать model parameters | PresetModelSettingsController.edit_definition → ModelParametersDialog → definition → ModelSettingsService.customize → render + form.changed | Dialog работает с copy/schema form, не пишет произвольные HTTP поля в endpoint; durable preset save отдельно |
| JSON/schema error | Form/JSON tab commit, неизменяемый dialect, проверка SettingsSchema + check_dialect у caller | Accepted в JSON tab ещё не означает valid schema: caller может показать ошибку и открыть dialog повторно |
| Выбрать обнаруженную модель | TestMixin обработал test response → ModelsLoadedDialog → selected_model → api_model_row + field_changed | Это выбор draft, не новый provider request и не немедленная смена уже идущей генерации |
| Copy models | ModelsLoadedDialog._copy_visible → TSV headers/видимые rows в clipboard | Нет экспорта БД и сохранения model weights |
| Compile now/later | FishSpeech install initialize callback optional=True → GuiInteractionService.confirm(triton) → WindowManager blocking → choice; skip/нетGUI возвращает successful postponed step | Postponed не compiled; explicit AI Hub compile идёт отдельным operations.initialize с device |
| Long paths | TritonDependenciesDialog._on_enable_long_paths → VoiceModelController.enable_long_paths → torch_compile_runtime.enable_long_paths | Кнопка запускает powershell/reg.exe с UAC для HKLM LongPathsEnabled, затем перечитывает status; это отдельный OS mutation, не простая local preference. В аудите не выполнялась |
| Backend plan link | AIHubDialog._confirm_backend_install → _BackendInstallConfirmationDialog → open_backend_requested | Переход на backend tab возвращает False и не даёт согласие на исходную install operation |

ModelParametersDialog поддерживает add/remove, type/default/range/enum/локализованный title/description, form↔JSON с проверкой tab switch. Gemini generationConfig prefix добавляется при редактировании. Save/import/export schema wired через PresetModelSettingsController; import_definition может сохранить внешнюю schema, но не означает автоматический durable save всего preset. ModelsLoadedDialog фильтрует paid/free и id/name/slug, сортирует и копирует видимый каталог; принятие требует непустого model ID.

WindowManager blocking использует BlockingQueuedConnection и holder(choice/error/done); штатный caller должен быть вне GUI thread. Событийный bus не переносит return choice подписчика обратно publisher. Для VCRedistWarningDialog реально реализованы **docs/retry/close**, не автоматическая установка redistributable. Найдены factory и event subscriber, но production emitter SHOW_VC_REDIST_DIALOG в исследованном src не найден; общий GuiController.confirm(vc_redist) также не преобразует retry в affirmative. Поэтому зарегистрированный error dialog и реальный active recovery workflow различаются. Для Triton найден прямой production caller в FishSpeechInstallSpec callback.

NewPresetDialog, ProtocolPipelineDialog и VoiceActionWindow: повторный поиск definitions/imports/callers и composition registry не дал production creation witness. Оставлены **UNPROVEN**, не обязательный самостоятельный parity. Не удалялись и не исправлялись. Регистрация protocol_pipeline подтверждает MessageProcessingDialog, а не одноимённый alternative class. Произвольные QDialog-функции Telegram и native file/input/message pickers уже имеют отдельные workflow specifications.

Точные дополнительно просмотренные источники: window_composition_controller factories; protocol_pipeline_gui_controller полностью; api_settings/controller245–309, editor_mixin build/save, model_settings_controller; model_parameters_dialog129–249; models_loaded_dialog filtering/select/copy; voice_action_windows940–1169; gui_controller.confirm; fish_speech_model optional compile callback; torch_compile_runtime425–462; AI Hub _confirm_backend_install; window_manager registration/blocking lifecycle. Незакрытая граница — Qt thread/render/live interaction и consumers других callbacks, а не отсутствие описания этих actions.
