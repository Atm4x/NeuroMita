# Настройки игровых сценариев: выбор персонажа для мини-игры и Beat Sync

**Назначение:** пользовательские сценарии раздела Game Settings, их входы, состояния, побочные эффекты и связь с Unity. Статус: `ACTIVE/CONDITIONAL` — раздел регистрируется обычным GUI, конкретные функции зависят от настроек и наличия GameLinkService. Исследуемая ревизия: локальный Python snapshot `CodeNow.zip`; runtime GUI не запускался.

## CAP-GAME-UI-001 — ручной запуск мини-игры с указанием персонажа

**Источник:** `src/ui/settings/game_settings.py:35-169,170-247,462-558`; `src/services/contracts.py` (`CharacterRegistry`, `GameLinkService`); [desktop-mini-games.md](../01-functional/desktop-mini-games.md).

В секции «Игры» два действия — запустить шахматы (`chess`) или морской бой (`seabattle`). Каждая кнопка предварительно учитывает три разрешения: `ENABLE_GAMES`, собственный `ENABLE_GAME_CHESS` или `ENABLE_GAME_SEABATTLE`, а при подключении Unity дополнительно `ALLOW_GAMES_WHEN_CONNECTED`. Результат действия — вызов `character.game_manager.start_game_from_player(game_id)` для конкретного выбранного персонажа. Отсутствие загруженного runtime персонажа и отказ менеджера запустить игру отображаются пользователю как отдельные предупреждения.

Особая ветка возникает, когда **текущий персонаж Sandbox отличается от персонажа, с которым игрок говорит в Unity**. UI показывает оба имени в тексте кнопки и предлагает явный выбор `Unity target` / `Sandbox current`. При отмене диалога игра не запускается. Если выбран персонаж Unity, отправляется `Events.Character.SET_CURRENT` на смену выбранного в Sandbox персонажа, затем запускается игра. Это **не** неявная подстановка персонажа по факту подключения Unity: пользователь выбирает владельца действия.

| Состояние | Значение / переход | Источник |
|---|---|---|
| Нет текущего CharacterRegistry runtime | Сообщить о неготовности, не запускать | `game_settings.py:113-133` |
| Unity отключён или target тот же | Запуск с выбранным Sandbox персонажем без отдельного выбора | `game_settings.py:60-112` |
| Unity подключён, target отличается | Диалог выбора; cancel оставляет состояние неизменным | `game_settings.py:81-110` |
| Выбран Unity target, отличающийся от Sandbox | `Events.Character.SET_CURRENT`, затем `start_game_from_player` | `game_settings.py:147-162` |
| Изменено разрешение/персонаж/Unity target | Пересчитать enabled/text/tooltip кнопок | `game_settings.py:170-247` |

Кнопки обновляются не только при редактировании настроек: GUI подписывается на `Events.Character.CURRENT_CHANGED`, `Events.Server.GAME_DIALOGUE_TARGET_CHANGED` и `Events.GUI.UPDATE_STATUS_COLORS`. Это проекция состояния, а не отдельный game runtime. Текущая логика MiniGameManager и реакции на результат описана в [desktop-mini-games.md](../01-functional/desktop-mini-games.md).

## CAP-GAME-UI-002 — управление Beat Sync и пользовательским кэшем

**Источник:** `src/ui/settings/game_settings.py:249-386,550-640`, `src/ui/settings/beat_settings_presentation.py`, описание обработки музыкальных задач — [music-beats.md](../01-functional/music-beats.md).

Режимы backend представлены идентификаторами `auto`, `beat_this`, `librosa`, `dsp_fallback`. GUI получает проекцию `BeatSettingsState` с выбранным и реально разрешённым backend, количеством файлов и размером кэша, возможной диагностикой, флагом `busy`. Изменение режима отправляет `BeatBackendSelected` во view model, не вызывает backend непосредственно.

Операции пользователя: перейти в AI Hub (`BeatOpenHubRequested`), открыть каталог кэша в системном файловом менеджере (`BeatOpenCacheRequested`), выбрать музыкальную папку и инициировать reindex (`BeatRebuildCacheRequested(selected_dir)`). На время `busy` все три action-кнопки отключены. Функционально это независимые операции установки компонента, просмотра существующего хранилища и пересчёта кэша. Включение `BEAT_SYNC_ENABLED` задаёт использование Beat Sync для запросов от Unity; не заменяет выбор режима/обслуживание кэша.

Жизненный цикл: при открытии раздела `BeatSettingsActivated` инициирует первое состояние. При смене языка повторно запрашивается состояние ради новых локализованных labels, что не должно запускать вычисление музыки. `BeatOpenDirectory` вызывает `QDesktopServices.openUrl`, а `BeatShowMessage` — информационный/ошибочный диалог.

## Контракт паритета

- `REQ-GAME-UI-001`: запуск игры требует выбора конкретного персонажа и применимых пользовательских разрешений, с различением Sandbox и Unity target.
- `REQ-GAME-UI-002`: реакция GUI на смену персонажа, Unity target и разрешений должна сохранять enabled/status/text и не приводить к автоматическому запуску игры.
- `REQ-BEAT-UI-001`: различать preferred/resolved backend, операции reindex/open/hub, кэш-статистику и состояние busy.

**Проверки на будущее:** Unity disconnected/connected, одинаковый/разный target, пользовательская отмена, отсутствие загруженного Character runtime, успешный/неуспешный запуск; смена Beat backend, запрет операций при busy, смена локали. **Не проверены:** реальные Qt-диалоги, Unity/GameManager E2E, результаты аудиоанализа. Архитектурный framework GUI не выбран.
