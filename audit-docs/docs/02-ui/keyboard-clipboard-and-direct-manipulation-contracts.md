# Keyboard, clipboard и direct manipulation в активных экранах

**Цель.** Дополнить функциональный реестр действиями без отдельных кнопок. Поиск проведён по `src/ui/**/*.py` и `src/controllers/gui/**/*.py` по `QShortcut`, `QKeySequence`, `keyPressEvent`, `eventFilter`. Это **не** нормативный полный accessibility audit ОС. Статусы: source-confirmed active UI paths для перечисленных registered components.

| Экран/контрол | Действие без отдельной кнопки | Source | Функциональное следствие |
|---|---|---|---|
| Chat composer | `Enter`/`Return` отправляет сообщение, если доступно; `Shift+Enter` не перехватывается этой веткой | `src/ui/widgets/chat_panel.py:262-287` | Отправка и вставка переноса различаются. Доступность отправки определяется `_send_if_available`, не состоянием клавиши |
| Chat composer | `Ctrl+V`, `Meta+V` или `Shift+Insert` сначала пытаются добавить *изображение* из clipboard | `chat_panel.py:269-282` | Если image staged, событие перехватывается; текстовая вставка работает стандартно при отсутствии image payload |
| Контекст LLM | `Ctrl+F` фокусирует поиск; обзорные ссылки ведут к индексированному сообщению | `src/ui/dialogs/context_viewer_dialog.py:262-269,639-652` | Поиск и навигация по сохранённому контексту без сетевого запроса |
| Граф знаний | `Ctrl+F` открывает поисковый UI для узлов | `src/ui/dialogs/graph_view_widget.py:716-741` | Search/neighbor state — transient UI state, не изменение entity storage |
| Gallery viewer | `Left`/`Right` переключают фотографию, wheel масштабирует картинку, кнопка открывает оригинал во внешней ОС | `src/ui/dialogs/gallery_viewer.py:95-142`, `:25-66` | Preview navigation, open local file and zoom are distinct actions |
| Database viewer | `Delete` удаляет **выделенные** строки после явного confirmation | `src/ui/dialogs/db_viewer.py:295-300,991-1034` | Destructive SQL action; не эквивалент domain soft-delete |
| Voice tabs | `Left`/`Right`/`Home`/`End` меняют выбранную вкладку | `src/ui/widgets/character_voice_tabs.py:335-354` | Выбор модели/вкладки поддерживается и без мыши; wheel прокручивает tab strip (`:356+`) |
| Address scheme editor | Вставка полного URL, копирование полного URL при отсутствии выделения, курсор между scheme и host | `src/ui/widgets/template_url_edit.py:199-239` | Визуальное разделение scheme/address не меняет семантику одной URI-строки; стандартная copy/paste сохраняется |
| Background task dialog | `Escape` скрывает окно, **не** останавливает выполняемую задачу | `src/ui/dialogs/background_task_dialog.py:273-296` | UI dismissal ≠ cancellation; stop — отдельный action |

## Контекст и инварианты

- Обязательные пользовательские действия должны быть доступны в новой презентации вне зависимости от того, окажется ли конкретная комбинация клавиш той же на всех платформах. Исследование сохраняет **возможности**, а не необходимость имитировать Qt event filter.
- Состояния `selection`, `clipboard payload`, `pending image`, `current tab`, `search query`, `background task visible` — представление; изменение durable history, database или playback требует отдельного Core use case.
- Копирование содержимого API request/response может содержать prompt, историю и секреты. В current UI это действие пользователя; будущая модель access control/редакции должна быть осмыслена отдельно, **не** выводится автоматически из копирования.
- Нужны Qt E2E/UI fixtures: image clipboard vs text clipboard, empty send, multi-line chat, modal focus search, tab keyboard, dialog hide vs stop, и случай нескольких выделенных SQLite строк. В этом проходе source прочитан, GUI runtime тест не выполнялся.

**Связанные документы:** [composer](chat-composer-and-attachments.md), [context and DB viewers](context-and-sqlite-data-inspection-workflows.md), [dialogs](dialog-interaction-and-background-task-contracts.md), [gallery](gallery-lifecycle-and-photo-viewer.md).
