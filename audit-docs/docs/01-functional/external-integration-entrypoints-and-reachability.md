# Внешние интеграции: реальные runtime-пути и самостоятельные экспериментальные поверхности

**Цель:** не просто перечислить присутствующие в репозитории API, а установить, *из какого действия/настройки* они достижимы в обычной NeuroMita, кто потребляет ответы и какой пользовательский контракт необходимо сохранить при независимой Rust-реализации. **Источник:** локальный `CodeNow.zip` без Git metadata. Никаких сетевых вызовов в проходе не выполнялось.

## CAP-EXT-ROUTE-001 — условный Telegram MTProto user client и голосовой бот

**Статус:** `CONDITIONAL`, production registration подтверждена. `src/controllers/main_controller.py:169-180,305-343,483-504`, `src/controllers/telegram_controller.py`, `src/handlers/telegram_handler.py`; подробные сценарии [Telegram voice](telegram-voice.md), [Telegram auth GUI](../02-ui/telegram-auth-modal-contracts.md).

Composition сначала регистрирует недоступный `TelegramService` и отдельный `TelegramAuthService`; затем optional-feature registry заменяет TelegramService действующим `TelegramController`, если `USE_VOICEOVER` и метод `TG`/`telegram`, с обязательным импортом `telethon`. В GUI mode auth доступен как интерактивная операция с кодом/2FA; при `headless` сервис аутентификации помечается недоступным для ввода кода. `TG_AUTOCONNECT` и credentials влияют на **автоматическое подключение**, но `USE_VOICEOVER/VOICEOVER_METHOD` — граница регистрации возможности. Запрос озвучки → очередь user-client → external bot → аудиофайл; наличие Telethon в dependencies само по себе не означает подключённый аккаунт/готовый бот.

## CAP-EXT-ROUTE-002 — LLM tools как опциональные внешние операции

**Статус:** `CONDITIONAL`, встроенный production tool manager. `src/controllers/model_controller.py:60-68,1480-1508`, `src/managers/tools/tool_manager.py`, [инструменты и веб](tools-and-web.md).

В состав каталога включены `web_search` (DDGS), `google_search` (Custom Search API), `web_reader` (посредством `r.jina.ai`), а также локальные `calculator`, `memory_search`, `reminder`. Первые три по умолчанию выключены, а последние два включены по умолчанию, но **общий tool gate** может отключить весь pipeline. Результаты внешних поисков возвращают контент в LLM continuation, а не напрямую в Unity. Важные функциональные границы: provider credentials/timeout/response format, tool-specific enablement, разрешённая глубина вызова и возвращаемые ошибки. Пакет `bs4` сам по себе не доказывает наличие в действующем web_reader собственного browser/HTML scraper.

## CAP-EXT-ROUTE-003 — удалённая озвучка и LLM API как зависимости, а не отдельные серверы

**Статус:** `ACTIVE/CONDITIONAL` по выбранному голосовому или LLM provider. `src/controllers/main_controller.py:114-125,700-704`, `src/services/remote_voice_service.py`, `src/handlers/remote_voice/`, `src/handlers/llm_providers/`.

`RemoteVoiceService` зарегистрирован как типизированный сервис в composition root; пользовательские пресеты и выбор голоса конкретного персонажа описаны в [remote voice routing](remote-voice-presets-and-character-routing.md). LLM провайдеры — **исходящие HTTP/protocol clients**, с отдельными идентификаторами preset, model и credentials. Их presence нельзя интерпретировать как запуск локального API endpoint. Провайдерный транспорт и авторизация исследованы отдельно в [wire contracts](../03-runtime/provider-wire-contracts.md).

## CAP-EXT-ROUTE-004 — FastAPI VTT, mock OpenAI и HoI4 не являются автоматически основным Core

**Статус:** `STANDALONE/EXPERIMENTAL` или `UNRESOLVED` по подключению к production. `src/web/server.py:1-37`, `src/web/vtt/router.py`, `src/web/mock_api/router.py`, `src/connetors/hoi4/hoi4_connector.py`, `src/connetors/hoi4/hoi4_server.py`.

`web.server` собирает отдельное FastAPI приложение и запускает uvicorn **только** из `__main__`; VTT API принимает WAV и использует Vosk, mock OpenAI router условен по `NEUROMITA_ENABLE_MOCK_API=1`. По `main_controller.py` и обычному launcher path не подтверждено создание uvicorn внутри основного runtime. Поэтому HTTP server, Vosk web model directory и mock scenarios — **не автоматически обязательные** функции первого Rust Core. Однако при решении о поддержке самостоятельного сервера его контракт должен быть описан отдельно, без отождествления с live ASR.

HoI4 connector умеет находить Windows окно `hoi4.exe`, передавать клавиши/консольные команды и взаимодействовать с отдельным mod protocol. Но прямых production imports/registration из `MainController` при выборочной проверке не обнаружено. Факта существования `src/connetors/hoi4` недостаточно, чтобы объявить его обязательной игровой интеграцией первой Rust-версии. Сравнение с [standalone web surface](standalone-web-surface.md) и existing [HOI4 snapshot](hoi4-standalone-prototype.md) — по итоговому evidence, а не по названиям папок.

## Пользовательские состояния и требования

| Вариант | Условие активации | User-visible outcome | Незакрытая проверка |
|---|---|---|---|
| Telegram voice | Voice setting TG + installed Telethon + credentials/session | Auth dialog, connect, queued voice, audio | login, bot responses, timeout, cancel E2E |
| Web search/read | tool gate + per-tool enable + provider internet credentials/availability | LLM tool call/result in current conversation | реальный remote response, no-results/error mapping |
| Remote voice | character voice selection + remote profile/credentials | Speech synthesis output for audio/Unity | provider and device E2E |
| Standalone VTT | отдельный `python -m`/uvicorn entry | HTTP endpoint outside normal GUI | external deployment owner unresolved |
| HoI4 prototype | отдельный запуск/мод, production path не найден | windows automation/protocol as standalone experiment | подтвердить или исключить по продуктовому решению |

- `REQ-EXT-ROUTE-001`: каталог интеграций должен различать production active, optional enabled и standalone/unresolved; присутствующая Python library не равна обязательной новой функции.
- `REQ-EXT-ROUTE-002`: пользовательская авторизация Telegram, tool provider credentials и remote voice profile — **разные** контуры credentials и session readiness.
- `REQ-EXT-ROUTE-003`: входящие результаты сторонних систем должны сохранять provenance (`tool result`, `voice media`, `HTTP API`), correlation и доступный пользователю статус отказа/отмены.

**Пределы:** Это классификация регистраций и контрактов, не тест международной сетевой доступности, действующих ботов, авторизации Google/Jina или исходного HoI4 мода. Не предлагались фиксы старой реализации и не выбирались Rust libraries.
