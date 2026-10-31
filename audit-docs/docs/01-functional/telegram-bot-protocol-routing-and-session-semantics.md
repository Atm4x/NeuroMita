# Telegram Voice: бот-протокол, session state, очереди и выбор получателя аудио

**Назначение:** функциональное описание отдельной условной системы Telegram-озвучки. Это не общий TTS API и не требование использовать Telethon в Rust. Действующий путь зарегистрирован в `src/controllers/main_controller.py:169-180,305-343,483-504`, события и host lifecycle — `src/controllers/telegram_controller.py:16-483`, wire client — `src/handlers/telegram_handler.py:61-484`. **Статус:** CONDITIONAL при выбранном TG voice method, действующих credentials и доступной сети.

## CAP-TG-PROTOCOL-001 — авторизация и готовность клиента

`TelegramBotHandler` создаёт `TelegramClient(session_name, api_id, api_hash, device_model, system_version, app_version)`; ввод номера, кода и 2FA разделён между клиентом и `TelegramAuthService` (`telegram_handler.py:61-109,305-425`). В `start`: подключение с ограничением сетевого шага 30s, проверка авторизации, до трёх попыток подтверждения кода, запрос нового кода при истечении, затем 2FA при `SessionPasswordNeededError`. UI-требование — различать `await code`, `wrong code`, `await password`, `authorized`, `connected`, `ready for bot requests` и `cancelled`.

После авторизации отправляет `/start`, публикует connected state. Для `@silero_voice_bot` дополнительно выбирает голос `/speaker mita`, формат `/mp3`, включает HD и отключает video notes через отдельные toggle-команды (`telegram_handler.py:325-343,436-484`). Это **семантика выбранного внешнего бота**, не универсальный Telegram протокол.

## CAP-TG-PROTOCOL-002 — синтез с корреляцией ответа

`send_and_receive(input_message, speaker_command, message_id)` (`telegram_handler.py:166-304`):

1. Проверяет непустой текст, команду голоса и готовый Telegram client. Сохраняет последнюю norm-form команды; отправляет `speaker_command` **только при изменении**, затем текст, соблюдая минимальные паузы и ограничение количества сообщений за минуту (`:112-154,183-199`). Для `@CrazyMitaAIbot` перед текстом добавляет `/voice`.
2. Перед отправкой получает `base_id` последнего сообщения бота; polling запрашивает только `message.id > base_id`, игнорирует собственные исходящие сообщения; принимает MP3 (`audio/mpeg`) либо голосовой OGG (`audio/ogg` с `DocumentAttributeAudio.voice`) (`:185-244`). Это message-ID guard против повторного использования старого voice response, **не** строгая server-side request correlation ID.
3. Срок ожидания вычисляется из `SILERO_TIME` (default 10 s), проверка выполняется примерно три раза в секунду. Пустой/непригодный ответ возвращает None; timeout не равен успешной синтезированной тишине (`:203-244`).
4. Медиа скачивается в `temp`, после чего ожидается стабилизация размера файла до 10 s (`:248-272`). Если Unity подключён, файл конвертируется в WAV, затем публикуются путь `SET_PATCH_TO_SOUND_FILE` и ID `SET_ID_SOUND` в GameLink events (`:274-295`). Без Unity файл направляется локальному `AudioHandler.handle_voice_file` (`:296-299`). Это два отдельных потребителя результата, выбранных состоянием game connection **на момент обработки ответа**.

## CAP-TG-PROTOCOL-003 — управление задачами Core

`TelegramController` подписывается на settings snapshots, изменения, loop-ready и команды start/stop. Автоподключение обусловлено `TG_AUTOCONNECT` и настройками, в headless auth нет интерактивного ввода (`src/controllers/telegram_controller.py:55-235`). `send_voice` ставит работу в очередь и ожидает future; worker выполняет запросы последовательно и должен завершить либо отменить ожидающие futures при shutdown (`:372-483`). Connect/disconnect и очередь генерации — разные состояния; наличие авторизованной session file само по себе не означает активного сетевого клиента.

## Сохраняемые требования, без копирования API

- Пользователь включает Telegram-озвучку как альтернативу другим voice methods; необходимо сохранять auth + bot conversation + voice routing, а не переписывать inference.
- Очередность запросов, ограничение скорости, динамический speaker command и фильтрация чужих/старых ответов — существенная пользовательская семантика; никакие «модели голосов» не загружаются в Rust.
- Результат должен иметь владельца, correlation с turn/message и route Unity/local playback; если сеть недоступна или бот отвечает текстом, статус не подменяется success.
- Перезапуск/изменение настроек/автоконнект без раскрытия session secret, отмена при выходе; не переносить строку `session_name` как целевую архитектуру хранилища.

**Пределы:** по исходникам подтверждено поведение клиента/очереди. Реальный Telegram auth, доступность ботов и формат их ответов в этом проходе не проверялись. Эти проверки требуют live integration, а не unit теста.
