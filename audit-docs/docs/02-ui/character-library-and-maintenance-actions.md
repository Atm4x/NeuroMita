# UI библиотеки персонажей и операции обслуживания — карта активных действий

**Capability:** `CAP-UI-CHAR-001—003`; **ACTIVE/CONDITIONAL**. Это аудит экрана и точек вызова; детальная семантика самих миграций/индексов дополняется [data-maintenance](../01-functional/data-maintenance.md) и [compatibility imports](../01-functional/compatibility-imports.md). Исходники: `CodeNow.zip` (снимок без `.git`), 2026-10-30; UI/runtime не запускались.

## Отделить выбранного для настройки персонажа от активного в диалоге

`src/controllers/gui/character_settings_view_model.py:11-35` хранит `selected_character_id`, `active_character_id`, provider choices и names. `src/ui/settings/character_settings/ui.py:498-584` строит двуколоночную библиотеку: поиск/список слева и подробные настройки справа, раздельные блоки Prompt Set, Provider, History, Maintenance, Danger; глобальная Danger Zone ниже секций индивидуального персонажа (`ui.py:372-495`).

`src/controllers/gui/character_settings_logic.py:275-298` прямо разделяет `_configured_character_id` (selected in settings) и active chat character. Переключение выбора в списке (`:684-706`) не меняет собеседника. Event `CURRENT_CHANGED` только обновляет индикатор активного персонажа, выбор не сбрасывается (`:544-566`). Фильтр регистра-независимый (`:677-682`). Это **обязательный пользовательский инвариант**: настройка персонажа Б не должна незаметно переключать активный диалог А.

## Действия для выбранного персонажа

Привязки реальных GUI callbacks — `character_settings_logic.py:534-613`; UI controls — `ui/settings/character_settings/ui.py:140-370`.

| Группа | Действие / data target | Evidence / boundary |
|---|---|---|
| Prompt set | выбор набора, показ author/version/description, reload, открыть папку | `character_settings_logic.py:764-845,846-879`; применяется `CHAR_PROMPT_SET_*` с `RELOAD_DATA` event, не switch chat |
| Provider | отдельный provider per selected character | `character_settings_logic.py:569-571,1040-1047`: key `CHAR_PROVIDER_<id>`, сохранение числового значения, изменения после API preset save/delete/import обновляют catalog `:520-532` |
| История | открыть DB viewer, export/import, очистить историю | `character_settings_logic.py:579-590,973-989,1512-1525,2136-2294`; очистка подтверждается и публикует событие, а не выполняет sync DB mutation прямо в UI |
| Историческая совместимость | files→DB, backup restore legacy memory, tags→structured, обновление формата | `character_settings_logic.py:592-612,1003-1039,1049-1511`; часть операций Worker+progress, различаются cancellation и backup |
| История/RAG | dedupe, индексирование missing embeddings, full reindex | `character_settings_logic.py:600-608,1525-1753,1916-2035`; scopes и ресурсы различаются |

`apply_prompt_set:818-843` требует явного подтверждения при `force_apply`, сохраняет выбор и выпускает `Events.Character.RELOAD_DATA`. Это не доказательство, что reload завершился к моменту popup «успех». `save_character_provider:1040-1047` пишет per-character key; следует тестировать provider switch при незавершённом LLM request.

## Действия для **всех** персонажей

Привязки находятся в `character_settings_logic.py:614-634`, controls в `ui/settings/character_settings/ui.py:372-495`: файлы→БД, tags→data, history viewer/export/import, dedupe, missing-index/full-reindex, очистка всех историй и purge `is_deleted=1` **для всех персонажей**. Они намеренно вынесены из per-character detail. Это разные capability scopes; UI-разделение является важным safety affordance, но не гарантирует транзакционность.

`clear_history:973-989` и `clear_history_all:991-1000` требуют confirmation и публикуют `Events.Character.CLEAR_HISTORY` либо `CLEAR_ALL_HISTORIES`; их handlers применяют фактические изменения **позже**, поэтому нельзя считать confirm dialog commit acknowledgment. `purge_deleted_data:894-970` идёт последовательно по всем characters, отдельно очищая память и историю с `backup=True`, собирает `errors`, затем вызывает SQLite `VACUUM` и формирует summary. Если один персонаж/операция завершится ошибкой, следующие продолжают работу. Это **частично применимый массовый процесс**, не атомарный all-or-nothing. Успешное открытие финального dialog не означает отсутствие ошибок — ошибки включены в текст summary.

## Reindex/backups/cancel: UX-границы

- `ReindexAllCharactersWorker` и `FullReindexAllCharactersWorker` — отдельные классы (`character_settings_logic.py:94-244`), а single-character operations — иные entrypoints (`:1670-1753,1916-2035`). Нельзя приравнивать incremental и full-reindex по эффектам и времени.
- Имеются callbacks progress/error/cancel/finished и диалоги, но истинная остановка вычисления/rollback зависит от внутреннего worker и соответствующего manager; это нужно проверить отдельным test harness, а не по наличию кнопки cancel (`character_settings_logic.py:1803-1915,2036-2135`).
- `purge_deleted_data` проводит VACUUM даже после ошибок по отдельным characters; данные после отдельных steps могут быть изменены. Место записи backup и возможность restore должны проверяться на уровне реальных менеджеров, а не по тексту confirmation popup.
- Per-character и all-scoped export/import имеют отдельные entrypoints. Переносить в новую реализацию **семантическую область действия**, а не только UI label.

## Требования для новой реализации (без выбора Rust-архитектуры)

- `REQ-UI-CHAR-001`: независимые selected-for-settings и active-in-chat identities; смена выбора для настройки не запускает разговор/смену активного персонажа.
- `REQ-UI-CHAR-002`: явное scope каждой операции (`one character` / `all characters`), подтверждение опасных операций и правдивый outcome `requested/running/partial/succeeded/failed/cancelled`.
- `REQ-UI-CHAR-003`: per-character provider/prompt-set selection и reload имеют stable character id, отсутствие stale UI result при смене selection, сохранение данных с контролируемыми событиями.
- `REQ-UI-CHAR-004`: bulk maintenance report содержит per-character outcomes и recovery/provenance backup; нельзя выдавать частично завершённый purge/индексирование за атомарный успех.

## Что ещё требуется исследовать

Полная последовательность событий и транзакционные гарантии `CLEAR_HISTORY`, очередь resource locks при all-character reindex, дедупликация по сохранённой identity и on-disk format legacy backup должны быть окончательно сведены с managers/tests. Текущий документ — **трассировка UI действия → команда**, не утверждение об успешном disk mutation после клика. Использовать совместно с документами history/RAG/persistence.
