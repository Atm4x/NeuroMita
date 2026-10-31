# Telegram: интерактивная авторизация, диалоги и разрешение requests

**Срез:** `CodeNow.zip`, 2026-10-30. **Статус:** `CONDITIONAL` — только при подключении Telegram с неавторизованной user session и видимом GUI. Кнопки и API подтверждены по исходникам; PyQt UI E2E не исполнялся.

## CAP-UI-TG-AUTH-001 — диалог кода и пароля 2FA

`src/handlers/telegram_handler.py:305-425` запускает Telethon user login с retries и получает input через `TelegramAuthService.request(kind='code'|'password', error, attempt)`. `src/services/telegram_auth_service.py:19-74` сохраняет pending `Future` и owner asyncio loop под случайным `request_id`, публикует EventBus событие только с metadata, защищает request timeout (default 180s, min5) и отвергает отсутствие UI (headless). `resolve/reject:76-119` завершают originating Future через `loop.call_soon_threadsafe`; поздний response после timeout уже не найдёт pending request.

`src/controllers/gui/dialog_controller.py:6-43` подписывается на `PROMPT_FOR_TG_CODE`/`PROMPT_FOR_TG_PASSWORD` и передаёт `request_id`, error в Qt signal (поле `attempt` из исходного event не передаётся). `src/ui/windows/app_window_base.py:1310-1324` открывает соответствующий dialog. `src/ui/dialogs/telegram_auth_dialogs.py:159-233` создаёт modal `dialog.exec()`, принимает submit по button/Enter, запрещает пустое значение, при Submit отправляет `SubmitTelegramAuth(request_id, value)`; при Reject отправляет `RejectTelegramAuth(request_id, reason)` **если** ранее не был submit. Интенты обработаны `src/controllers/gui/telegram_auth_view_model.py:18-28`, который вызывает service. Для password input используется password field в `_build_auth_dialog:88-156`. Это чёткая round-trip транзакция user prompt→intent→future completion, не прямой вызов Qt из worker.

## Пограничные состояния

Список состояний: `waiting/queued UI` → `modal open` → `submitted|rejected|timed out|shutdown`, а network auth отдельно `code requested` → `code invalid/expired` → `retry`, либо `2FA needed`. Ошибка `try_emit` отвергает pending Future (`telegram_auth_service.py:58-74`). Если EventBus принял событие, но UI не создал окно, service всё равно завершит ожидание по timeout. Принятое EventBus событие ≠ доказательство успешного показа modal (не проверялось).

**Существующие ограничения:** отсутствие PyQt6 блокирует запуск UI-тестов в этой среде; `DialogController` в коде не проверяет `self.view` перед TG signal emit (`dialog_controller.py:31-43`) — отсутствие view в момент callback является статическим риском ошибки, а не воспроизведённым случаем. Старые callbacks с истёкшим request_id отбрасываются `TelegramAuthService._take`. Попытки UI без времени/attempt metadata требуют уточнить, нужно ли показывать retry count в новом интерфейсе. Telethon создаёт session файл `session_name` отдельно от GUI credentials; отображать session authenticated и credentials-complete как одно состояние нельзя.

## Требования

- `REQ-UI-TG-001`: визуальная авторизация по коду и 2FA, submit/cancel/error/retry, без утечки password в state/log.
- `REQ-UI-TG-002`: request-scoped identity для промптов, один terminal outcome, timeout и shutdown cleanup; без зависания при отсутствующем UI.
- `REQ-UI-TG-003`: headless режим должен явно сообщать невозможность интерактивной авторизации либо использовать предварительно сохранённую разрешённую session; она не создаётся магически.
- `REQ-UI-TG-004`: account/session credentials, bot readiness и voice synthesis availability — разные измерения состояния.

**Невыполненные тесты:** просроченный code, 2FA три ошибки, параллельные auth prompts, view destroyed before signal, пользовательское закрытие окна, session reuse после рестарта, фактический диалог Telegram с внешней сетью. Состояния/валидация частично исследованы по коду.

**Связано:** [Telegram voice](../01-functional/telegram-voice.md), [GUI dialog lifecycle](dialog-interaction-and-background-task-contracts.md), [settings and secrets](../01-functional/settings-storage-and-migrations.md).
