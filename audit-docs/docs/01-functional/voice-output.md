# Озвучка и доставка аудио

Статус: ACTIVE, отдельные методы CONDITIONAL. Исследован основной маршрут Local/API/TG и локальное воспроизведение. Провайдеры remote voice, Telegram conversation и сами inference-модели ещё не разобраны полностью.

## Сценарий и границы

Готовый ответ можно озвучить локальной Python-моделью, удалённым API либо Telegram-ботом. Вход содержит текст, character_id, voice_profile, необязательные task_uid/message_id/trace_id. Результат синтеза — путь к файлу. Доставка игровому клиенту и проигрывание на desktop — отдельные последующие действия.

`AudioController._on_voiceover_requested` выбирает метод из текущих настроек. Local получает `process_text_to_voice(text)`, API получает исходный текст. Профиль и speaker стараются фиксировать из запроса, а не повторно брать текущего персонажа. Пустой текст немедленно завершает обработку; неготовый LoopService приводит к failure задачи. Неизвестный метод — configuration failure.

LocalVoiceController при отсутствии explicit profile ищет персонажа по id, затем current profile. Выбор модели читается из NM_CURRENT_VOICEOVER, fallback `low`. Installed, initialized и selected — разные состояния. При пустом initialized cache автоматическая инициализация запрещена, если LOCAL_VOICE_INIT_ON_REQUEST=false; пользователь получает MODEL_NOT_INITIALIZED. При разрешённой lazy init asyncio lock исключает одновременную первую загрузку. Перед каждым synthesize повторно активируется environment выбранной модели.

## Состояние и lifecycle

Local inference остаётся в Python: команда tts/synthesize передаёт text, output_file, character profile и model_id, timeout 3600s. Файлы создаются под MitaVoices с UUID. Выбор/активация managed environment и сам inference — два вызова; нельзя считать их одной атомарной операцией только по наличию init lock. При AI service restart controller сбрасывает model/installed/initialized/triton caches и engine reference, обновляет UI.

AudioController устанавливает waiting_answer=true на время запроса и сбрасывает в finally. Это общий bool, а не реестр параллельных запросов. Индикатор «озвучивает» включается после синтеза. Для Local/API task status SUCCESS с voiceover_path публикуется **до** локального playback. Если есть task_uid и GameLinkService.is_connected(), код выбирает игровую доставку через task_update; фактические начало/конец речи ожидаются от Unity speech_state. Это решение о маршруте, не подтверждение проигрывания.

Без игрового маршрута и при VOICEOVER_LOCAL_CHAT=true используется AudioHandler. Он сериализует pygame mixer глобальным threading.Lock, проигрывает файл в asyncio.to_thread и опрашивает busy с частотой 10Hz. API playback errors пробрасываются, Local по умолчанию только логируются. Поэтому status SUCCESS для local voice не доказывает успешный слышимый playback. Общего cancellation handle для конкретной реплики в просмотренном маршруте нет.

Громкость ограничена 0..200%. До 100% применяется mixer gain; выше 100% WAV переписывается через numpy/soundfile с clipping. Если усиление невозможно, остаётся ограничение mixer до 100%. Временная усиленная копия удаляется в finally. mixer.quit() расположен в штатной ветви, а не в finally: освобождение устройства при исключении требует проверки.

## Файлы и ошибки

Для Local desktop штатный AudioHandler удаляет файл после playback, если разрешено; по умолчанию удаление принудительно включено, отдельный checkbox учитывается только при ENABLE_VOICE_DELETE_CHECKBOX=1. При ошибке playback удаление может не выполниться. API удаляет полученный файл в controller finally, если он не передан в игру. Кто удаляет игровой файл после получения/проигрывания — вопрос Unity-протокола. Отключённый desktop playback может оставить Local output на диске.

Команда delete_all_sound_files ищет `*.wav`/`*.mp3` в cwd, без рекурсии; это не очистка всех MitaVoices и не гарантированный сборщик артефактов.

TG-ветвь здесь вызывает TelegramService.send_voice и публикует task SUCCESS с возвращённым путём; AudioHandler здесь не вызывается. Нельзя выводить полную TG-семантику по AudioController: продолжение доставки находится в Telegram subsystem.

## Требования к проектированию с нуля

Разделить как минимум результаты «синтез готов», «доставка принята», «проигрывание началось/завершилось/ошиблось». Для файлов нужен явный владелец и срок жизни, включая ошибку и отключение получателя. Персонаж, модель, язык и назначение должны фиксироваться в идентифицируемом запросе. Параллельность требует отдельных operation ids, а не общего waiting bool/одного UI indicator. Политику отмены synthesis и playback определить отдельно.

Это выводы о поведении, а не предложение воспроизвести контроллеры или pygame API на Rust. Выбор Rust audio backend и transport для Python требует последующего dependency research.

## Доказательства и пробелы

| Источник | Что прочитано |
|---|---|
| src/controllers/audio_controller.py:25 | Полностью: методы, dispatch, task status, delivery, cleanup |
| src/handlers/audio_handler.py:12 | Полностью: serialized playback, gain, exceptions |
| src/controllers/local_voice_controller.py:87 | Managed activation, engine call, public API |
| src/controllers/local_voice_controller.py:404 | Restart invalidation, synthesize, output path, lazy init |

Не закрыты: remote provider implementations, Telegram delivery, local model-specific profiles/language/options, повторная озвучка из GUI, stop/interrupt UI, фактический Unity ack и cleanup. Реальное аудио не запускалось.

## Дополнительный проход: remote voice

DefaultRemoteVoiceService, RemoteVoiceRepository, core remote_voice types и FishAudioProvider прочитаны полностью. В локальном catalog один provider fish_audio; это факт версии репозитория, не проверка актуальности внешнего API. Presets имеют свой id/name/model/key/default voice/speed и per-character overrides. Active preset обязателен, последний удалить нельзя. Поля нормализуются до сохранения; configured означает заполненную допустимую конфигурацию, verified — успешный synthesis именно для resolved preset в текущем процессе. Изменение конфигурации инвалидирует несовпадающие verified entries; перезапуск не сохраняет verified.

Settings/remote_voice.json поддерживает версии1/2/3, пишет version3 через temporary file + flush/fsync + os.replace; ошибки чтения/записи типизированы и доходят до caller. API key исключён из repr, но сохраняется в JSON как поле asdict; это не credential vault. Пользовательские файлы/ключи при аудите не читались.

Provider нормализует voice id либо HTTPS fish.audio URL, speed0.5..2.0 finite и printable ASCII key. Запрос POST JSON с text/reference_id/format=pcm/sample_rate44100/prosody и Authorization/model headers; redirects=false. Результат целиком собирается в WAV mono16bit, потоковые chunks только ограничивают download, audible streaming в этой ветви отсутствует. Лимиты100MiB и180s проверяются на chunk boundaries; сетевой timeout45/connect15. Проверяется HTTP status, текст вместо audio, пустое/нечётное PCM. Статус оплаты определяется по HTTP402 либо ограниченному error body. Не делается явный retry/fallback в service/provider.

Async cancellation ставит threading.Event, shield сохраняет thread task до завершения; late file удаляется callback. Provider проверяет cancellation до, во время chunk loop и после скачивания, удаляет частичный файл на BaseException. close отмечает pending requests cancelled и закрывает managed HTTP client. Это более явный lifecycle, чем local playback, но не гарантированная мгновенная остановка remote synthesis/оплаты. В новой системе нужно сохранить typed configuration/network/audio outcomes и ownership download artifacts.

Remote GUI editing/testing ещё не исследован. Уточнение предыдущего списка пробелов: provider implementation теперь разобран; внешний API не проверялся и запросы к нему не выполнялись.
