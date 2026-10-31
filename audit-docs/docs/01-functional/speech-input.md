# Голосовой ввод, устройства и владение репликой

Статус: ACTIVE/CONDITIONAL. Разобраны controller reconciliation, managed ASR start/switch/stop, input gate, segmentation и основной routing. Inference-алгоритмы остаются Python; выбор Rust audio backend пока открыт.

## Возможности и сценарии

Пользователь выбирает микрофон, ASR engine и режим radio/PTT/VAD, включает микрофон, получает текст в desktop input либо Unity. Поддерживаются автоматическая отправка и задержка. Запись/готовность ASR/активное разрешение ввода/распознавание — разные состояния. GUI может показывать capture phase и error без запуска или probe worker.

Каталог ASR engines: google, gigaam, gigaam_onnx, whisper, whisper_onnx. Это зарегистрированные варианты; наличие engine class не означает установленную модель. Нужная установка предлагается через AI Hub, controller сам её не запускает. Отсутствие managed AI engine не включает молча local fallback в remote mode. Local recognition ветвь существует; её production reachability требует отдельной проверки.

## Устройство и сигнал

MicrophoneSelectionService хранит стабильный endpoint uid, index hint, name и optional backend. При uid unavailable и недоступной Windows identity возвращается специальная ошибка; нельзя подменять известное устройство произвольным default. Legacy name/index мигрируются отдельно. В каталоге одна предпочитаемая representation на физический endpoint, с возможностью выбора backend. Приоритет WASAPI → DirectSound → MME; WDM-KS исключается для используемого blocking capture.

Проверяется mono float32. Целевая частота ASR/VAD 16000Hz; если endpoint поддерживает только native mix rate, capture открывается на ней, затем блок преобразуется к ASR rate/frame count. В текущем коде integer downsample усредняет блоки, остальные отношения используют linear interpolation. Не переносить этот DSP-выбор автоматически: требования к качеству ещё надо определить.

PortAudio refresh использует private sounddevice lifecycle API под process-local lock и не выполняется при зарегистрированных активных streams в этом процессе. Отдельные процессы имеют отдельные каталоги. Managed worker повторно разрешает uid/backend перед открытием потока, поэтому GUI index не является единственным источником истины.

## Lifecycle

SpeechController использует desired/applied generations и lifecycle lock. Изменение настроек просит reconcile; после медленной операции controller перечитывает актуальное желаемое состояние. Смена только микрофона сначала пытается switch_input без выгрузки модели; при ошибке выполняется полный stop/start. Start активирует managed environment с validation_method=start_live; readiness означает успешный startup, а не просто создание worker wrapper. Неудачный старт отключает MIC_ACTIVE и сообщает причину.

Shutdown отключает desired state, закрывает settings subscription, останавливает recognition, снимает event subscriptions и отменяет owned tasks с timeout1s. В SpeechRecognition.stop состояние running сбрасывается до remote stop, чтобы штатный status не считался аварией; remote stop ожидается до3s, local future до5s. Успешное завершение native read/transcription этим автоматически не доказано.

## Input gate и сегменты

ASRInputGate хранит mode/enabled/active/session_id/generation/press_generation/target/epoch/revision и lease. Команды требуют строгих bool/int и generation 0..2^63−1. Radio может принадлежать desktop или game; PTT — game. Активная radio capture не передаётся другой сессии. Lease3s требует renew, истечение делает reset и требует release. Переотпускание той же generation допустимо, повторный start — нет. Отключение, смена режима, speech block и cancellation меняют epoch; обычный release сохраняет право выдать уже записанный текст.

Отложенный результат проверяется по epoch/mode/session/permitted. Значит отмена означает запрет публикации устаревшего результата; это не обязательно физическая остановка native ASR. Mode vad допускает автоматическую сегментацию без manual active. Radio использует VAD с pre/tail0.5s; release дописывает tail. PTT набирает удерживаемую реплику, после release tail0.128s; при max duration текущий press исчерпан до следующего нажатия. Минимум speech frames отбрасывает слишком короткие сегменты.

AudioCaptureConfig defaults: chunks512, VAD threshold0.5, silence0.6s, prebuffer0.4s, max30s, min speech0.35s. Реальные настройки передаются payload и могут отличаться. Захват читает блоки через executor, VAD вызывается в capture loop. При background transcription есть один transcriber thread и максимум3 pending segments; далее сегмент отбрасывается с queue_full progress. Без background transcription callback ожидается в capture loop. В finally pending transcription ожидается перед shutdown executor: это потенциально длинный stop, который надо связать с parent timeout/recovery.

## Маршрутизация и эффекты

После распознавания проверяются MIC_ACTIVE, microphone test, capture validity и speaking window. Без capture_context действует exact dedup2s и fuzzy0.92 для длинных строк в1.5s. Captured radio/PTT aggregates используют отдельную tracking semantics.

Игровой owner фиксируется в момент решения о routing: session id берётся из capture context либо GameLink. IGNORE_GAME_REQUESTS + All events оставляет ввод desktop. Игровой SEND_ASR_TEXT содержит id/client/text/final/autosend/delay/engine; final utterance claim хранится в bounded map64. Событие undelivered переводит текст в desktop один раз. В просмотренном Python contract нет end-to-end Unity ACK по utterance_id; факт emit не доказывает принятый игровой ход.

Desktop instant send идёт через GUI.SEND_TEXT_MESSAGE, сохраняя пользовательский pipeline изображений/захвата. При ожидании озвучки текст остаётся в input. Задержанная отправка задаётся INSERT_TEXT_TO_INPUT.autosend_after. Срок/отмена GUI timer ещё не проверены. Speaking window подавляет autosend и, при MIC_MUTE_WHILE_SPEAKING, делает input gate blocked. Локальная речь и Unity speech leases учитываются отдельно; disconnect закрывает leases конкретного клиента. Это suppression, не акустическое echo cancellation.

## Требования к новой системе

Сохранить устойчивую идентификацию устройств, явные состояния readiness и ошибку исчезнувшего endpoint. Отделить физический capture, segmentation policy, Python inference и передачу распознанной реплики владельцу. Ownership/capture identity должны сопровождать результат до финального consumer. Нужны различимые outcomes rejected/cancelled/queue_full/transcription_failed/delivered и определённая политика overload. Release и cancel обязаны иметь разную семантику.

Решение, где именно будет захват — Rust host или Python worker — ещё не принято. Сейчас устройства открывает Python worker. Перенос capture в Rust потребует нового PCM/segment contract; оставление в Python требует самостоятельной упаковки его audio integration. Оба варианта исследовать после полного каталога функций.

## Источники и незакрытое

| Источник | Просмотр |
|---|---|
| src/controllers/speech_controller.py:43 | Constructor; reconcile/start/stop/shutdown; capture state; gate; routing и dedup |
| src/handlers/asr_handler.py:533 | Live payload, managed start, switch, stop; local loop целиком ещё не разобран |
| src/handlers/asr_input_gate.py:13 | Полностью |
| src/handlers/asr_audio_capture.py:199 | Config, segmenter, AudioCaptureService полностью; helpers signal conversion прочитаны |
| src/services/microphone_selection.py:25 | Полностью |
| src/infrastructure/audio/portaudio_catalog.py:21 | Refresh, compatibility, начало catalog; endpoint matching tail ещё не прочитан |
| src/handlers/asr_models/registry.py:8 | Полностью |

Остаются Windows endpoint discovery/migration matching, microphone monitor/test implementation, ASR worker event bridge/recovery, engine-specific installation/settings, GUI command reachability и Unity consumer. Не запускались устройства или модели.

Дополнительный проход worker: `_start_live_internal` запускает capture в отдельном thread/private asyncio loop, background_transcription=true; ready приходит после первого успешного stream.read, startup deadline10s. Перед/после transcribe проверяются capture generation и gate validity. Stream switch сохраняет recognizer/VAD, увеличивает capture generation; stop ждёт capture task до5s, затем cancel wrapper, что само по себе не останавливает to_thread. Worker text/capture/status/error bridge прочитан: running=true восстанавливает состояние core после replay; runtime error обрабатывается отдельным thread, чтобы не блокировать result loop ожиданием его же ответа. Local mode default выключен (`_remote_asr_mode=True`); иных присваиваний в просмотренном rg не найдено.

В error branches worker обнаружен [ISSUE-007](../05-architecture/current-problems.md): undefined mic_index маскирует часть startup failures. Исправления не выполнялись.

Дополнительно полностью прочитаны windows_endpoint_identity.py, portaudio_catalog.py tail, migrations/settings/microphone_endpoint_id.py, services/microphone_monitor.py и GUI MicrophoneMonitorController. Endpoint uid извлекается из PortAudio PaWasapi_GetIMMDevice через COM GetId; borrowed IMMDevice не освобождается вручную, allocated id strings освобождаются CoTaskMemFree. Catalog различает available/partial/unavailable/unsupported, aliases default input исключаются, ambiguous name mapping не угадывается. MME truncated names восстанавливаются только при единственном совпадении. Legacy selection мигрируется только при AVAILABLE identity и неизменившихся preferences.

Microphone test — реальный input→output monitor, не ASR inference: отдельный daemon thread, input native rate, default output rate/channels≤2, bounded FIFO0.12s с interpolation между clocks, RMS meter. SpeechController получает test session active и блокирует routing/ввод. GUI опрашивает state каждые40ms, stop при смене устройства/hide/close; close join≤2s. Buffer overflow оставляет последние samples, underrun заполняется нулями. Устройство с uid повторно разрешается, без uid проверяется неизменность name по index. Это отдельная полезная core-возможность для новой GUI/audio architecture. Обработка исчезновения endpoint в monitor error path требует review: переменная device может стать None до логирования device.index.
