# Telegram voice и авторизация

Статус: CONDITIONAL ACTIVE. Это пользовательский Telegram client через Telethon, взаимодействующий с voice bot; не Telegram Bot API server. Аудит кода не выполнял логин, отправку сообщений или сетевые запросы.

## Вход, сценарий, состояние

Настройки задают api_id/api_hash/phone, bot, TG_AUTOCONNECT, метод озвучки, интервалы и SILERO_TIME. Credentials gate проверяет только непустые строки. Автоконнект разрешён при USE_VOICEOVER=true, VOICEOVER_METHOD=TG и TG_AUTOCONNECT; cooldown20s ограничивает повтор. Ручной force пропускает cooldown и условия метода, но не отсутствие credentials. При неготовом LoopService старт откладывается до LOOP_READY.

TelegramController хранит connecting/connected/bot_handler_ready, queue и её worker, текущие настройки. Handler создаёт TelegramClient с SQLite session name `session_name` относительно рабочего каталога; persistent session является отдельным credential artifact. Ошибка constructor логируется, дальнейший start отклоняет отсутствие client. Переключение credential fields обновляет controller, но уже существующий handler не пересоздаётся этим автоматически. Bot name меняется в живом handler.

## Авторизация

Handler connect ограничен30s. Если session не авторизована, запрашивается login code, до3 попыток sign_in. Неверный/пустой код повторяется; expired code запрашивается заново; SessionPasswordNeeded переключает на 2FA password с тремя попытками. Ошибки start пробрасываются controller, чтобы connected=false не был перезаписан ложным успехом.

DefaultTelegramAuthService владеет Futures по UUID; GUI получает request_id/kind/error/attempt, не сам Future. Resolve/reject идёт thread-safe в originating asyncio loop. Timeout default180s, минимум5; close отвергает pending. В headless запрос интерактивного code/password явно запрещён. Существующая авторизованная session может пройти без prompt; весь headless Telegram сценарий ещё не проверялся runtime.

После авторизации handler отправляет /start. Для silero bot дополнительно /speaker mita, /mp3, /hd и /videonotes с проверкой русских response strings. Эти команды меняют настройки внешнего чата. Код знает также CrazyMitaAIbot с /voice prefix и отдельным speaker command. Точная актуальная внешняя семантика ботов ещё не проверялась.

## Очередь и получение audio

Controller использует asyncio.Queue без maxsize, один worker. `send_voice` создаёт concurrent Future и enqueue в owner loop. TG_MIN_REQUEST_INTERVAL ограничивает запросы controller. Handler отдельно считает максимум20 исходящих messages/minute, выдерживает gap1.5s и jitter при ожидании окна; speaker command также расходует budget. Повтор одинакового normalized speaker command подавляется.

Перед текстом сохраняется последний chat message id. После отправки handler polling3Hz до SILERO_TIME ищет среди5 новых входящих сообщений MP3 либо voice OGG; собственные сообщения пропускает. Reply correlation основана на временном chat watermark и serialized requests, явного request id с ботом нет. Timeout возвращает None. Сетевые errors polling проглатываются. SILERO_TIME не является общей deadline всей операции: rate wait, send, download, conversion и playback добавляются отдельно.

Полученное media скачивается в cwd/temp; затем размер файла ожидается стабильным до10s. При connected game handler конвертирует FFmpeg в WAV44.1k stereo PCM16 и публикует старые SET_PATCH_TO_SOUND_FILE/SET_ID_SOUND events, возвращает WAV path. В production src подписчиков этих events rg не обнаружил. Реальная task-based delivery получает path через AudioController SUCCESS. Для запроса desktop без task_uid при подключённой игре здесь нет аналогичного Local/API fallback playback — это отдельный gap.

Без game handler сам проигрывает файл через AudioHandler и обычно удаляет его **до** возврата path controller. Поэтому path в task result может уже не существовать, а индикатор AudioController включается после playback. VOICEOVER_LOCAL_CHAT в этом handler не проверяется. AudioController TG branch не открывает MITA_SPEAKING_WINDOW вокруг handler playback, в отличие от Local/API: ASR suppression требует отдельной проверки общего контракта.

## Ошибки и завершение

Shutdown отменяет queue worker, отклоняет ещё не взятые queued Futures и disconnect клиента. Отмена текущей coroutine не обрабатывается как обычная Exception внутри `_async_send_and_receive`; completion Future уже извлечённого запроса может остаться unresolved. stop_silero только disconnect/reset и не завершает очередь. Параллельный start/stop не имеет desired-generation reconciliation, в отличие от SpeechController; позднее завершение start после stop — риск для дальнейшей проверки.

AudioConverter возвращает bool при timeout/FFmpeg failure; handler этот bool игнорирует, удаляет source и возвращает output path. AudioController принимает None от TG timeout как SUCCESS voiceover_path=None. Эти error outcome mismatches внесены в реестр дефектов.

## Проектирование с нуля

Сохранить пользовательскую авторизацию/session, prompts с lifecycle, selected voice/bot options, serialized bot conversation и rate policies. Для новой реализации отдельно определить отмену queued/inflight requests, correlation старого/позднего audio, readiness session и bot setup. Синтез через Telegram должен возвращать одинаковый с другими voice backends outcome и file ownership; consumer выбирает доставку/воспроизведение. Это требования поведения, не требование сохранять Telethon-классы.

Telethon — важный кандидат для dependency research core, потому что здесь используется полноценный MTProto user client. Пока не утверждается отсутствие Rust-аналогов; сравнить login/2FA/session/media/history/rate/error capabilities по первичным источникам.

## Источники

Полностью прочитаны src/controllers/telegram_controller.py, src/handlers/telegram_handler.py, src/services/telegram_auth_service.py, src/core/telegram_credentials.py, src/services/telegram_service.py, src/controllers/gui/telegram_auth_view_model.py, src/utils/audio_converter.py. Auth dialogs/widgets пока не разобраны. Дополнительно прочитан process_text_to_voice: markup removal, script/statistical language detection, integer→words fallback, alphabet/punctuation filtering; языковой parity требует отдельного исследования.
