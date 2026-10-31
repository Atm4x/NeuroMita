# Неявные, опциональные и установочные Python-зависимости: доказательства без прямого импорта

**Назначение:** уточнить границу функции и Python distribution при переходе NeuroMita Core на Rust. Этот документ **не выбирает Rust crates** и не считает package unused из-за отсутствующего `import`. Источник — Python snapshot `CodeNow.zip` и [инвентаризация requirements](full-requirements-runtime-evidence-ledger.md).

## Четыре принципиально разные причины присутствия distribution

1. **Core imports**: приложение непосредственно импортирует API пакета в выполняемом пути. При переписывании сохраняется *функция*, а не совместимость с его Python-интерфейсом.
2. **Runtime feature probe**: зависимость не импортируется синтаксически, а обнаруживается через механизм разрешения модулей. Её отсутствие переключает поведение.
3. **Installer-owned package string**: пакет присутствует в установочном плане изолированного AI backend, даже если главный Core его не импортирует. Оставление Python inference не подразумевает необходимость переноса этого пакета на Rust.
4. **Transitive dependency**: пакет требуется другой distribution. Подтверждение требует lock/distribution metadata фактического окружения; из одного файла `requirements.txt` обратные зависимости надёжно не восстановить.

## Проверенные вторичные зависимости и признаки

| Distribution / группа | Source evidence | Доказанная функция | Граница / доказанность |
|---|---|---|---|
| `h2` | `src/handlers/llm_providers/http_transport.py:94-123,190-203` | `importlib.util.find_spec('h2')` проверяет поддержку HTTP/2 до создания `httpx.Client`; отсутствие означает HTTP/1.1 и предупреждение | **CONFIRMED** runtime feature probe, не прямой import. Функционально нужен протокол HTTP с согласованным fallback, не именно этот пакет |
| `google-api-core` | `src/handlers/voice_models/f5_tts_model.py:300-345` | Указан в `InstallAction(type='pip')` F5-TTS вместе с `f5-tts`, версиями `numpy`, `librosa`, `numba` и лингвистическим пакетом | **CONFIRMED** installer-owned в Python voice backend; не самостоятельная функция Rust Core |
| `pyphen` / `ruaccent` | `src/handlers/voice_models/f5_tts_model.py:320-340` | Выбор зависимости по cross-lingual признаку варианта F5 | **CONFIRMED** опциональный состав Python voice backend |
| `platformdirs`, `requests`, `certifi`, `charset-normalizer`, `idna`, `urllib3`, `cffi`, `pycparser` | `src/game_connections/services/beat_backend_spec.py:50-74` | Явные элементы `BEAT_SHARED_PACKAGES` для Beat backend | **CONFIRMED** installer-owned (не доказательство direct Core import) |
| `rotary-embedding-torch`, `einops`, `tqdm` | `src/game_connections/services/beat_backend_spec.py:81-86` | Дополнительные Python distribution для BeatThis | **CONFIRMED** installer-owned в optional BeatThis backend |
| `ffmpeg.exe`/аудиодекодирование | [component operations](../01-functional/installable-families-runtime-operations.md), [installation plans](../01-functional/installer-component-plans.md) | Управляемая установка внешнего бинарного инструмента и runtime media conversion | Не равняется Python-дистрибутиву `ffmpeg-python`; анализировать separately: wrapper, executable, codec dependency |
| `PyQt6`, `PySide6` в отдельных инструментах | `src/ui/**` и самостоятельный `prompt_editor` | GUI-зависимости могут принадлежать разным entrypoint; не каждая auxiliary UI поверхность входит в основной executable | **CONDITIONAL/UNRESOLVED** по конкретной достижимости, не универсальная обязательная dependency |

## Runtime-ветка HTTP/2 в деталях

`LLMHttpClient` инициализирует `self._http2_available = find_spec('h2') is not None` и устанавливает `http2=self.http2_enabled` для `httpx.Client`; по умолчанию `http1=True`. При явном enable и недоступном модуле выводит warning. Клиент создаётся/выдаётся через `HttpClientRegistry` с меткой сервиса и ограничением соединений; `post_json` различает потоковый ответ (`stream=True`) и немедленное чтение, регистрируя response в cancellation resources (`src/handlers/llm_providers/http_transport.py:94-203`). Для новой реализации это контракт транспортной способности и управления ответом, а не обязательство использовать h2 crate в любой конфигурации.

## Различать установку компонента и владение средой

`scripts/run.py:62-93` явно описывает запрещённые в `Lib/core` inference-distributions (включая `torch`, `onnxruntime*`, `f5-tts`, `fish-speech-lib`, `ctranslate2`, `xformers`, `triton`). Таким образом, инвентаризация `requirements.txt` не может автоматически интерпретироваться как обязательный набор дистрибутивов для Core. Подробности — [текущая граница AI worker](ai-worker-python-core-import-boundaries.md) и [реальная импортная достижимость](python-import-reachability.md).

## Требования к дальнейшему подтверждению

- Для полного перечня package-edges понадобится разрешённое фактическое Python окружение (metadata/wheel lock) и исполняемый feature sweep. Этого в статическом snapshot нет.
- Для каждого `importlib`, lazy-loader, `.so/.dll`, отдельного Python process и `InstallAction(packages=...)` вести независимую строку с владельцем и feature-condition.
- В target Rust Core сохраняются требования «изолировать AI», «устанавливать и восстанавливать его backend», «использовать transport features»; реальный inference stack остаётся Python.
- Нельзя из 52 записей без прямых AST imports заключить, что 52 пакета лишние: среди них есть installer-owned, optional probes и транзитивные зависимости.

**Статус:** статическая source-проверка. Wheel metadata, лицензии и наличие всех Rust альтернатив отдельно не верифицированы.

## Уточнение Pass 13

Предыдущая строка статуса относится к исходному проходу. Сейчас дополнительно проверены [131 local METADATA и reverse parents всех 84 requirements](installed-wheel-metadata-and-native-evidence.md), direct/delay PE imports шести binaries, [common](core-library-alternatives-and-native-costs.md) и [niche Rust paths](core-niche-alternatives-and-parity-gates.md) по первичным источникам. Это не target release/managed environment lock и не runtime loadability.

Ещё один implicit optional consumer: `langdetect` в `utils/__init__.py:9–15,378–416` участвует в выборе языка произносимых числительных, но отсутствует в корневых requirements. Package unavailable → statistical detector None → остальные language/default branches, не обязательный startup failure. [Функциональные gates](../01-functional/language-normalization-rag-morphology-and-speech-numerals.md). Native alternatives существуют; ни один не объявлен готовым corpus-equivalent replacement.

Distribution aliases подтверждены metadata: bs4→beautifulsoup4, dotenv→python-dotenv, python-chess→chess. Нельзя строить complete import/dependency mapping только заменой `-` на `_`. DDGS также несёт primp/lxml, py7zr — отдельные codec/native packages, HTTP2 — hpack/hyperframe; extras api/test/dev не становятся active от одного наличия записи в metadata.

Дополнительный AST review всех 717 production-src modules (без Lib/Testing/not_used) уточнил external import candidates. `character` и `hoi4_connector` в таком root-name scan могут быть локальными bare imports, не PyPI dependencies. FastAPI/Vosk/loguru/pyautogui относятся к ранее описанным standalone web/HOI4; model packages cached_path/hydra/omegaconf/transformers/etc — к Python inference. Candidate list сам не меняет reachability.

**psutil** требует отдельной core-классификации: четыре importing modules включают не только HOI4, но Home launcher, Unity update process guard и compile-cache diagnostics. Корневой requirement отсутствует, локально psutil приходит также через py7zr metadata. Функция, target identity и native alternatives описаны в [process-control дополнении](core-library-alternatives-and-native-costs.md). **mss** — active screen capture helper, **faiss** — optional exact search, **importlib_metadata** — compatibility metadata fallback; они не становятся переносом AI inference на Rust от одного отсутствия в root requirements.
