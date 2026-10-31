# Семь зарегистрированных страниц: действия, состояние и функциональная достижимость

**Задача:** единая матрица `registered page → action origin → functional consumer → visible outcome`, чтобы новый Rust Core сохранил сценарии, а не иерархию UI. Источники: `src/ui/pages/main_page_registry.py:12-51`, файлы страниц/презентации и GUI view models. **ACTIVE** здесь означает наличие зарегистрированной страницы; отдельные контуры могут быть `CONDITIONAL` по конфигурации и доступности внешнего ресурса.

## Реестр навигации

| Page key | User-facing scenarios | UI source / action evidence | Функциональный владелец/выход | Условие и остаток |
|---|---|---|---|---|
| `home` | Статус Python app/Unity game, primary launch/update/restart, выбор компонентов для обновления, меню действий, последние релизы/переход к news | `src/ui/pages/home_page.py:215-239,278-315,330-461` | `HomePageViewModel`/`HomePageController` и update catalog, OS/game launch | Reload/news/loading/partial update; launch не эквивалент install. [Home](home-launcher-update-and-game-state.md) |
| `news` | Список релизов, выбор release, открытие деталей и ссылок, refresh, ошибки сети | `src/ui/pages/news_page.py`, `src/controllers/gui/news_page_view_model.py`; [News](news-and-logs-live-ui-contracts.md) | Release manifest/GitHub fallback, cached release state | Remote source conditional; offline empty/error не терять |
| `gallery` | Обновить, открыть папку, сортировать новые/старые, открыть фото в viewer, zoom/fit/prev/next/open original | `src/ui/pages/gallery_page.py:70-115,157-265`, `src/ui/dialogs/gallery_viewer.py:25-190` | Local Unity Gallery scan + thumbnail worker/filesystem watcher, OS open | Доступность Unity directory, photo file, decoder; gallery ≠ кадры текущего LLM. [Gallery](gallery-lifecycle-and-photo-viewer.md) |
| `sandbox` | Активный персонаж, chat/attachments, voice/mic/game/capture toggles, история/DB, context viewer, debug, память, инспектор, clear history | `src/ui/pages/sandbox_page.py:608-2605`, `src/ui/widgets/chat_panel.py`; [Sandbox](sandbox-page-functional-contract.md) | ChatModel requests, SettingsService, GameLink, capture, history/memory and status projections | Game link, ASR, TTS, camera conditional; generation busy/cancel/error independent |
| `settings` | 12 зарегистрированных секций, редактирование пресетов, персонажи, AI Engine, RAG, установки, API, обновления, экспорт | `src/ui/pages/settings/section_registry.py:15-173`, [settings](settings-functional-actions-and-live-effects.md) | Сервис настроек, команды/события, installers/AI worker | Dynamic section visibility + lazy loading; отдельные dialogs/operations |
| `wiki` | Локальные Markdown статьи, категории, поиск/ссылки, навигация back/forward и anchors, app deep links, смена языка | `src/ui/pages/wiki_page.py:350-857`, [Wiki](wiki-navigation-localization-and-anchors.md) | Local docs root, OS URL opener, page action deep-link | Locale fallback/путь+якорь, не удалённый браузер или LLM document parsing |
| `logs` | Live просмотр tail, ручной refresh, открыть папку, перейти к Sandbox debug; ошибки чтения | `src/ui/pages/logs_page.py:68-185`, `src/controllers/gui/logs_page_view_model.py`; [Logs](news-and-logs-live-ui-contracts.md) | Local logger file/worker; OS folder | UI refresh каждые 2 s только на активной странице; это file tail, не подписка на structured trace stream |

## CAP-GUI-PAGE-REACH-001 — границы маршрутизации

1. Реестр `MAIN_PAGE_SPECS` использует семь статических ключей, но грузит factories через `import_module` по запросу (`main_page_registry.py:12-51`). Наличие статического ключа в текущем UI не означает, что heavy page dependencies загружаются при startup.
2. `home`: primary button dispatches `HomePrimaryRequested`, а меню во время операции используется как cancel только при `state.can_cancel`; вне операции открывает extra menu (`home_page.py:219-232,455-461`). Выбор отдельных компонентов `HomeToggleUpdate(name,selected)` хранится отдельно от факта обновления (`:278-293`).
3. `gallery`: viewer открывается по grid click/activate, thumbnail запрашивается отдельно через model (`gallery_page.py:95-114`). Обработка photo selection не производит автоматически LLM request.
4. `logs`: screen timer 2000 ms; при смене активной страницы timer останавливается, а обновление не выполняется (`logs_page.py:75-78,150-185`). Нельзя считать эту страницу real-time Push channel, хотя она называется «Живой поток».
5. `sandbox`: переключение отдельных voice/mic/RAG/game значений меняет настройки, но конечное состояние оборудования и AI worker отображается через status/events; read-only session и настраиваемая секция персонажа — разные источники идентичности.
6. `wiki`: `app:` ссылки могут выполнять переход в другие страницы или настройки; маршрут должен учитывать ограничения документов и целевых deep link keys.

## Одна операция — четыре слоя данных

Для функционального parity отделяются: **Action intent** (нажатие/shortcut), **accepted/queued** (например, Home updater, AI Hub), **result** (изменение persisted/runtime state), **projection** (видимый progress/error/ready). В current Python GUI встречается optimistic setting update, а readiness подтверждается позже; это не основание выбирать одинаковую модель для всех действий.

**Не закрыто:** полный список всех nested widget controls, точное keyboard/locale E2E, повторные открытия всех модальных окон, полное картографирование каждой UI action на unit/integration fixtures. Документ покрывает зарегистрированные страницы и ключевые операции, не объявляет всю GUI область `PRIMARY`.
