# Диалоги: редактирование, экспорт, предупреждения и фоновые задачи

**Capability IDs:** `CAP-UI-DIALOG-001—005` — source-confirmed ACTIVE paths; отдельные окна и опции условны по месту вызова. Срез `CodeNow.zip`, 2026-10-30. Здесь исследованы проверенные экземпляры, **не полный реестр всех QDialog приложения**. Классы PyQt — источники evidence, не предлагаемая целевая архитектура.

## 1. Фоновая задача не равна модальному диалогу

`src/ui/dialogs/background_task_dialog.py:93-119,190-210` задаёт `BackgroundTaskDialog` как `NonModal` с двумя различными действиями. «Скрыть» вызывает `hide()`, **не** прерывая задачу. Нажатие системного X вызывает `closeEvent`, который игнорирует закрытие и скрывает окно, если `_allow_close` не установлен; Esc тоже скрывает (`:273-296`). Программное `finish()` — единственная предусмотренная обычная ветка, разрешающая настоящее закрытие. Отображаемый progress может быть неопределённым (0,0) до первого сообщения; затем determinate с range/значением и показом процентов (`:241-260`). Статусы/подробности динамически увеличивают высоту, но не уменьшают её (`:216-240`).

«Остановить» (`:273-277`) отключает кнопку, изменяет подпись на «Остановка...» и **посылает сигнал** `stopRequested`; сам виджет не останавливает worker. Связь с исполнением изучена на реальном `ReindexAllCharactersWorker` в `src/controllers/gui/character_settings_logic.py:1816-1914`. Там сигнал выполняет `worker.requestInterruption()` с `try/except`, ставит `cancelled=True`, вызывает `finish`; обновления progress/status приходят сигналами worker. Это кооперативный запрос, не доказательство моментальной/гарантированной остановки I/O или записи в БД. На успешном/ошибочном окончании диалог закрывается, есть отдельный cleanup; сигнал о завершении после запроса cancel не должен превращаться в ложное сообщение успеха (`:1853-1906`).

**Требования `REQ-UI-DIALOG-001—002`:** сохранять различия `hide`, `request cancellation`, `finish`; поддерживать reopening скрытой задачи, неопределённый и определённый progress, worker terminal states, не принимать UI-close за rollback. Проверять late callbacks, double stop, close/esc, native hang, failed interruption, ошибку и завершение после запроса отмены.

## 2. Редактор pipeline — transactional UI, не auto-apply

`src/ui/dialogs/message_processing_dialog.py:39-168,198-348` получает payload каталога трансформаций (`transform_catalog`), доступных ID (`available_ids`), базовой цепочки (`base_transforms`) и текущей цепочки (`current_transforms`). Виджет поддерживает add/remove, reorder, reset to base и справку к отдельному transform. Повторное использование ID внутри UI предотвращается вычислением `available - currently_used` (`:244-306`), но детальная доменная валидность pipeline принадлежит вызывающему Core, не QWidget.

`MessageProcessingDialog._steps` возвращает `deepcopy` корректно сформированных записей с непустым `id` (`:188-198`); `transforms()` тоже deepcopies итог (`:347-348`). Кнопка Apply активна только если `_current != _initial`; Reset только если `_current != _base`, то есть **изначально сохранённая** и **базовая** конфигурации — разные опорные состояния (`:303-306`). Cancel → `reject()`, Apply → `accept()`. Реальное применение связывается в `src/controllers/gui/protocol_pipeline_gui_controller.py:13-60`: WindowManager регистрирует singleton/hide-on-close modal dialog, `on_ready` привязывает callback к конкретному экземпляру в `WeakKeyDictionary`; при `accepted` передаёт `dialog.transforms()` в callback. Ошибка callback логируется, но никакой persistence/rollback guarantee сам диалог не даёт.

**Требования `REQ-UI-DIALOG-003`:** фиксировать отдельно `base`, `initial`, `working`; отсутствие mutations до Apply; dedup selections; bounded reorder; cancel without applying; repeated open of cached singleton with new callback/payload; downstream apply failure отдельно от `dialog.accepted`. Тестировать callback from replaced payload and no memory leak on dialog lifecycle.

## 3. Экспорт dataset и SQLite snapshot — разные функции

`src/ui/dialogs/export_dialog.py:23-256` представляет экспорт collected samples для fine-tuning. Фильтры и count preview пересчитываются через `view_model.export_samples`; при неактивном collector отображается disabled/empty state (`:156-214`). У кнопки Export есть выбор raw JSONL vs ShareGPT JSONL, выбор `QFileDialog.getSaveFileName`, затем `view_model.export_to_file(samples,path,sharegpt=...)`; результат показывается как сообщение и после успеха `accept()` (`:215-256`). Cancel file picker ничего не пишет. Preview может стать stale к моменту повторного `export_samples` при реальном экспорте, поскольку выборка исполняется снова. Код не доказывает atomic write/fsync — это контракт view model / storage, который надо проверять отдельно.

`src/ui/dialogs/db_export_dialog.py:16-135` — **другая** операция для `Histories/world.db`: выбор `character_id` либо all, категорий history/memories/variables, активного/забытого/удалённого статуса и периода. Это не alias finetuning exporter. Вызовы из `src/controllers/gui/character_settings_logic.py:2140-2152`; сам диалог собирает параметры, сохранение выполняет consumer после успешного `accept()`. Отдельный source audit underlying DB writer остаётся привязанным к [Data Maintenance](../01-functional/data-maintenance.md).

**Требование `REQ-UI-DIALOG-004`:** отделить export-preview, output-format selection, Save dialog cancellation, success/error и actual writer. Наличие active samples collector не равно наличию истории/памяти в SQLite. Файловые экспорты тестировать на empty state, permission denied, invalid output, partial write, меняющихся записях между preview и export, character scope и deleted status.

## 4. Предупреждения и ошибки

`src/ui/dialogs/styled_message.py:39-90` содержит `StyledMessageDialog` с `level = info/warning/error`, локальным оформлением (icon/color/title/body), selectable текстом и одним OK, который завершает `exec()` через `accept`. Это **модальный alert**, не потоковая нотификация и не error-reporting storage. Фактические вызовы обнаружены в `src/ui/windows/app_window_base.py:346-370` и `src/ui/pages/logs_page.py:172`. Это не замена native message box для подтверждений Yes/No: там используются Qt QMessageBox. Документировать в новой presentation модели как отдельные intent/result types (`confirm`, `inform`, `progress`) без копирования классов.

**Требование `REQ-UI-DIALOG-005`:** сообщения info/warn/error и confirm должны отличаться; ошибки выполнения не должны теряться за успешным закрытием modal dialog; предоставлять текст для копирования; locale и keyboard operation без зависимости от Python Qt hierarchy.

## Обобщённая lifecycle-модель (из поведения, не исходный класс)

| Пользовательское действие | UI state | Core operation |
|---|---|---|
| Hide running progress | hidden, active task | continues |
| Stop running progress | stop requested, disabled button | cooperative interrupt request, eventual outcome unresolved |
| Esc/X while task running | hidden | continues |
| Apply edited pipeline | accepted | callback with copied working pipeline; success не гарантирован |
| Cancel edited pipeline | rejected | no apply callback |
| Export and cancel file selection | dialog stays | no write |
| Export to selected path | result alert then accepted on success | view-model writer, underlying durability unverified |
| Info alert OK | closed | no persistent side effect |

## Пограничные сценарии и пробелы

Статические source paths доказывают **семантику control callbacks**, но не полноценные GUI-интеграционные тесты. Ещё нужно исследовать другие диалоги `context_viewer`, `db_viewer`, `model_parameters`, `models_loaded`, `new_preset`, `voice_action_windows` и установочные confirmation — с требованием проверить регистрацию в WindowManager и действия callers. Параметры SQLite export и записи persistence должны соотноситься с отдельными функциональными документами, чтобы не подменить бизнес-семантику UI-кодом. Нет основания объявлять все dialogs закрытыми одним проходом.
