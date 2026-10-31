# Подтверждения, отказ, повторная попытка и destructive operations в GUI (Pass 12)

**Задача:** восстановить поведение пользователя у modal-confirmation ветвей, а не переносить `QMessageBox` как целевую модель. Статический просмотр исходников `CodeNow.zip`: **29 прямых callsite `QMessageBox.question`** в `src` вне `utils/Testing`, по файлам, перечисленным ниже. Число учитывает и библиотеку `managers/prompt_catalogue_manager.py`, достижимость конкретной кнопки которой отдельно не доказана. Не включает кастомные `QMessageBox(...)` объекты, `QDialog.exec()`, `StyledMessageDialog` и arbitrary GUI alerts — все виды подтверждений ещё не исчерпаны.

## CAP-UI-CONFIRM-001 — подтверждения, которые предшествуют реальной операции

| Операция | Откуда | Что означает согласие / что означает отказ |
|---|---|---|
| Сброс Sandbox персонажа | `ui/pages/sandbox_page.py:2213+` | Согласие отправляет action reset, отказ оставляет текущую сессию; операция не совершается самим message box |
| Удалить prompt set | `managers/prompt_catalogue_manager.py:134-148` | Подтверждение перед удалением набора, но активность этого manager в конкретной UI цепи проверяется отдельно |
| Применить prompt set | `controllers/gui/character_settings_logic.py:818-838` | Явное разрешение `force_apply=True` перед изменением выбранного набора в настройках; не переносить требование подтверждения на каждый programmatic update |
| Очистить историю выбранного | `character_settings_logic.py:973-990` | `CLEAR_HISTORY` с `character_id` через EventBus; отказ — без события |
| Очистить всю историю | `character_settings_logic.py:991-1001` | `CLEAR_ALL_HISTORIES` через EventBus; это отдельный scope и recipient identity |
| Физически удалить помеченные факты памяти | `character_settings_logic.py:897-950` | Предварительный warning о резервном копировании, затем worker purge выбранных ID; `is_deleted=1` — не все факты памяти |
| Перевести историю в structured формат | `character_settings_logic.py:1003-1027` | Backup обещан самим пользовательским сценарием; после подтверждения запускается migration outcome с count |
| Импортировать JSON историю в SQLite | `character_settings_logic.py:1048-1098` | Две операции `migrate_to_db` и `migrate_to_db_all`, оба scope с подтверждением, сохранением старых файлов |
| Восстановление legacy memory | `character_settings_logic.py:1101-1196` | Сначала выбор источника и preview/warnings; согласие допускает worker только после preview. Второе подтверждение (`:1242-1251`) предлагает `allow_reimport=True`, если архив, вероятно, уже обрабатывался |
| Structured migration данных | `character_settings_logic.py:1405-1469` | Подтверждение перед переразметкой текста/тегов, далее отдельное окно progress/cancel |
| Дедупликация истории | `character_settings_logic.py:1520-1556,1590-1626` | Два scope: текущий персонаж / все персонажи, оставление строки с минимальным ID; после подтверждения `TaskWorker` |
| Дозаполнить отсутствующие embeddings всех персонажей | `character_settings_logic.py:1806-1832` | После подтверждения запускается exclusive worker / `BackgroundTaskDialog`; не равно полному пересчёту |
| Полная переиндексация embeddings | `character_settings_logic.py:1918-1950,2038-2065` | Отдельные current/all операции с предупреждением о перезаписи существующих embeddings |
| Удалить весь граф | `controllers/gui/rag_memory_controller.py:626-643` | Разрушительная команда графового store; независима от очистки исходных history/memory |
| Объединить дубли памяти | `controllers/gui/rag_memory_controller.py:1275-1314` | Подтверждение плана с количеством пар; затем worker/DB операция, не мгновенный UI-only merge |
| Удалить fine-tuning dataset | `ui/settings/data_settings.py:399-419` | `ClearFineTuneData()` intent, физическое удаление файлов позже через view model/service |
| Удалить TorchInductor/Triton compilation cache | `ui/windows/ai_hub/settings_panel.py:413-433` | `DeleteAIHubModelCompilation()` intent для общего кэша, а не для одной модели/видеокарты |
| Удалить RAG preset | `ui/settings/rag_preset_widget.py:95-108` | `DeleteRagPreset(name)` intent; не путать с удалением downloaded models или истории |
| Удалить строку в World.db editor | `ui/dialogs/db_viewer.py:990-1004` | Число выделенных строк и таблица в предупреждении; после Yes отдельный DB edit |
| Удалить API preset | `controllers/gui/api_settings/editor_mixin.py:689-720` | Отдельно спрашивает судьбу unsaved changes и подтверждает удаление; preset editing имеет guards |

## CAP-UI-CONFIRM-002 — согласие на последующую операцию, которая может быть отложена

- **Необходимые RAG-модели:** `ui/settings/rag_preset_widget.py:109-133` предлагает положить **несколько** отсутствующих моделей в очередь (`InstallMissingRagModels`) при применении preset; согласие не означает немедленную готовность моделей.
- **API preset dirty state:** `controllers/gui/api_settings/presets_mixin.py:177-201` диалог `Save / Discard / Cancel` при переключении. `Cancel` восстанавливает предыдущий выбор; `Save` инициирует асинхронное сохранение и pending selection, а `Discard` позволяет переключиться. Это не сводится к бинарному `confirm_delete`.
- **Новая версия на Home:** `ui/pages/home_page.py:535+` подтверждение после установки обновления для перезапуска; install outcome и restart — два самостоятельных пользовательских решения.
- **Voice model controller:** `controllers/gui/voice_model_controller.py:132-155` предоставляет общий confirm helper для модели; конкретные вызывающие действия/экран следует трассировать по фактическим аргументам, не считать каждый helper отдельной возможностью.

## CAP-UI-CONFIRM-003 — продемонстрированные переходы состояния

Для destructive/long-running workflows во многих местах подтверждён шаблон **preview → user consent → admission/background job → result/progress**. Его надо сохранить функционально, но не копировать `QMessageBox` или `TaskWorker`: файлы/SQL/очереди владеют состоянием отдельно. Наличие 29 `question` вызовов не является количеством confirmation types: в историческом редакторе несколько разных операций используют один и тот же тип ввода, а dirty-state у API имеет три исхода.

Отказ не должен удалять данные, менять пресет, отправлять gameplay command или начинать download job. Завершение UI-диалога не равно успешному результату worker; закрытие progress/hide также не является cooperative cancellation без отдельного request.

## REQ и паритетная проверка

- `REQ-UI-CONFIRM-001`: операции с удалением/перезаписью durable данных имеют явный пользовательский барьер согласия и scope (текущий/all); описывать effect только после приёма команды системой.
- `REQ-UI-CONFIRM-002`: preview и факт возможного дублирования legacy restore — отдельные стадии, решение о повторном импорте следует после результата «already imported».
- `REQ-UI-CONFIRM-003`: `Save/Discard/Cancel` для dirty preset и `offer download` при отсутствующих RAG-моделях имеют разные переходы; не объединять с обычным Yes/No.
- `REQ-UI-CONFIRM-004`: нажатие Yes на update restart/compilation delete/RAG model install означает initiation, не подтверждение завершения.

**Пределы:** counts — синтаксические, а не проверка реально открытых Qt окон; тесты с GUI не выполнялись. Popup errors, permissions и все `QMessageBox(...)` instances не входят в эту матрицу. Legacy/standalone scripts не получают статус ACTIVE без входящего вызова. См. [достижимость именованных диалогов](dialog-class-reachability-and-action-outcomes.md) и [системные file pickers](native-dialogs-and-file-input-output-workflows.md).
