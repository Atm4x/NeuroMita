# Sandbox — функциональный контракт страницы и inspector

**Source snapshot:** `CodeNow.zip`, 2026-10-30. **Status:** `ACTIVE` (основная зарегистрированная страница приложения), отдельные возможности `CONDITIONAL` (game link, voice, capture, RAG). **Capability:** `CAP-UI-SANDBOX-001`. **Метод:** Python source only, без интерактивного PyQt запуска. Документ фиксирует функциональность, не QWidget-структуру как цель переноса.

## Назначение и композиция

Sandbox объединяет live chat и панель инспектора текущего персонажа. `src/ui/pages/sandbox_page.py:608-673` получает `SandboxPageViewModel`, отдельные `CharacterStatePanel` и `ChatPanel` viewmodels/actions, связывает `state_changed` → `render`, `effect_emitted` → handler, закрытие страницы → `view_model.close()`. Панель inspector состоит из **Session**, **State**, **Debug** и сворачиваемого rail (`:2446-2605`). Главный ChatPanel — отдельный компонент со своей моделью и требует самостоятельного chat action inventory; его нельзя считать покрытым этим файлом.

## Владелец состояния и действия

`src/ui/pages/sandbox_presentation.py:10-145` задаёт неизменяемые dataclass `SandboxState`, `SandboxMemoryState`, `SandboxBudgetState`, `SandboxLastRequestState`, `SandboxStatusState`, selectors и набор именованных intents. `src/controllers/gui/sandbox_page_view_model.py:58-129` принимает активацию, refresh-section, переключение персонажа/модели/пакета промптов, настройку, clear history, открытие истории, обновление голосовых панелей. `:75-95` подписывается на model start/success/fail, token budget, settings/status, install/voice model results, history/character updates и API preset changes. `:144-272` пересчитывает selectors, memory summary, status, budget через `run_coalesced`, не через прямой блокирующий запрос Qt при каждом render.

**Presentation update semantics:** `sandbox_page.py:691-740` сравнивает поля предыдущего и нового `SandboxState` и обновляет только изменившиеся части. `:1435-1482` на активации запускает отложенный ряд refresh с ticket и проверкой активной страницы; устаревшие запланированные UI callbacks не выполняются. Это presentation-level stale update fence, но не доказывает такую же защиту всех async queries в backend; их coalescing следует изучать отдельно.

## Action inventory, подтверждённые входы

| Пользовательский сценарий / источник | Контракт, side effect и ownership |
|---|---|
| Выбор персонажа `sandbox_page.py:1221-1235`; `sandbox_page_view_model.py:305-313` | `SandboxCharacterSelected` → `SandboxPageController.select_character()` → `Events.Character.SET_CURRENT` с `reload_data`; не прямая SQL-модификация. Обновляются avatar, selectors и chat panel. |
| Model/prompt indicator в Session `sandbox_page.py:1783-1900`; `sandbox_page_controller.py:75-140` | Сессионный label отражает effective `CHAR_PROVIDER_<character_id>` либо `LAST_API_PRESET_ID`; настройки персональной привязки находятся в соответствующем settings. Отдельные intent handlers для селекторов существуют (`:1164-1218`), но актуальный UI показывает read-only labels — не приравнивать старые callback methods к разрешённым controls. |
| Gear/quick action → Settings `sandbox_page.py:894-905,1853-1861` | Deep link `force=True`, можно открыть даже скрытый раздел; `subsection` поддерживается. |
| Voice / microphone / instant send / RAG switch `sandbox_page.py:907-956,1056-1108` | Typed `SandboxSettingChanged` (ключи `USE_VOICEOVER`, `MIC_ACTIVE`, `MIC_INSTANT_SENT`, `RAG_ENABLED`) и optimistic dot; runtime start/stop наблюдает settings registry отдельно. Instant-send subordinate row скрывается при выключенном микрофоне. |
| Game link `sandbox_page.py:957-975` | Switch OFF ставит `GAME_BLOCK_LEVEL="All events"` и `IGNORE_GAME_REQUESTS=True`; ON только снимает ignore, **не** возвращает прежний block level. Connection chip показывает реальный `GameLinkService.is_connected()`, это иная ось, чем mute. |
| Capture toggle `sandbox_page.py:2168-2202` | Screen analysis, auto attach, camera; state из settings, обратная синхронизация с блокировкой widget signals. |
| Display toggle `sandbox_page.py:2290-2356` | Show thinking, timestamps, system/context messages, token/cost stats. Эти ключи меняют видимость, не содержание сохранённой истории. |
| Last request/context `sandbox_page.py:2134-2166,2204-2207` | Просмотр последнего контекста через host handler; request summary приходит по model events и budget. |
| Reset character `sandbox_page.py:2209-2226` | Стандартное подтверждение `Yes/No`, default No, затем intent → `Events.Character.CLEAR_HISTORY`; текст говорит об очистке истории **и состояния**. Надо проверить downstream semantics события; emit сам по себе не доказывает сохранённый commit. |
| Инспектор State `sandbox_page.py:2227-2284` | Показ memory/history counts, forgotten, missing indexes, trash, last activity, DB size; быстрый переход в RAG/memory settings. |
| Инспектор Debug `sandbox_page.py:2286-2441` | Session summary, refresh, открытие DB/логов/API и подключённая `debug_settings.setup_debug_panel_controls`: системное debug-сообщение, save/load snapshot, context. Исследовать эти операции отдельно как самостоятельные actions. |
| Сворачивание inspector `sandbox_page.py:2516-2605` | Ephemeral 420↔60 pixel rail; клики по иконке rail сразу разворачивают нужный tab, список tabs сохранён в состоянии виджета, не БД. |

## Семантика состояния, ошибок и инварианты

- `sandbox_page_view_model.py:315-333`: настройка отражается оптимистично, откатывается только при **синхронном** исключении SettingsService. Отложенная ошибка долговременной записи из SettingsManager не имеет здесь автоматической обратной транзакции. Отображение ≠ durable commit.
- `sandbox_page_controller.py:36-52`: смена персонажа и clear history выполняются через EventBus.emit, где обработчик может исполняться позже в async lane. Следовательно `SandboxPageViewModel._clear_history` (`:334-339`) завершение метода не означает завершение destructive operation — нужно отдельное completion/failed event в целевом контракте.
- `sandbox_page_view_model.py:364-422`: время последнего запроса основано на одном `self._request_started_at`; события model start/finish без собственного correlation id в UI state. При параллельных запросах может быть неверная latency/finished-model annotation; это **static concurrency risk**, не воспроизведённая ошибка.
- `:250-272` неизвестная стоимость `None` преобразуется в 0.0; такой визуальный zero нельзя автоматически толковать как бесплатный запрос (см. [token budget](../01-functional/token-budget-and-pricing.md)).
- `:212-248` memory summary использует effective prompt-history count либо active history fallback, а также missing indices и soft-deleted counts. Это разные величины, не взаимозаменяемые метрики.
- `sandbox_page.py:1435-1482` activation ticket защищает только scheduled callbacks; teardown `view_model.close` отписывает subscriptions; проверить deferred worker cancellation и owner semantics в отдельной fault-driven UI проверке.

## Требования и валидация

`REQ-UI-SANDBOX-001`: сохранить одной страницей chat, controls активного персонажа, инспектор Session/State/Debug, collapsed/expanded rail и быстрые глубокие переходы в Settings; `REQ-UI-SANDBOX-002`: отделять connection state, mute state и feature enable/health, не интерпретировать «игра подключена» как «игровые события разрешены»; `REQ-UI-SANDBOX-003`: сохранять обратную синхронизацию settings, условную доступность controls, refreshing без stale UI repaint; `REQ-UI-SANDBOX-004`: destructive commands и persistent settings должны иметь явный `accepted / committed / failed`, без успеха от одного EventBus.emit; `REQ-UI-SANDBOX-005`: last request и budget projections должны сохранять provenance/correlation и unknown semantics.

**Тестовые сценарии:** toggle mic off/on с подчинённым instant-send; смена модели/персонажа при async refresh; voice install event; game connected+muted четыре комбинации; унаследованный preset персонажа; click gear для hidden settings section; повторное открытие после закрытия; два перекрывающихся запросa; reset rejected/accepted, event worker fails; read-only session fields; fallback цены отсутствует; renderer flags; collapse rail with selected Debug tab.

**Не закрыто в этом проходе:** chat bubble/editor attachments/actions и keyboard shortcuts в `ChatPanel`; конкретные операции в `ui/settings/debug_settings.py`; все callbacks `CharacterStatePanel`, визуальные детали/высота окон, история сессий и DB commit under event execution. Не объявлять GUI аудит полным.

**Связи:** [Settings UI](settings-navigation-and-lazy-pages.md), [Settings storage](../01-functional/settings-storage-and-migrations.md), [token pricing](../01-functional/token-budget-and-pricing.md), [events](../03-runtime/typed-services-and-settings-observers.md), [functional traceability](../06-design-input/feature-traceability.md).
