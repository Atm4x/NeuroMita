# Raw-string events: дополняющий аудит маршрутов и Qt bridges (Pass 12)

**Scope/метод.** AST проход `CodeNow.zip` по 717 modules (исключены `src/Lib`, `src/ui/not_used`, `src/utils/Testing`) обнаружил 786 синтаксических вызовов методов с именами `emit/try_emit/subscribe`, из них 28 разных строковых литералов в аргументе события. **Это сырая оценка, не число EventBus-событий:** Qt signals и собственные `subscribe` сервисов имеют похожие названия, поэтому автоматические совпадения фильтруются вручную. [Индекс событий по `Events.*`](event-producer-consumer-callsite-index.md) охватывает другой класс аргументов и ранее не учитывал строки.

## CAP-EVENT-RAW-001 — реальные двухсторонние маршруты вне `Events.*`

| Event string | Producer | Consumer | Назначение и наблюдаемое состояние |
|---|---|---|---|
| `history_loaded` | `src/controllers/model_controller.py:801-853` | `src/controllers/gui/view_event_controller.py:6-22` | Начальная страница истории с `request_id`, `character_id`, `messages`, `total_messages`, `loaded_offset`; затем `AppWindowBase.history_loaded_signal` (`src/ui/windows/app_window_base.py:80,272`) |
| `more_history_loaded` | `src/controllers/model_controller.py:857-911` | `src/controllers/gui/view_event_controller.py:8,23-27` | Более старая страница, привязанная к тому же `character_id`; UI prepend/offset отдельно от начальной загрузки (`app_window_base.py:81,273`) |
| `reload_prompts_success` | `src/controllers/model_controller.py:2815` | `src/controllers/gui/view_event_controller.py:12,39-42` | Подтверждение перезагрузки prompt-файлов и независимое UI notification |
| `reload_prompts_failed` | `src/controllers/model_controller.py:2817-2820` | `src/controllers/gui/view_event_controller.py:13,44-48` | Ошибка перезагрузки prompt-файлов; payload передаётся GUI |
| `display_loading_popup` | `src/controllers/main_controller.py:768-775` | `src/controllers/gui/view_event_controller.py:14,50-53` | Показывает индикацию ожидания только при GUI runtime; headless пишет сообщение в лог |
| `hide_loading_popup` | `src/controllers/main_controller.py:776-778` | `src/controllers/gui/view_event_controller.py:15,55-58` | Убирает индикацию, не равнозначно отмене исходной операции |
| `send_periodic_image_request` | `src/controllers/capture_controller.py:355-390` | `src/controllers/chat_controller.py:410,1240+` | Настроенная периодическая отправка накопленных screen frames в диалоговый маршрут, отдельная от ручного attach |
| `update_screen_capture_exclusion` | `src/controllers/capture_controller.py:198-219` | `src/controllers/capture_controller.py:67,94-105` | Применяет исключение собственного GUI window или окна по title к `ScreenCapture`; настройки могут потребовать перезапуск capture |

Восемь строк найдены и на стороне эмиттера, и на стороне подписчика; это **синтаксическое evidence**, не E2E в живом Qt/Windows. `ViewEventController` создаётся в `src/controllers/gui_controller.py:81`, его `subscribe_to_events` проходит через конструктор `BaseController`/GUI init. Вызывает Qt signals view, а не напрямую изменяет persisted history.

## CAP-EVENT-RAW-002 — существенные переходы, ранее скрытые за raw names

**History paging:** `ModelController._on_load_history` фиксирует целевого персонажа в request payload, запрашивает `get_recent_messages` с limit/offset, проецирует строки для UI и публикует `history_loaded`. При альтернативном чтении локального character history выбирается tail страницы (`model_controller.py:797-851`). `ModelController._on_load_more_history` проверяет `character_id` на совпадение с `_history_character_id`, загружает следующую порцию и отправляет `more_history_loaded` (`:855-912`). Таким образом, `LOAD` и `LOAD MORE` имеют разную семантику offsets, а синхронизация с текущим выбранным персонажем — самостоятельная UI responsibility.

**Periodic screen observation:** `CaptureController` при создании получает ключи `SEND_IMAGE_REQUESTS`, `IMAGE_REQUEST_INTERVAL` и прочие capture keys (`capture_controller.py:12-52`). Отдельная supervised background loop проверяет таймер и вызывает `send_interval_image` (`:335-391`); отключённый `ENABLE_IMAGE_ANALYSIS`, отсутствие готовых кадров или выключенный screen analysis меняют результат. При наличии кадров отправляется `send_periodic_image_request` с пустым текстовым input и `image_data`. Это самостоятельный автоматический *trigger*, не то же самое, что `CAPTURE_SCREEN` или `AUTO_ATTACH_IMAGES`.

**Cross-thread view handoff:** `MainController` по событиям loading переводит состояние либо в лог (headless), либо в события `display_loading_popup`/`hide_loading_popup` и далее Qt signals (`main_controller.py:768-778`, `view_event_controller.py:49-58`). Доставка event означает отложенный GUI update, но сама по себе не гарантирует результат операции, вызвавшей loader.

## Односторонние raw strings и ограничения автоматического поиска

В статическом индексе встречаются подписки на `model_initialized`, `model_init_cancelled`, `model_init_failed`, `capture_settings_loaded`, `start_*_capture`, `stop_*_capture`, `speech_settings_loaded`, `telegram_settings_loaded` без *прямого литерального* эмиттера в выбранном scan. Возможны динамический `event_name`, константное значение из `Events`, сервисный bridging или неиспользуемый path; **нельзя объявлять их inactive либо unsupported** без проверки по значениям и фактической регистрации. Строки `event` и `language` в raw scan относятся к отличающимся `.emit`-интерфейсам и **не должны увеличивать счётчик EventBus событий**.

## Требования для паритета / future fixtures

- `REQ-RAW-EVT-001`: сохранять два результата history loading (initial/older) с идентичностью target character, request identity и offsets; отдельный сценарий быстрой смены персонажа.
- `REQ-RAW-EVT-002`: периодические screen observations должны иметь явные триггер/permission, частоту, источник изображений, политику пропуска без frames и observable outcome в dialog pipeline.
- `REQ-RAW-EVT-003`: loading-popup/status события не считать acknowledgment бизнес-операции, headless fallback сохраняет наблюдаемость без Qt.
- `REQ-RAW-EVT-004`: дедуплицировать EventBus names по **wire values и зарегистрированным producers/consumers**, не по одинаковому синтаксису метода `.emit` в разных библиотеках.

**Открыто:** прямые и косвенные эмиттеры one-sided raw names, Qt signal-handlers beyond first hop, runtime проверка актуальности начальных/запаздывающих страниц, реальная работа capture Windows. Static evidence недостаточно для полного закрытия Traceability gate 20.

## Pass 13: конечный history receiver и часть one-sided имён

Начальная/older history доведены до Qt receiver и coordinator в [контракте страниц](../02-ui/history-page-fencing-and-live-replay.md); изолированно проверены stale request, mismatch, inactive character и live replay. Это закрывает неизвестность первого UI-перехода, но не live Qt+DB E2E.

Поиск в production `src` и `scripts` (`*.py`, без Lib/Testing/not_used), затем чтение constructors/subscribers и callsites уточнили raw names:

| Raw value | Подтверждённый маршрут | Вывод для функциональности |
|---|---|---|
| stop_screen_capture / stop_camera_capture | Равны `Events.Capture.STOP_*`; producer `gui/app_shell_controller.py:112–113` при close без attached main controller; consumer CaptureController и headless fallback | Это не две разные функции «raw» и «enum». В CaptureController есть обе записи subscription; фактическую dedup/delivery не выводить из их количества |
| start_screen_capture / start_camera_capture | Объявлены Events.Capture.START_*, подписки есть, production emit этих constants не найден. CaptureController `_apply_initial_settings` и `_on_setting_changed` вызывают start методов напрямую | Рабочая capture capability подтверждена независимо от найденного/ненайденного producer этих compatibility event names |
| capture_settings_loaded | Подписка ведёт в `_apply_initial_settings`; producer по literal/constant не найден. Constructor уже вызывает `_apply_initial_settings` и подписывает settings changes (`capture_controller.py:23–57,170–200`) | Не объявлять startup зависимым от этого event |
| speech_settings_loaded | Может подменить supplied settings и вызвать `_apply_settings_snapshot`; producer в исследованном scan не найден. Constructor применяет snapshot сам (`speech_controller.py:138`) | ASR settings/init не следует считать недостижимыми из-за one-sided alias |
| telegram_settings_loaded | Может заменить supplied settings; producer не найден. Constructor подписывает SettingsService и вызывает `_load_settings_snapshot(reason="initial")` (`telegram_controller.py:46–56`) | Telegram credentials/config читаются active путём; old event не единственный trigger |
| model_initialized / model_init_cancelled / model_init_failed | Есть ViewEventController → объявленные AppWindowBase Qt signals. Production producers и `.connect` для этих трёх signals поиском не подтверждены | **UNPROVEN compatibility bridge**, не самостоятельная обязательная функция или доказанная notification chain |
| Реальный voice loading outcome | LocalVoiceController публикует Events.Audio.UPDATE_MODEL_LOADING_STATUS / FINISH_MODEL_LOADING; VoiceoverController подписан (88–94) | Нельзя путать с похожими one-sided model_init_* именами. [Рабочий voice lifecycle](../02-ui/local-voice-model-management-and-compile-dialogs.md) описан отдельно |

Негативный поиск ограничен указанным source snapshot; внешняя reflection/plugin emission не доказана и не запрещена им. Остальные динамические EventBus names и event payload registration продолжают требовать контекстной проверки. Новых network/device/Qt запусков здесь не было.
