# Действующий каталог персонажей, их идентичность и загрузка состояния

**Capability:** `CAP-CHAR-CATALOG-001—004`. **Статус:** `ACTIVE`; `CONDITIONAL` для неактивных и ещё не материализованных персонажей. Исследуется текущий Python runtime, не желаемая структура будущих Rust-типов. **Источник:** локальный `CodeNow.zip`, `src/managers/character_manager.py:8-229`, `src/characters/__init__.py:9-256`, `src/characters/character.py:80-174,184-259`, `src/services/character_registry.py:8-81`, `src/controllers/character_controller.py:11-114`, `src/ui/character_names.py:5-26`. Код исходников не изменён.

## Каталог девяти регистрируемых identity

`CharacterManager._CHARACTER_DEFINITIONS` (`character_manager.py:41-51`) — источник списка, отличающийся от иерархии всех определённых в Python классов. В нём **девять** персонажей, восемь Mita и один особый GameMaster. `char_id` — стабильная runtime identity; `display_name` — отображение; `storage_name` — имя каталога истории; `short_name` — выбор локальных голосовых ассетов. Эти четыре значения **не взаимозаменяемы**. `ui/character_names.py:5-14` добавляет отдельное локализованное отображение.

| `char_id` | Runtime factory | Display/storage name | Локальный short name | Начальные особые значения `DEFAULT_OVERRIDES` |
|---|---|---|---|---|
| `Crazy` | `CrazyMita` | Crazy Mita | `CrazyMita` | attitude 50, boredom 20, stress 8, FSM `Hello` |
| `Kind` | `KindMita` | Kind Mita | `MitaKind` | attitude 90, stress 0, FSM `Default` |
| `Cappie` | `Cappie` | Cappie | `CappieMita` | boredom 25, FSM `Default` |
| `ShortHair` | `ShortHairMita` | ShortHair Mita | `ShorthairMita` | attitude 70, boredom 15, stress 10, FSM `Default` |
| `Mila` | `MilaMita` | Mila | `Mila` | attitude 75, FSM `Default` |
| `Sleepy` | `SleepyMita` | Sleepy Mita | `SleepyMita` | boredom 40, FSM `Sleeping` |
| `Creepy` | `CreepyMita` | Creepy Mita | `GhostMita` | attitude 40, stress 30, FSM `Default` |
| `Ghost` | `GhostMita` | Ghost Mita | `GhostMita` | attitude 30, boredom 10, stress 30, FSM `Default` |
| `GameMaster` | `GameMaster` | GameMaster | `PhoneMita` | attitude 100, boredom 0, stress 0; `DialogueActorKind.GAME_MASTER` |

**Правило начальных значений:** `Character.BASE_DEFAULTS` → subclass `DEFAULT_OVERRIDES` → optional constructor overrides → `load_config` user/preset overrides → **persisted history/variables** при `ensure_runtime_loaded` (`character.py:136-146,213-259`). Значения из таблицы — **defaults, не доказанные значения в живой сессии**: user variables и saved data их перекрывают. `GameMaster` имеет отдельную роль в обработке Unity/director requests; наличие в character registry не превращает его в обычного девятого участника игровых реплик.

## Материализация и ownership существующего runtime

При старте `CharacterManager(initial_character_id=...)` строит лёгкий индекс девяти определений и регистрирует `character_id → storage_name` в общем resource manager; **не** создаёт сразу девять тяжёлых runtime (`character_manager.py:57-84`). Выбранный `CHARACTER` из settings становится текущим только если ID известен; иначе начальный `Crazy`. `get_all_characters()` возвращает IDs всех доступных, а `get_loaded_characters()` — только материализованные instances. `get_character(id)` создаёт нужную instance при первом запросе, связывает с ресурсами и вызывает `ensure_runtime_loaded()` (`:104-163`); это загружает историю и память один раз.

Смена активного персонажа запускается `Events.Character.SET_CURRENT` с `character_id`, применяется после проверки существования в каталоге; event `CURRENT_CHANGED` содержит ID и display name (`character_controller.py:52-74`). При возвращении к уже загруженному персонажу `CharacterManager` выполняет `reload_character_data`, при первом выборе создаёт его (`character_manager.py:165-199`). `RELOAD_DATA`, `RELOAD_ALL_DATA`, `RELOAD_PROMPTS`, `CLEAR_HISTORY`, `CLEAR_ALL_HISTORIES` — самостоятельные зарегистрированные команды. **Выбор персонажа в settings** и **активный character identity Unity conversation** не обязательно один и тот же источник истины: см. [group dialogue](../03-runtime/conversation-session-projections.md).

`ManagedCharacterRegistry` отдаёт `get`, `all_ids`, `stats_of`, `current`, `current_profile`, `display_name_of` из действительного владельца. `SettingsOnlyCharacterRegistry` нужен для `gui_only`: он знает лишь `CHARACTER` из settings, возвращает `current=None` и `get(id)=None` — **не** следует изображать полноценную загруженную память/статистику в этом режиме (`services/character_registry.py:49-81`). Для ещё не загруженного персонажа `get_character_stats()` берёт сохранённые variables через resource manager без создания тяжёлой instance (`character_manager.py:117-135`).

При `CLEAR_ALL_HISTORIES` менеджер проходит и по runtime-загруженным, и по **не загруженным** участникам каталога, очищая у последних историю, память, working state, граф (`character_manager.py:201-227`). Это важная функция обслуживания, не свойство Python class hierarchy.

## Особенные правила персонажей и legacy-след

`SecretExposedCharacter` используется **только** `Crazy`, `Ghost`, `Creepy` (`characters/__init__.py:9-25,28,94,156`): если structured response содержит `secret_exposed` и не установлен marker `secretExposedFirst`, устанавливается `secretExposed=True`. Дополнительно историческая обработка текстового `<Secret!>` присутствует в `process_response_nlp_commands`; прямое наличие override не доказывает, что legacy text ingress сегодня вызывается. Для остальных шести персонажей специальный typed effect `secret_exposed` нельзя считать гарантированно действующим изменением переменной.

`GameMaster` задаёт `dialogue_actor_kind=GAME_MASTER` и в legacy `<p>...</p>` parser удаляет эти теги, не меняя собственные поведенческие параметры (`characters/__init__.py:232-257`). Обновлённый structured GM effect contract изучается отдельно в [GameMaster](game-master-scene-direction.md).

`SpaceCartridge`, `DivanCartridge`, `Mitaphone` целиком закомментированы в `characters/__init__.py:196-271`, в действующем `_CHARACTER_DEFINITIONS` отсутствуют; status `LEGACY` в контексте настоящего каталога, **не** включать автоматически в требования parity.

## Ресурсы и functional parity независимо от языка

Требуется сохранить: точный реестр доступных IDs и их display/storage/voice relations; fallback при неизвестном initial ID; загрузку персонажа по требованию; доступ к сохранённой статистике без обязательной полной materialization; управление выбором и reload через application commands; очистку данных неактивных персонажей; отдельную идентичность GameMaster; per-character секреты и выбор голосового профиля. **Не требуется** наследование `SecretExposedCharacter` в Rust, класс `CharacterController` или конкретные Python event strings.

Проверки для нового Core: девять catalog IDs и локализованные labels; initial known/unknown; `gui_only` current-profile no runtime; first select vs reselect; persisted variable overrides; simultaneous different actor instance and character ID; clear all including unloaded; selective secret rule; voice asset fallback for `Creepy`/`Ghost` sharing one short_name.

**Открыто:** полный migration mapping старых storage aliases и пользовательских prompt packs, статус internal FSM events из Unity, side effects других `Character` methods beyond structured response. Это не мешает документировать основной действующий функциональный контракт каталога.
