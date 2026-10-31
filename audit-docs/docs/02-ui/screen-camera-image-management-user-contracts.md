# Экран, веб-камера, внутриигровая камера Миты и обслуживание изображений

**Назначение:** восстановить самостоятельные пользовательские возможности раздела «Экран и камера» без смешивания двух устройств ввода и Unity FrameRecorder. **Статус:** `ACTIVE` UI регистрация; каждое действие `CONDITIONAL` по настройкам, устройству, Unity и разрешению работы с изображениями. Источники: локальный snapshot `CodeNow.zip`; отсутствие runtime проверки отмечается явно.

## CAP-SCREEN-UI-001 — режимы получения изображения рабочего стола

**Источник:** `src/ui/settings/screen_analysis_settings.py:23-73`; существующий core-data-flow описан в [images-and-capture.md](../01-functional/images-and-capture.md).

- `AUTO_ATTACH_IMAGES`: одиночный **актуальный** снимок при отправке сообщения, даже если постоянная запись экрана отключена. Для фактической передачи требуется `ENABLE_IMAGE_ANALYSIS` и vision-capable main model либо отдельная поддержанная ветка описания.
- `ENABLE_SCREEN_ANALYSIS`: фоновое создание кадров в буфер; параметры `SCREEN_CAPTURE_INTERVAL`, `FPS`, `QUALITY`, `WIDTH/HEIGHT`, `HISTORY_LIMIT` и `TRANSFER_LIMIT` задают темп, формат/ёмкость и число передаваемых кадров.
- `SEND_IMAGE_REQUESTS` + `IMAGE_REQUEST_INTERVAL`: периодические **самостоятельные** запросы модели с кадрами — другое назначение, нежели прикрепление к сообщению.
- `EXCLUDE_GUI_WINDOW`, `EXCLUDE_WINDOW_TITLE`: настройки исключения окна из desktop capture.

Настройки представляют разные намерения пользователя: «увидеть экран в ответ на моё сообщение», «собирать временной буфер» и «периодически инициировать запросы». Их нельзя объединять в один флаг захвата.

## CAP-CAMERA-UI-001 — независимый захват веб-камеры

**Источник:** `screen_analysis_settings.py:75-112`, `src/ui/settings/runtime_options.py`.

`ENABLE_CAMERA_CAPTURE`, выбор `CAMERA_DEVICE` и кнопка явного refresh камер; `CAMERA_CAPTURE_INTERVAL`, `FPS`, `QUALITY`, `WIDTH/HEIGHT`, `HISTORY_LIMIT` и `TRANSFER_LIMIT`. Список камер поступает через runtime options view model (`register_camera_options`, `refresh_camera_options`, `select_camera_option`), а не через статический список устройств. Переключение веб-камеры не меняет выбранного Unity персонажа. Не следует смешивать аппаратную camera и in-game FrameRecorder.

## CAP-IMAGE-DESCR-001 — текстовая интерпретация изображений

**Источник:** `screen_analysis_settings.py:114-225`; `src/controllers/model_controller.py:1530-1595`, `src/handlers/image_description_handler.py`, `src/controllers/prompt_controller.py:226`.

Имеются два независимых способа обработки: `IMAGE_INLINE_DESCRIPTION` просит vision-capable основную модель сделать описание внутри ответа, `IMAGE_DESCRIPTION_ENABLED` выбирает промежуточную vision-модель (при необходимости отдельный API-провайдер `IMAGE_DESCRIPTION_PROVIDER`) и подставляет описание в текстовый контекст. Оба режима используют `IMAGE_DESCRIPTION_DETAIL` со значениями brief/normal/detailed. В GUI поле детализации доступно, когда включён **хотя бы один** режим; поле внешнего провайдера зависит от non-native режима. Список провайдеров обновляется через `register_provider_options`, поэтому это не только константы страницы.

Семантика изображения дополнительно зависит от происхождения: `tv_observer` → видео на игровом телевизоре, `camera_snapshot_result`/`mita_camera` → собственный взгляд персонажа, `easel_drawing` → рисунок игрока. Подстановка изображения без provenance разрушит разницу между видимым персонажу миром и пользовательским вложением.

## CAP-IMAGE-MAINT-001 — статистика, поиск и удаление файлов изображений

**Источник:** `screen_analysis_settings.py:228-365`; `src/utils/image_cleanup.py:25-163`.

Три явных GUI-команды: посчитать число и суммарный вес изображений по персонажам; обнаружить локальные файлы без ссылок из истории; удалить такие файлы и показать количество освобождённых байт. Сканируются изображения из `Histories/<character>/Images/`, а referenced paths извлекаются из `Histories/world.db`, `history.meta_data.multimodal_parts[*].image_url.url`. Важно **сохранить функциональную связь файла и истории**, а не конкретный SQL-алгоритм старого кода. При отсутствии БД или невалидных метаданных результат имеет отдельную область неопределённости; никаких новых алгоритмов исправления в текущем аудите не предлагается.

Автоматическая очистка при старте управляется `IMAGE_CLEANUP_TTL_ENABLED`, `IMAGE_CLEANUP_TTL_DAYS` (UI default 30) и `IMAGE_CLEANUP_MAX_PER_CHAR` (UI default 500); фактический startup runner и последовательность вызовов уже рассматривались в [images-and-capture.md](../01-functional/images-and-capture.md), здесь подтверждён именно пользовательский контракт настроек.

## CAP-MITA-CAM-001 — внутриигровой FrameRecorder

**Источник:** `screen_analysis_settings.py:367-493`, `src/game_connections/handlers/actions/create_task.py:657-673`, `src/controllers/model_controller.py:1541-1559`, `src/controllers/server_controller.py:158`.

В отличие от системной камеры это функция Unity: `MITA_CAMERA_ENABLED` разрешает head-mounted camera у персонажа. **Continuous** `MITA_CAMERA_CONTINUOUS`: периодический снимок через `MITA_CAMERA_INTERVAL`, ring buffer из `MITA_CAMERA_MAX_FRAMES` и выбор `MITA_CAMERA_FRAMES_TO_SEND`; **on-demand** `MITA_CAMERA_ON_DEMAND`: модель может отправить DSL-команду `camera_snapshot`, после которой Unity посылает `event_type='camera_snapshot_result'`. Python handler преобразует событие в `task_type='chat'`, `model_event_type='chat'`, `system_input='[Your eyes (in-game camera)] ...'`, `image_source='mita_camera'` и изображения из `collect_context_images(...)`.

`MITA_CAMERA_JPEG_QUALITY` управляет сжатием. `MITA_CAMERA_USE_FILE_TRANSFER` — альтернативный транспорт «путь файла» вместо inline base64; документация GUI прямо ставит предпосылку совместного компьютера Unity и Python. Это вариант передачи данных, **не отдельный тип изображений**. Само выполнение DSL-команды в Unity здесь не тестировалось; подтверждён consumer события Python.

## Требования и границы

- `REQ-IMAGE-UI-001`: явное различение single-shot attachment, buffered screen capture и periodic requests; независимые интервалы, лимиты и разрешения.
- `REQ-IMAGE-UI-002`: webcam, desktop capture и Unity head-mounted camera имеют разные источники и настройки, даже если далее используют общий multimodal формат.
- `REQ-IMAGE-UI-003`: промежуточное/инлайн описание и уровень детализации доступны независимо; в LLM контекст необходимо передавать источник изображения.
- `REQ-IMAGE-UI-004`: предоставить учёт изображений по персонажам, поиск orphan и подтверждённое удаление; параметры автоматической очистки хранятся как пользовательские настройки.
- `REQ-IMAGE-UI-005`: Unity event `camera_snapshot_result` инициирует отдельный dialog task с изображениями и provenance «глаза персонажа»; отправка по файловому пути применима только при доступе к общему файлу.

**Открытые вопросы:** производительность real hardware capture, все варианты re-encode старых кадров по `IMAGE_QUALITY_REDUCTION_*`, E2E Unity FrameRecorder command producer и сохранение metadata при миграции. Эти проверки не исполнялись. Формальных архитектурных решений для Rust пока нет.
