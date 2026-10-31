# GUI: каталог моделей API, модальные действия и подтверждённые вспомогательные окна

**Статус:** статический функциональный аудит `CodeNow.zip`; `ACTIVE/CONDITIONAL` только по подтверждённым producer → view paths. **Назначение:** описать пользовательские действия независимо от PyQt-иерархии, не принимать неиспользуемые QDialog-классы за обязательные функции.

## CAP-UI-MODEL-001 — проверка API-провайдера и выбор модели

**Статус:** `ACTIVE`, условно по наличию подходящего выбранного API-пресета, ответа провайдера и `models` в результатах. **Доказательства:** `src/controllers/gui/api_settings/test_mixin.py:80-123,125-209` → `src/ui/settings/api_settings/dialogs/models_loaded_dialog.py:38-154,359-492`.

Пользователь нажимает «Проверить» в настройках API. UI определяет URL, текущую схему protocol и действие (`test_connection` и альтернативы), проверяет пригодность HTTP/HTTPS URL там, где это требуется, затем публикует `Events.ApiPresets.TEST_CONNECTION` с ID/base, ключом, URL, protocol ID, account ID и action. Кнопка находится в состоянии testing до возврата результата. Результаты от других пресетов (несовпадающий `id`) не применяются к текущему UI.

При положительном результате `known_models` обновляется из нормализованного списка; при наличии preferred model или account actions может обновиться текущая модель; затем открывается modal `ModelsLoadedDialog`. Он принимает **две разные формы результата**: набор model ID и дополнительные model_infos; не все поставщики предоставляют metadata.

| Действие пользователя | Состояние/результат | Источник |
|---|---|---|
| Поиск по моделям | Фильтрует видимые строки каталога | `models_loaded_dialog.py:67-76,359-386` |
| Включение платных моделей | Checkbox показывается лишь когда одновременно существуют free и paid; по умолчанию paid скрыты | `models_loaded_dialog.py:54-76,375-386` |
| Просмотр деталей модели | Таблица ID/name/type, контекст, rate limits, цены, latency, TPS при наличии данных | `models_loaded_dialog.py:116-154,206-358,386-465` |
| Сортировка | Сортируемые числовые значения отделяются от форматированного текста; сортировка таблицы | `models_loaded_dialog.py:24-36,379-465` |
| Выбрать / двойной клик | `selected_model` становится ID; родитель устанавливает его в поле настроек и помечает изменение | `models_loaded_dialog.py:467-476`, `test_mixin.py:176-185` |
| Копировать видимое | Текущая таблица (с заголовками) отправляется в clipboard как TSV | `models_loaded_dialog.py:478-489` |
| Закрыть без выбора | Смена выбранной модели через диалог не происходит, хотя авто-выбор до диалога уже мог быть сделан | `models_loaded_dialog.py:108-111`, `test_mixin.py:166-185` |
| Неуспешный тест | Показывается предупреждение/ошибка, кнопка возвращается в обычное состояние | `test_mixin.py:190-209` |

**Инварианты функции:** отдельная identity пресета и selected model, нормализация списка, отсутствие обязательного полного metadata, read-only таблица, явная confirmation выбранной модели и независимая связь UI с provider test service. GUI-фреймворк для новой системы пока не выбирался.

## CAP-UI-VOICE-001 — окно загрузки локальной голосовой модели

**Статус:** `ACTIVE/CONDITIONAL` — инициируется при non-silent load. `src/controllers/gui/voiceover_controller.py:1600-1673`, `src/ui/dialogs/model_loading_dialog.py:74-153`.

При загрузке модели UI отображает имя и статус и предлагает **две разные операции**: «Скрыть» и «Отменить». `Hide` закрывает только окно, загрузка продолжает идти в фоне, прогресс появляется в индикаторе страницы голосовых настроек. `Cancel` сбрасывает loading selection, восстанавливает предыдущий выбор модели и синхронизирует UI. Нельзя моделировать закрытие QDialog как автоматическую остановку inference/загрузки: `rejected` вызывает hide path (`voiceover_controller.py:1648-1673`).

При отсутствии каталога голосовых assets предлагается открыть AI Hub в категории `voices` через `Events.GUI.SHOW_WINDOW` (`voiceover_controller.py:1610-1639`). Это **переход пользовательского сценария**, не прямая загрузка модели из UI страницы.

## CAP-UI-DEPS-001 — информирование о зависимости FFmpeg

**Статус:** `ACTIVE/CONDITIONAL`; `src/controllers/gui/system_controller.py:59`, `src/ui/windows/app_window_base.py:1279-1291`, `src/ui/dialogs/ffmpeg_dialogs.py:63-153`.

Есть два окна: немодальное информирование об установке FFmpeg и модальное сообщение при неудачной автоматической установке. Второе показывает роль FFmpeg как системной зависимости медиа-обработки, ссылку на официальный download page и копируемый текущий рабочий путь. Кнопка подтверждения закрывает окно. Это presentation contract, не гарантия того, что скачанный пользователем exe уже пригоден для работы. Сам installer смотрится отдельно в [installations.md](../01-functional/installations.md).

## Не переносить только по наличию определения

- `src/ui/settings/api_settings/dialogs/protocol_pipeline_dialog.py:15-108` реализует ordered transforms editor (`add/remove/up/down/reset`), но прямые references из `src` в этом snapshot обнаружены только внутри самого файла. **Runtime reachability — `UNRESOLVED`**, не объявлять обязательным открываемым диалогом без producer evidence. Возможность редактирования transforms как концепция может существовать через другой UI; проверять отдельно.
- `src/ui/settings/api_settings/dialogs/new_preset_dialog.py:11-98` реализует шаблон, автозаполнение имени и cancel/accept, но в текущем static search отсутствует вызывающий Python код. **Статус диалога `UNRESOLVED`**. Существование операции создания пресета подтверждается другим API UI, а не этим отдельным классом.

## Требования и открытые вопросы

- `REQ-UI-MODEL-001`: отображать каталог и подробную metadata только в мере фактического ответа провайдера, без обязательных `pricing`/`rate_limits`.
- `REQ-UI-MODEL-002`: модель выбирается по устойчивому model ID; UI-search, free/paid filter, clipboard export и сортировка являются отдельными функциями.
- `REQ-UI-MODEL-003`: отсеивать результаты проверки другого пресета; показывать pending/success/error состояния.
- `REQ-UI-VOICE-001`: скрытие прогресса не прерывает загрузку, отмена является другим намерением; сохранять status projection после скрытия.
- `REQ-UI-DEPS-001`: установка и отсутствие FFmpeg сопровождаются разными состояниями и понятной ручной альтернативой.
- `REQ-UI-REACH-001`: диалог или контроллер из исходников становится требованием паритета лишь при доказанном пути регистрации или запуска.

**Validation backlog:** fixture ответа API с/без model_infos; free/paid mixed filter; сохранение выбранного model ID и защиты от late test event; modal hide vs cancel; отображение ручной установки FFmpeg; reachability search для двух неподтверждённых диалогов. Тесты PyQt на этой итерации не выполнялись.

Связанные материалы: [api-presets-and-model-parameter-editor-workflows.md](api-presets-and-model-parameter-editor-workflows.md), [local-voice-model-management-and-compile-dialogs.md](local-voice-model-management-and-compile-dialogs.md), [dialog-interaction-and-background-task-contracts.md](dialog-interaction-and-background-task-contracts.md).
