# ASR Models: каталог, настройки движков, установка и пользовательские состояния

**Status:** `ACTIVE` GUI path; `CONDITIONAL` engine operations. **Источник:** `src/controllers/gui/asr_glossary_controller.py:14-186`, `asr_glossary_view_model.py:17-169`, `src/ui/windows/asr_glossary_presentation.py:9-47`, `asr_glossary_view.py:63-235` и последующие handlers, `src/services/asr_settings_service.py:15-188`, `src/handlers/asr_models/registry.py:8-51`, `src/services/installable_catalog_service.py:206-614`.

## 1. Пользовательский сценарий

Открывается отдельный диалог `asr_glossary`. Его содержимое создаётся по готовности окна; первое обновление инициируется через Qt event turn (`asr_glossary_controller.py:29-66`, `window_composition_controller.py:38,94-96`). Экран включает поисковую строку и список ASR-движков слева, панель описания/тегов/статуса/установки справа, отдельные вкладки подробностей и schema-driven controls настройки. UI допускает refresh без переоткрытия диалога (`asr_glossary_view.py:63-235`).

В движках текущего реестра пять ID: `google`, `gigaam`, `gigaam_onnx`, `whisper`, `whisper_onnx` (`handlers/asr_models/registry.py:8-15`). Это идентификаторы выбора обработчика, **не** эквивалент наличия его исполняемой модели. Lazy import движка происходит при `engine_class`, а install cards живут в отдельном каталоге `asr:<engine_id>`. Возможность посмотреть карточку не требует успешного импорта inference.

## 2. Намерения UI и состояния

`AsrGlossaryState` разделяет три независимые timeline: `catalog_revision`, `settings_revision`, `install_revision`. Дополнительно имеются `loading/error`, `settings_engine_id/schema/values/loading/error`, `installing_model_id/progress/status/error` (`asr_glossary_presentation.py:9-25`). На каждую группу приходит отдельное изменение UI. Список intents: RefreshAsrGlossary, LoadAsrSettings, InstallAsrModel, SetAsrOption (`:28-47`).

`AsrGlossaryViewModel.refresh` использует coalesced background loading; `load_settings` — latest-result-wins с проверкой `settings_engine_id`, чтобы быстрый выбор другой модели не перерисовывал старые настройки; installation request запрещается, когда уже есть `installing_model_id`, а progress и completion приходят через отдельные notifications (`asr_glossary_view_model.py:33-169`). Новому GUI необходима эта семантика выбора/устаревших ответов, не конкретно QObject.

## 3. Контракты с Core

- Catalog read: `list_rows(include_status=True, refresh=..., category='asr')`. Из metadata и status создаётся flat view row: id, component_id, name, description, languages, tags, readiness, details, `missing_required`, `missing_optional`; если `backend_ok=false`, к required добавляется `backend` (`asr_glossary_controller.py:82-118`). Для отображения UI фактически выставляет `installed` по `status.ready`, а не `status.installed`; **domain** status следует читать напрямую, не копировать это UI упрощение как общий контракт.
- Installation: `InstallableOperationsService.install({component_id:'asr:<engine>', with_ui:true, task_id:'asr:install:<engine>', meta.kind:'asr'})`. Admission может быть отвергнута; `Events.Install.TASK_PROGRESS/TASK_FINISHED/TASK_FAILED` обновляют состояние только ASR-тасков (`asr_glossary_controller.py:34-38,68-80,137-186`).
- Settings: схема и значения запрашиваются через `InstallableCatalogService.settings_schema/load_settings('asr:<engine>')`; при изменении одного поля загружается текущая конфигурация, заменяется ключ и вызывается `save_component_settings` с валидацией. Ошибка возвращается в `settings_error`, а не превращается в успешное изменение (`asr_glossary_controller.py:120-135`; `asr_glossary_view_model.py:56-65,76-90`).
- Основное состояние выбора engine в storage хранится в `settings_path('asr_settings.json')`, сервис содержит `engine` и отдельные dict для `models[engine_id]`, имеет global и per-engine revisions, уведомления подписчиков, запись через temp+replace (`asr_settings_service.py:22-188`). Default `engine='google'`, `gigaam.device='auto'` (`:29-35`). Изменение engine — не тождественно скачиванию модели или включению микрофона.
- Каталог инсталлятора подписывается на изменения ASR-настроек и инвалидирует status именно соответствующего `asr:<engine>` либо всей категории (`installable_catalog_service.py:55-87`). Поэтому изменение параметров устройства может поменять readiness без переустановки артефактов.

## 4. Границы между ASR settings, input devices и user capture

ASR Gallery описывает модели и их конфигурацию; microphone device list, PTT/continuous mode, capture state, VAD и выбранный Windows endpoint принадлежат соседнему пользовательскому сценарию (`controllers/gui/microphone_settings_controller.py`, `chat_panel_view_model.py`, `handlers/asr_audio_capture.py`). Не сливать model installation, device selection и live microphone recording в одну операцию. Для полной parity нужны как минимум: выбранный recognizer, настройки recognizer, готовность artifacts/engine, актуальное устройство, состояние записи, transcript/error.

## 5. Требования к последующему Rust UI/Core

Требуется сохранять поиск, метаданные пяти типов ASR, раздельные readiness/progress/setting states, схемы динамических полей, refresh, full error feedback, запрет параллельных установок из этого диалога, precise execution acceptance и независимость от Python heavy imports. Presentational layout можно изменить полностью. ASR inference (Whisper/GigaAM) остаётся в Python AI, Core лишь управляет окружениями/IPC и пользовательским состоянием.

**Validation fixtures:** быстрый переключатель engine при незавершённом ответе settings, запаздывающий status, install progress/failure, изменение device/option и новый readiness, отсутствие AI environment, перечисление всех пяти engine IDs, открытие/закрытие диалога. **Не подтверждено runtime E2E:** фактические Tensor/CUDA/Windows audio path и воспроизведение всех UI вариантов при Qt.
