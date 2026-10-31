# Home launcher: primary action, selective updates и состояние Unity

**Capabilities:** `CAP-UI-HOME-001—003`, **ACTIVE/CONDITIONAL**. Source `CodeNow.zip` (2026-10-30); продуктовый контракт GUI и orchestration, не повторное проектирование updater или целевой Rust UI. Связанные документы: [launcher updates](../01-functional/launcher-and-updates.md), [build/release](../03-runtime/build-and-release-distribution.md), [news](news-and-logs-live-ui-contracts.md).

## Основное управление

`src/ui/pages/home_page.py:146-244,330-412` отображает две карточки статуса (Python backend/Unity), флажки выбора компонента обновления, primary button с progress/icon, панель новостей и extra menu. `src/controllers/gui/home_page_view_model.py:76-183` централизует intents, подписан на events installer start/progress/finish/fail и на процессные сигналы Unity.

`_primary_action` (`home_page_view_model.py:459-473`) задаёт приоритет: `starting/stopping` → недоступное действие, если Unity `running` → **stop**, иначе при `pending restart` → **restart**, иначе при выбранных updates → **apply**, иначе при установленной Unity → **play**, иначе unavailable. `_run_primary_action:283-303` dispatch соответствующей операции. **Важно:** кнопка не всегда «запустить игру»; во время игры она останавливает Unity и может перекрывать доступность pending Python restart. UI disable, пока `operation != None`, открыт progress state или primary action неактивен (`home_page.py:352-381`).

Extra menu (`home_page.py:560-581`) предоставляет force update check, переход в настройки updates, открытие каталога Unity; stop game — только если game state=running. Home activation вызывает refresh local/process, news и (в зависимости от настроек) update checks (`home_page_view_model.py:116-127`).

## Избирательное обновление Python и Unity

`HomeToggleUpdate` отдельно допускает Python только при `available`, Unity при `available` **или** `installable` (не установлена) (`home_page_view_model.py:305-327`); пользователь может выбрать оба компонента. Check result обновляет карточки, сохраняет выбранное только при соответствии сохранённого previous state; pending Python restart скрывает предложение нового Python update (`:329-373`).

`_request_selective_update:509-530` отклоняет запрос, если операция уже идёт или не выбрано ни одного компонента. Для `UPDATE_CONTOUR == "test"` при отсутствии tester code вызывается password dialog; `HomeTesterCodeSubmitted` проверяет точный continuation id, отсутствие кода отменяет операцию до запуска, введённый code сохраняется в settings (`:532-552`, `home_page.py:515-533`). Это явный admission step, не свойство всех installables.

`_start_selective_update:554-670` формирует flags per selected component, snapshot settings, один `threading.Event` для cooperative cancel, компоненты/этапы/счётчики progress. Worker вызывает `HomePageController.apply_updates` с channel, tester code, unity dir, update_mode (`diff` default), `UPDATE_PRESERVE_PROMPTS` и progress/extract/verify/stage callbacks. Поэтому **раздельные настройки канала, сохранения пользовательских промптов и режима diff** — реальные параметры процесса. На `Cancel` выставляется event и disables повторную отмену, но не объявляется мгновенная остановка подпроцесса (`:710-721`).

### Очень важный terminal contract

`completed:612-662` отличает `cancelled`, `ok=False`, `python_pending_restart` и успешный финал. Даже если после успешного Python шага последующий Unity шаг завершился ошибкой или пользователь отменил операцию, `python_applied=True` приводит к `_mark_python_restart_required(pending_python_version)` и `HomePromptRestart` **после** завершения последовательности. Это правильный сигнал о частичном применении нескольких компонентов: `all failed` не должно скрывать уже применённый Python artifact. Но UI показывает общий error/cancel plus restart dialog; нет подтверждения атомарной компенсации всей пары.

`_finish_operation:671-688` очищает running/ownership state, обновляет local status и повторно проверяет updates; `prompt_restart=True` вызывает confirmation modal (`home_page.py:534-550`). Отказ от немедленного restart не означает, что update откатился; pending marker остаётся. Unity restart/stop и launch ошибки отображаются как отдельные эффекты (`home_page_view_model.py:723-790`).

## Lifetime и UI ownership

- `HomeNewsItemState` проецирует до трёх news cards (`home_page_view_model.py:792-814`); клик на release передаёт ID через `HomeOpenRelease` → `page_actions.open_release_page`, не открывает новый unrelated backend (`home_page.py:554-556`).
- Progress presentation содержит собственные фазы download/extract/verify/stage; число байт/этапов относится к **операции компонента**, а не к общей готовности всей установки (`home_page_view_model.py:815-969`).
- Смена языка вызывает refresh labels и news; не должна запускать установку повторно. Привязка home view-model и Qt lifetime через close signal есть, но отмена на закрытие окна и process ownership `HomePageController` проверяются отдельно.

## Требования (функциональные, не целевой Rust дизайн)

- `REQ-UI-HOME-001`: primary action однозначно выводится из GameProcess/Install/PendingRestart/Selection state; нельзя запустить новую game/update операцию при incompatible running state.
- `REQ-UI-HOME-002`: выбор независимых Python/Unity components, forced release check, test channel tester-code admission и сохранение выбранных user asset groups являются отдельными подтверждаемыми use cases.
- `REQ-UI-HOME-003`: многоэтапное обновление имеет per-component outcomes и явный `partial` result: Python applied + Unity failed/cancelled всё равно потребует restart и не должно потерять committed Python state.
- `REQ-UI-HOME-004`: Cooperative cancel, stage progress, stale status refresh, restart refusal/acceptance, GameProcess failure и home/news navigation имеют разные точные user-visible состояния.

## Открытые вопросы / проверки

Тесты через fault injection: `Python applied → Unity fails`, cancel between components, app restart declined, pending marker during Unity running, switch release/test contour between selected and worker, missing tester code, old callback after close, interrupted restart and pending update activation. Никакие реальные обновления и игры в исследовании не запускались.
