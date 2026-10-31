# AI Hub — трассировка пользовательских действий до результата

## CAP-UI-AIHUB-ACTIONS-001 — взаимодействия пользователя

**Назначение:** изолировать оставшийся GUI workstream как перечень *конкретных пользовательских операций*, а не оценивать готовность интерфейса числом файлов. **Статус:** `ACTIVE/CONDITIONAL` по операции. Основные источники: `src/ui/windows/ai_hub/dialog.py`, `src/controllers/gui/ai_hub_view_model.py`, `src/controllers/gui/ai_hub_settings_view_model.py`, `src/controllers/installable_controller.py`.

| User action | Intent/backend boundary | Видимое состояние/данные | Evidence и предел |
|---|---|---|---|
| Открыть AI Hub впервые | `ActivateAIHub` → optional `install` GUI → metadata refresh | Не все статусы известны на первом кадре | `ai_hub_view_model.py:71-109,110-145` |
| Переключить категорию | UI category → filtered cards; при необходимости selective status pass | TTS, voices, ASR, RAG, extras/beat, backend, dependencies | `ui/windows/ai_hub/dialog.py:906-956` |
| Выбрать backend filter/поиск | Локальный фильтр уже полученных metadata/status | Без удаления компонентов из реестра | `dialog.py:1005-1047` |
| Нажать Refresh | `RefreshAIHub(force=True)` → invalidate/reprobe | Spinner, timestamp, checking, error | `dialog.py:390-399,743-787`; `ai_hub_view_model.py:110-145` |
| Открыть карточку | View row metadata + compatibility + status | Описание, backend, поддержка, installed/ready, кнопки | `dialog.py:1113-1168`; [manifest](../01-functional/installable-catalog-identity-and-coverage.md) |
| Install | `RequestComponentAction` → preview/confirmation → queue admission | Preparing → queue → progress → recheck | `ai_hub_view_model.py:171-298`; [queue](../03-runtime/install-operation-admission-queue-and-completion.md) |
| Clean reinstall | Install intent с `clean=True` | Отличается от стандартного install | `dialog.py:1155-1164`, `ai_hub_view_model.py:171-220` |
| Uninstall | Отдельная component operation | Confirmation, task/progress, recheck | `dialog.py:1155-1164`; `installable_controller.py:144-163` |
| Initialize | Поддерживаемая component action, не всегда кнопка карточки | Возможен empty no-op plan | `ai_hub_view_model.py:43-45`; `installable_catalog_service.py:456-512` |
| Показать required backend | `install_preview()` + hardware information | Подтверждение дополнительного системного runtime | `installable_catalog_service.py:371-454`; `dialog.py:1359-1423` |
| Cancel pending | `CancelQueuedInstall` → `InstallQueueService.cancel_queued` | Строка исчезает из pending | `ai_hub_view_model.py:95-99`; `install_gui_controller.py:131-145` |
| Cancel running | `CancelRunningInstall` → cancel_event | «Cancelling...», задача может ещё выполняться | `install_gui_controller.py:147-168` |
| Смотреть progress/logs | Events TASK_STARTED/PROGRESS/FINISHED/FAILED | Progress bar, детали/лог, ссылка в окне | `ai_hub_view_model.py:418-519`; `dialog.py:181-262` |
| Открыть Settings для компонента | `AIHubSettingsViewModel` → schema/values | Loading, saved/dirty/saving/errors | `dialog.py:848-906`; [AI Hub general](ai-hub.md) |
| Перейти к другой модели с unsaved edits | Предупреждение discard/cancel | Dirty form не теряется молча | `dialog.py:848-899,956-1003` |
| Закрыть singleton окно с dirty form | `confirm_hide_on_close` также при hide-on-close | Discard/Cancel перед скрытием | `dialog.py:956-1003` |
| Очистить кэш загрузок | `ClearInstallCache` → catalog purge cache | Отдельная фоновая задача/результат | `ai_hub_view_model.py:147-169` |
| Открыть папку моделей | UI filesystem action | Открытие локального каталога | `dialog.py:1078-1094`; реальное Windows открытие не проверено |

**Отдельные режимы отображения:** модельные RAG карточки группируются по embeddings/reranker (`dialog.py:1138-1155`); очередь имеет независимые running/pending с global busy (`:1192-1225`); статус может прийти поздно и обновить единственную карточку (`ai_hub_view_model.py:367-397`). Это реальные требования к функциональности новой UI-проекции, **не** утверждение о том, какие именно Rust ViewModels надо создать.

### Что нужно проверить до полного закрытия GUI workstream

Сюда относятся UI компоненты других страниц, которые эта таблица не охватывает: все remaining settings builders, live GUI keyboard/wheel shortcuts, глобальные notifications/dialogs, read-only/service status chips, screen reader/accessibility, сложные динамические формы и E2E с установщиком. В AI Hub останутся full `settings_schema → field validation → save` для всех component types, compile forms, actual Windows path open и реальная отмена внешних процессов. Таблица позволяет проверять каждую action отдельно, не «закрывать 14/20» преждевременно.

**Требования:** `REQ-UI-AIHUB-ACTIONS-001` — полная action/intent/effect traceability; `REQ-UI-AIHUB-ACTIONS-002` — dirty guard; `REQ-UI-AIHUB-ACTIONS-003` — различие installed/status/operation progress; `REQ-UI-AIHUB-ACTIONS-004` — selective status refresh и late event. Никакой Rust UI framework не выбран.
