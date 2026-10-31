# Внешние HTTP-источники и действия: кто инициирует запрос и как используется результат

**Предмет исследования:** внешние сети, которые действительно достижимы в NeuroMita из основного приложения, в отличие от standalone/test utilities. Это функциональная карта интеграций, **не** выбор HTTP-библиотеки для Rust, не список обязательных Python-пакетов. Базис — локальные исходники `CodeNow.zip`; сетевые обращения не исполнялись.

## CAP-EXT-NET-001 — карта live исходящих операций

| Возможность | Инициатор (пользователь/runtime) | Внешний интерфейс и данные | Куда попадает результат | Код/граница |
|---|---|---|---|---|
| LLM completions | Отправка пользовательского текста, proactive/dialogue task | Provider endpoint; requests, stream/chunks, tool calls | Generation pipeline → Chat/UI + structured effects/voice/game | `src/handlers/llm_providers/`, `src/controllers/model_controller.py`; [протоколы](../03-runtime/provider-wire-contracts.md) |
| Web search (DDG) | Вызов разрешённого LLM tool `web_search` | DuckDuckGo/DDGS search results | Строковый tool result внутри следующего LLM turn, не прямой Unity command | `src/managers/tools/builtin/web_search.py:8-51` |
| Google search | Разрешённый `google_search` tool и credentials | Programmable Search JSON API | LLM tool result | `src/managers/tools/builtin/google_search.py:16-65` |
| Web reader | Разрешённый `web_reader` tool | Переданный URL → `https://r.jina.ai/{url}` (GitHub blob преобразуется в raw URL); 20-second timeout | Очищенный/обрезанный текст либо диагностический текст результата tool | `src/managers/tools/builtin/web_read.py:19-66` |
| Remote TTS | Выбор remote voice profile / синтез ответа персонажа | Remote provider API (в частности Fish Audio), текст и параметры голоса | Аудиофайл, затем voice routing/Unity/local playback | `src/services/remote_voice_service.py:46-340`, `src/handlers/remote_voice/fish_audio.py:22-150` |
| Telegram voice | Telegram как метод озвучки, MTProto login | Авторизация user client, отправка боту, ожидание ответа/аудиофайл | Очередь TTS → media pipeline | `src/handlers/telegram_handler.py`, `src/controllers/telegram_controller.py`, [контракт](telegram-voice.md) |
| Check for updates | Settings/Home/auto-check | GitHub release catalog, release assets | UI status и staging/update transaction | `src/updater.py:512-766,1104-1215,1585-2190` |
| News feed | Открытие News и refresh | GitHub releases; при недоступности — локальная shell-сводка | Карточки новости/чейнджлоги/ссылки, без установки | `src/controllers/gui/news_controller.py:113-141,207-382`, `src/ui/pages/news_page.py:41-68` |
| Prompt pack refresh | Обновление пользовательского набора промптов | `GET api.github.com/repos/<owner>/<repo>/zipball/<branch>`, zip с `Prompts` | Staged replacement prompt assets с восстановлением прежнего каталога при ошибке | `src/utils/prompt_downloader.py:26-81,83-241` |
| Voice asset update | AI Hub voice bundle install/check updates | GitHub Releases manifest/ZIP per character, локальный version stamp | Voice bundle файловый набор | `src/utils/voice_assets_installer.py:56-182`, `src/installables/voice_assets.py:40-137,140-357` |
| AI model download | Установка ASR/TTS/RAG | HF snapshot / direct HTTP model artifacts / pip repositories | Managed Python AI environments + checkpoint files | `src/managers/rag/install_spec.py:326-645`; installable classes in [family matrix](installable-families-runtime-operations.md) |
| Pricing/model discovery | Model settings UI, lookup или background pricing fetch | Provider model endpoint / OpenRouter price metadata | Price/token limits and model options in API preset UI | `src/managers/model_pricing_manager.py:205-320`, `src/controllers/api_presets_controller.py:1662-1763` |

Значимые **входящие** интерфейсы вынесены отдельно: Unity socket/protocol ([transport](../03-runtime/unity-transport.md)), optional local runtime TCP/JSON control plane ([IPC](local-runtime-ipc-external-control-contract.md)). **Не** относить их к тем же HTTP-клиентам и не считать любым HTTP-запросом командой LLM/Unity.

## CAP-EXT-NET-002 — пользовательское поведение vs механизм доставки

**Web reader:** `WebPageReaderTool.run(url,max_chars)` выполняет только HTTP GET к Jina Reader и обрезает текст; собственный HTML-parsing pipeline из импорта `bs4` в этом методе не задействован. Ошибка возвращается как **строка tool result**, а не пробрасывается в UI как отдельное error event (`web_read.py:37-52`). Это важно для семантики продолжения генерации, но не повод копировать тот же транспорт.

**Prompt update:** `PromptDownloader` выбирает GitHub owner/repo из `repo_url`, использует ветку `main` по умолчанию, скачивает ZIP частями, отбирает только директорию `Prompts`, ограничивает download/extracted size/file count, запрещает symlink и выход из staging; затем заменяет каталог через backup + os.replace (`prompt_downloader.py:34-81,83-241`). Новому приложению требуется сохранить функцию обновления prompt-assets и поведения пользователя при отказе/отмене, а не в точности эту Python-архивацию.

**Новости и обновления:** news feed — информационный контент; update workflow — отдельная транзакция с перезапуском и stage-journal. Нельзя использовать успех загрузки release notes как подтверждение успешного обновления приложения. `news_controller.py:113-141,207-382`; `updater.py:1104-1215,1585-2190`.

**Pricing:** данные стоимости могут загружаться асинхронно от провайдера и относятся к отображению/планированию расходов, а не к самому LLM inference. Нужны provenance, currency/units и состояние «стоимость не определена»; отсутствие свежей цены не запрещает генерацию (`model_pricing_manager.py:205-320`).

**Telegram/remote voice:** имеют собственные credentials, сроки жизни сессии и отдельную обработку мультимедиа. Не заменять одной абстракцией «HTTP интеграция»: MTProto, API-provider и локальный AI worker — принципиально разные границы.

## Reachability и функциональные требования

- `REQ-EXT-NET-001`: входящие/исходящие протоколы, их авторизацию и provenance хранить раздельно; наличие библиотеки в dependencies не доказывает активной функции.
- `REQ-EXT-NET-002`: пользовательская инициатива (`search`, `refresh`, `install`, `voice`, `update`) и автоматический trigger (`model discovery`, `startup check`, `retry`) должны быть различимы на уровне capabilities.
- `REQ-EXT-NET-003`: для каждой внешней операции нужны observable state `idle/in_progress/completed/failed/cancel_requested` там, где есть асинхронный пользовательский сценарий; точный UI и локализация отдельно.
- `REQ-EXT-NET-004`: в новом Rust Core управлять network/process/artifact lifecycle без вывода AI inference за пределы Python AI Engine.

## Классификация вне основного Core

`src/web/server.py` и `src/web/vtt/router.py`: самостоятельный FastAPI/uvicorn + Vosk endpoint; регистрация в production launch path **не подтверждена**. `src/connetors/hoi4/*`: standalone prototype; наличие модуля не подтверждает production registration. `src/web/mock_api/*` — тестовая поверхность с opt-in переменной. Подробности в [entrypoint status](external-integration-entrypoints-and-reachability.md). Их нельзя автоматически превращать в обязательные Rust capabilities.

## Открытые вопросы

Данные реальных credentials/provider/HTTP backend не проверялись; live tests Telegram/LLM/voice/update в этом аудите не выполнялись. Для независимого паритета ещё нужны fixtures по auth expiry, retry/cancel, network errors, URL policy, streamed response, rate limits и late-event delivery. Статическое покрытие producer/consumer не равно подтверждённому E2E.
