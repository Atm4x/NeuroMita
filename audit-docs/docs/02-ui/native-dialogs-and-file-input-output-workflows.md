# Системные файловые и короткие диалоги: подтверждённые пользовательские операции (Pass 12)

**Контекст:** GUI-функциональность исследуется как набор пользовательских действий и результатов, без наследования Qt/Python API. Изучен рабочий снимок `CodeNow.zip`, без запуска Qt. Все пути ниже относительно `src/` текущего Python-проекта. Поиск целевых `QFileDialog.get*` / `QInputDialog.get*` по `src/**/*.py` нашёл **23 + 9 синтаксических callsites**, из них **7 QFileDialog и 1 QInputDialog** находятся в `utils/Testing` (отдельный RAG tester и тестовый mock). Поэтому в рабочем интерфейсе обнаружены **16 QFileDialog и 8 QInputDialog callsites**; это количество вызовов, не отдельных кнопок и не всех разновидностей диалогов.

## CAP-UI-NATIVE-001 — выбор входных файлов и каталогов

| Сценарий | Trigger / файл и строки | Пользовательский ввод | Функциональный outcome и условия |
|---|---|---|---|
| Вложить изображения к чату | `ui/widgets/chat_panel.py:307-333` | Несколько PNG/JPEG/WebP/BMP/GIF | Список файлов проходит локальную обработку/представление во вложениях; отправка сообщения — отдельное подтверждаемое действие |
| Загрузить debug snapshot | `ui/windows/app_window_base.py:1568-1597` | JSON-файл из character-specific каталога | Передаётся shell-action загрузки snapshot для выбранного персонажа; CANCEL не загружает |
| Импорт старого сохранения | `controllers/gui/character_settings_logic.py:1112-1176` | **Альтернативные** одиночный ZIP/JSON, папка или несколько JSON | Один выбор превращается в нормализованный список источников для импорта; три пути — варианты одной функциональности, не три отдельных импортера |
| Импорт базы выбранного персонажа | `controllers/gui/character_settings_logic.py:2225-2236` | JSON и идентификатор выбранного персонажа | Вызывает `_start_import_worker(... override_character_id=cid)`; при отсутствии выбора операция недоступна |
| Импорт базы для всех | `controllers/gui/character_settings_logic.py:2238-2242` | JSON | Вызывает `_start_import_worker(... override_character_id=None)`; область действия отличается от предыдущей |
| Выбор папки для fine-tune датасетов | `ui/settings/data_settings.py:210-226` | Каталог | К выбранному каталогу добавляется подпапка `FineTuneData`; это редактирование формы, не доказательство немедленного переноса существующего датасета |
| Папка музыкальной библиотеки Beat Sync | `ui/settings/game_settings.py:336-356` | Каталог | Событие `BeatRebuildCacheRequested(selected_dir)` инициирует пересканирование; состояние операции позже обновляется view model |
| Путь установки Unity | `controllers/gui/updates_settings_controller.py:660-682` | Каталог | Текстовое поле обновляется, значение `UNITY_INSTALL_DIR` сохраняется как настройка; запуск/установка Unity отдельно |
| Каталог экспорта базы | `ui/dialogs/db_export_dialog.py:241-255` | Каталог | Устанавливает `out_dir` в форме экспорта, ещё не создаёт файл |
| Импорт схемы параметров модели | `controllers/gui/api_settings/model_settings_controller.py:52-64` | JSON definition | `service.import_definition`, затем `change_schema` и локальная перерисовка формы, с обработкой parse/file errors |

**Доказанная общая семантика:** закрытие системного селектора (пустая строка/список) не означает ошибку обработки бизнес-операции: до передачи в Core это добровольный отказ. `selected path` — входные данные; фактическая установка, импорт и изменение persisted state находятся после него.

## CAP-UI-NATIVE-002 — экспорт и сохранение во внешние файлы

| Сценарий | Trigger / источник | Результат |
|---|---|---|
| Экспорт fine-tune samples | `ui/dialogs/export_dialog.py:230-250` | Пользователь задаёт путь JSONL; формат Raw/ShareGPT выбирается в экспортной форме до открытия селектора |
| Экспорт схемы модели | `controllers/gui/api_settings/model_settings_controller.py:65-74` | JSON с schema ID в имени по умолчанию, `service.export_definition(...)` после выбора |
| Сохранение install log | `ui/windows/voice_action_windows.py:638-656` | Запись UTF-8 текстового лога установки; повторное открытие окна — отдельное действие |
| Сохранение action log | `ui/windows/voice_action_windows.py:912-931` | Запись UTF-8 логов действия модели/AI Hub, независимо от install log |

Экспорт `World.db` как JSON через `DbExportDialog` имеет отдельную форму path/name и worker; не следует путать с JSONL fine-tuning или model-parameter schema export.

## CAP-UI-NATIVE-003 — короткие вводы и выборы

| Сценарий | Источник | Ввод и смысл |
|---|---|---|
| Release tester code в Home | `ui/pages/home_page.py:513-532` | Парольный ввод для допуска к релизным архивам, не общий credential provider |
| Release tester code в Updates | `controllers/gui/updates_settings_controller.py:399-420` | Другая точка входа в тот же функциональный доступ к релизам; не считать отдельной системой аккаунтов |
| Batch edit строк БД | `ui/dialogs/db_viewer.py:1049-1079` | Значение одного столбца для нескольких выбранных строк, после ввода идут изменения в модели/БД |
| Создание embedding preset | `ui/settings/embed_provider_settings.py:580-593` | Имя → `AddEmbedPreset` intent; подтверждение UI не гарантирует durable commit до результата операции |
| Сохранение RAG preset | `ui/settings/rag_preset_widget.py:151-170` | Непустое имя; `ApplyRagPreset` при сохранении в выбранный preset |
| Выбор персонажа при запуске мини-игры | `ui/settings/game_settings.py:98-137` | Варианты Sandbox и текущего Unity-собеседника при их расхождении; cancel не стартует игру |
| Копирование API preset | `controllers/gui/api_settings/editor_mixin.py:535-562` | Имя копии (suggestion: `Copy`), отдельная операция создания preset |
| Переименование API preset | `controllers/gui/api_settings/editor_mixin.py:654-684` | Новое непустое имя, применение через API preset service |

**Отграничение Testing:** `utils/Testing/rag_tester/rag_tester_gui.py` содержит самостоятельный загрузчик/сохранение сценариев, suite и экспорт результатов; это инструмент тестирования, а не доказанная обязательная страница production GUI. `utils/Testing/test_release_preset_names.py` использует patch `QInputDialog.getText` и не представляет пользовательский callsite.

## Дополнительная поверхность: модальные подтверждения и прогресс

По статическому поиску `QProgressDialog(...)` выделяются глобальный loading-overlay (`ui/windows/app_window_base.py:1466`), графовый viewer (`ui/dialogs/graph_view_widget.py:949`) и операции maintenance/reindex/export в `controllers/gui/character_settings_logic.py:1214-2256`. Эти диалоги визуализируют ход, а не становятся владельцем операции автоматически. Многочисленные `QMessageBox.question/warning/information` требуют группировки по **действию**, а не механического включения 300+ вызовов в каталог функций; отказ от destructive action — часть контракта.

## Требования и критерии паритета

- **REQ-NATIVE-DIALOG-001:** сохранить выбор одного/нескольких файлов, каталогов и custom output paths там, где исходный GUI реально открывает системный селектор; отмена выбора должна оставлять исходную операцию невыполненной.
- **REQ-NATIVE-DIALOG-002:** различать `selection`, `intent/admission`, `background result`, `durable effect` в импортерах, экспортах, датасетах, installation logs и Unity folder selection.
- **REQ-NATIVE-DIALOG-003:** сохранить два scope импорта World.db (выбранный персонаж/all) и три источника импорта старого backup (архив/каталог/несколько JSON), не дублировать операции по числу диалогов.
- **REQ-NATIVE-DIALOG-004:** сохранить пользовательский выбор между Sandbox/Unity target для ручного старта мини-игры и проверку доступа к тестерским релизам из обоих GUI ingress.

**Проверки, которые ещё отсутствуют:** реальный Windows picker, permissions и длинные пути, отказ от перезаписи, гонка с текущим персонажем/несохранённой формой, сохранение через network drive, Qt delivery после background worker. Это не blocker для описания первичных контрактов, но не следует считать E2E-паритет подтверждённым.
