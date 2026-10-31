# Управление голосовыми сервисами и профилями

Статус: CONDITIONAL. Основные GUI actions и backend settings/admission прочитаны; реальная модель, Telegram login, API preview и установка не запускались. Inference остаётся Python. Дополняет [озвучку](../01-functional/voice-output.md), [Telegram](../01-functional/telegram-voice.md) и [AI Hub](ai-hub.md).

## Local voice: установить, загрузить, выбрать

CAP-VOICE-002. Voice settings переключает Local/TG/API и использование голоса; local model selector хранит machine id. Отдельно показаны installed/initialized/checking/loading/unavailable; действие кнопки зависит от состояния: открыть AI Hub, initialize или reinitialize. USE_VOICEOVER не скрывает факт продолжающейся инициализации Local. Есть restart tts service и переход к AI engine settings. LOCAL_VOICE_LOAD_LAST разрешает silent startup load только выбранной установленной совместимой модели.

Manual init проверяет compatibility и наличие models; ошибки ведут к install UI. Silent load не показывает модалки. Hide/крестик прячет progress, загрузка продолжается со status chip. Cancel снимает ожидание результата и восстанавливает прежний выбор, но не останавливает worker inference load. Finish применяет модель, только если _loading_model_id совпадает; после cancel late success не выбирает её автоматически. Fence здесь model_id, не уникальный generation/request id: повторный запрос той же модели требует отдельного concurrency contract в новой системе.

## Каталог и параметры локальных моделей

CAP-VOICE-003. VoiceModelController строит каталог из tts installables/get_model_configs и canonical metadata; fallback — presets/local_voice_models. В fallback12 IDs: edge_tts_rvc_cuda/onnx, silero_rvc_cuda/onnx, omnivoice, medium, medium+, medium+low, high, high_clf5, high+low, high_clf5+low. Этот список не означает12 независимых engine implementations: комбинации используют общие backends/RVC. Полный перечень component-specific options/install plans пока не закрыт.

Параметры хранятся отдельно в Settings/voice_model_settings.json по model_id, накладываются на schema/defaults кроме locked fields. GPU vendor/schema expansion выбирает допустимые CPU/CUDA/DirectML/MPS значения и labels. CUDA хранит ordinal, DML предпочитает dml@LUID, преобразуя в runtime index; сохранённое устройство валидируется по актуальным choices. Настройки могут задавать зависимое поведение half/device. Эти правила — host control/configuration.

Save нормализует values/behaviors, проверяет devices, merge-ит по model/key и пишет temp JSON. Перед os.replace старый settings file может удаляться; это не гарантированная atomic replacement во всех failure points. Возвращаются changed/errors/error. GUI _save_values обрабатывает errors (device validation), но одиночный error записи не проверяет перед refresh/events: сохранение может выглядеть успешным. Общей строгой валидации всех component options в этом методе не доказано.

## Установка, удаление и compile

CAP-VOICE-004. Install preflight показывает несовместимость или предложение добавить CPU/CUDA/ONNX backend в план; catalog preview failure пропускает предварительный gate, installer имеет собственный admission. Действия идут через InstallableOperationsService и task IDs, accepted отличается от completion. VoiceModelGuiController install/uninstall handlers вызывают backend, затем возвращают True без переноса backend bool — возможна потеря немедленного отказа admission.

Удаление из отдельного voice dialog блокируется, если LocalVoiceService считает модель initialized/in use; пользователь получает предложение перезапуска. Затем explicit confirm и общая uninstall операция. Это поведение конкретного GUI entrypoint, не доказательство глобальной невозможности удаления другими путями AI Hub. После удаления текущей модели GUI выбирает другой installed id из set либо None; порядок fallback не определён продуктово.

Для medium+/medium+low backend предоставляет compile/clear-cache initialize modes, device selection и events. Отсутствующий installables feature даёт отказ с диагностикой; compile request не равен готовому executable artifact. Component compile implementation/licensing/native prerequisites требуют следующего отдельного прохода. Window VM ограничивает install/uninstall одной operation, refresh coalesced, показывает errors и completion; полная renderer/compile UI reachability ещё не закрыта.

## Remote voice и проверка звука

CAP-VOICE-005. GUI поддерживает presets из provider templates: save/select/add/delete, API key, model, speed0.5–2, общий voice и overrides по персонажам. Character voice tabs не переключают собеседника. Provider docs/keys links открываются внешним browser. Switching/adding сначала сохраняет текущий draft; preview также сохраняет его, затем синтезирует текст для выбранного character.

RemoteVoiceSettingsViewModel сериализует операции busy gate. Preview воспроизводит локально через AudioHandler, публикует speaking-window state, применяет volume0–200 и удаляет временный output в finally. Это реальный synthesis+playback, не только endpoint ping. Закрытие view может прекратить применение UI результата/воспроизведение после synthesis, но вызов provider этим сам по себе не отменяется. Provider/domain errors переводятся в UI message без вывода секретов; settings backend описан в voice-output.

CAP-TG-002. Code/2FA dialogs привязаны к request_id: непустой submit, Enter, Esc/Cancel→Reject; код ограничен10 символами, password скрыт. Оба ввода strip whitespace, включая пароль. Ошибка может отображаться при повторном запросе. Start Telegram из voice settings разрешён только при complete credentials, публикует force start. Auth service/state описан отдельно; login не проверялся.

## Доказательства и ограничения

Прочитаны VoiceModelsViewModel; VoiceModelController catalog/load/save/preflight/install/uninstall/compile/finalize; VoiceModelGuiController admission/confirm/save/completion; voiceover_settings_logic и VoiceoverSettingsViewModel; RemoteVoiceSettingsViewModel actions/preview; remote_api draft/character voice и ключевые form controls; Telegram auth dialog construction/submit/reject; VoiceoverGuiController init scheduling/autoload/loading/finish/cancel и snapshot status path частично; core.voice_device_selection enumeration/schema/validate/migrate.

Не считать полностью прочитанными весь VoiceoverGuiController, painter character tabs, hardware compatibility helpers, profiles per local model, все old synchronous helpers и renderer. Найденный undefined state в _sync_local_model_status относится к старому synchronous helper, единственный найденный caller _sync_everything_sync_legacy; активность последнего не доказана, поэтому это не зарегистрированный дефект текущего пользовательского пути. Установка/выбор/загрузка/готовность/synthesis/playback нуждаются в разных outcomes и operation identities независимо от языка нового core.

## Динамическое разрешение параметров: выбранное устройство меняет допустимость FP16

Важный контракт schema-driven voice settings, который нельзя заменить постоянным списком полей. `src/core/setting_behaviors.py:6-40` поддерживает поведение `source_allowlist`: настройка содержит ссылку на **другой** ключ (`source`), список разрешённых значений (`supported_values`) и значение при запрете (`unsupported_value`). Например, `is_half` становится недоступным не просто при отсутствии CUDA, а при **выборе конкретного неподдерживаемого GPU**; другой установленный CUDA GPU может допускать FP16. Значение `"cuda"` приводится к `"cuda:0"`. При запрете нормализация значений принудительно подставляет заданное `unsupported_value`.

Границы достижимости: `src/ui/windows/voice_model_view.py:421-433` и `src/ui/windows/ai_hub/schema_renderer.py:459-480` обновляют **enabled state** controls, тогда как `src/controllers/voice_model_controller.py:496-...` и `src/services/installable_catalog_service.py:594-...` выполняют нормализацию на backend. Это одновременно UI-зависимость и runtime validation: отключение поля визуально не гарантирует, что старое значение не попадёт в конфигурацию, поэтому значение также нормализуется перед использованием. `src/utils/Testing/test_voice_device_selection.py:150-179` задаёт fixture с двумя GPU: один разрешает `is_half=True`, другой переводит его в `False`. Это source contract, не проверка фактической точности CUDA модели.

Для нового Core сохранить capability «выбор voice model + device → пересчёт разрешённых значений config», но не копировать внутренние PyQt-структуры. Для будущих тестов: переключение CUDA ordinal 0 ↔ ordinal 1, CPU, отсутствие GPU, устаревший сохранённый FP16 flag и редактирование в AI Hub vs отдельном voice dialog.
