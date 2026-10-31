# Новости релизов и live logs: детальные GUI-контракты

**Capabilities:** `CAP-UI-NEWS-DETAIL-001`, `CAP-UI-LOGS-DETAIL-001`; **ACTIVE** для зарегистрированных страниц, remote release feed **CONDITIONAL**. Уточняет [общий реестр навигации](navigation-gallery-and-help.md); не предполагает использования старого Qt toolkit в Rust. Python source snapshot `CodeNow.zip`, 2026-10-30. Provider/network/Win32 не запускались.

## News releases

`src/controllers/gui/news_page_view_model.py:17-67` получает repository из `target_for_contour(settings.UPDATE_CONTOUR)` на создании страницы и при каждом refresh. `ActivateNewsPage` запускает сетевую загрузку только если список пуст и уже не идёт `loading`; `RefreshNewsPage(force=True)` принудительно вызывает `news.invalidate()` только если repository не изменился. При changed repository сам `set_repository()` должен привести к обновлению cache. `run_coalesced("news-page-refresh")` создаёт фоновую работу, возвращающую **три разных представления**: `items` UI, `releases` для внешних consumers, `content` текст. Результат обновляет `revision` и публикует `NewsPageUpdated`.

`src/ui/pages/news_page.py:19-132` показывает loading placeholder, release cards, `Refresh`, `Open on GitHub`; последний формирует URL GitHub Releases для текущего repository. На каждую смену состояния `render` **пересоздаёт** страницу/Qt widgets (`:74-91`). Внешний переход с Home в конкретный релиз передаёт release ID: `focus_release` ищет card по `itemId`; если widget/card пока отсутствует, сохраняет `_pending_focus_release_id`. После загрузки повторно пытается найти и прокрутить к карточке через `QTimer.singleShot` (`:101-122`). `NewsPageUpdated` вызывает `page_actions.refresh_home_news()` (`:93-96`), то есть Home и News share release-derived content, но разные UI states.

**Риски:** неизменяемый payload для list/result (`immutable_payload`) не означает автоматически generation fencing между сменой repository и готовым worker. При быстром последовательном `release → beta → release` старый result мог бы быть применён без отдельной проверки revision, если `run_coalesced` не изолирует generation; это **вопрос для runner-level теста**, а не подтверждённая race. Pending focus для несуществующего release ID продолжает храниться, потому что `focus_release` возвращает false, пока card не найден; нужно определить expiration/404/empty-list UI.

## Live logs

`src/ui/pages/logs_page.py:68-191`: страница показывает read-only tail общего журнала с `QPlainTextEdit`, цветовую подсветку уровней `DEBUG, PROGRESS, INFO, NOTIFY, WARNING, SUCCESS, ERROR, CRITICAL`, и actions `Refresh`, `Open folder`, `Sandbox diagnostics`. Только когда страница активна, `QTimer` вызывает `refresh_logs` каждые **2 секунды**; при деактивации timer останавливается (`:75-77,150-159,179-187`). `render` не заменяет текст, если tail не изменился; при обновлении сохраняет scroll position, если пользователь не был у конца (`:160-168`).

`src/controllers/gui/logs_page_view_model.py:18-81`: `RefreshLogs` запускает `run_coalesced("logs-tail")`, читает **последние 64 KiB** или меньше; разбивает на строки, выбрасывает первую неполную строку при ненулевом offset, затем оставляет максимум **500 последних строк**. Decode — UTF-8 с `errors="replace"`. Если файла нет, это нормальное empty state, IO exception отображается в тексте с error info. `OpenLogsFolder` создаёт `logs_dir` и вызывает `os.startfile`, Windows-only; failure становится отдельным `LogsShowError` эффектом. `Sandbox diagnostics` переводит на другую страницу без file mutation.

**Техническая граница:** термин *Live stream* в интерфейсе означает **polling file tail**, не системный log subscription. Worker reader обрезает байты до декодирования, поэтому может прочитать середину UTF-8 code point и заменить invalid replacement; это допустимое следствие текущей реализации, но новые требования должны определить приоритет целых строк/encoding и bounded memory. Чтение только `runtime_log_path` не собирает worker logs из `Logs/AIWorkers`: folder link даёт доступ к ним отдельно. Отдельные личные данные/секреты в логах требуют privacy policy при копировании/экспорте, даже если страница read-only.

## Требования

- `REQ-UI-NEWS-001`: change update contour/repository и refresh должны иметь идентичность source generation; исключить stale result / stale focus, при этом сохранить запуск из Home на конкретный release и observable offline state.
- `REQ-UI-NEWS-002`: release derived views `cards/release metadata/full content` доступны без повторного remote запроса для каждого UI consumer, и имеют version/provenance.
- `REQ-UI-LOGS-001`: bounded file-tail view с ясным missing/error/partial-line состоянием; refresh только активного viewer и stable scroll position.
- `REQ-UI-LOGS-002`: локальный log path, отдельные worker logs, OS open folder и Sandbox diagnostics доступны как независимые действия; никакого скрытого remote upload.

## Непроверенные сценарии

Новости: две смены contour во время request, force refresh с сетевым timeout, фокус на release, которого нет в новом repository; foreground/background producer Home. Логи: rotation/truncation во время чтения, non-UTF8, very long single line, исчезновение файла, empty file, OS open folder error; downstream privacy redaction.
