# Наблюдение YouTube на игровом телевизоре: отдельный источник контекста

**Статус:** CONDITIONAL/ACTIVE when Unity provides observation. **CAP-TV-001—003.** Отвечает на вопрос, *что именно должен понимать персонаж*, когда смотрит телевизор вместе с игроком, и почему этот вход нельзя считать очередным сообщением игрока или фотографией.

## Реальный пользовательский сценарий

Игрок включает ролик YouTube на телевизоре внутри игрового мира. Unity может послать в Core наблюдение с названием, автором, URL, текущим временем видео, фрагментом субтитров и серией кадров экрана. Модель персонажа должна отличать происходящее *на экране телевизора* от действительных событий игрового мира и от слов самого игрока. При сохранении истории и отображении в Sandbox к кадрам/сообщению привязываются source metadata.

## Объект наблюдения

`src/core/tv_observation.py:7-45` принимает только dict с `source == "youtube"`; другие источники не превращаются в TV observation. `normalize_tv_observation()` ограничивает `title≤500`, `author≤300`, `url≤2000`, `subtitles≤4096` символов; время видео — в `0..864000` секунд, интервал кадров — `0..1800`, кадров не более **8**. Числовые NaN/inf/ошибочные значения приводятся к нулю. До 8 отдельных `frame_times_seconds` фильтруются по finite/non-negative и ограничиваются 864000; `frame_order = "oldest_first"` фиксирован.

`format_tv_observation()` производит отдельный текстовый блок `[TV observation]...[/TV observation]`, где прямо указано: это не личные переживания Миты, не фото пользователя, а телевизионный контент; слова игрока следует отличать от реплик ролика. В него включаются известные playback timestamps и субтитры. Никакого HTTP fetching YouTube и декодирования ролика этот formatter не делает: producer кадров находится на другой стороне, источник контекста передаётся как данные.

## Роль события, содержание и видимость

`tv_observation_part()` создаёт `{"type":"text", "text":formatted,... "tv_observation":normalized}` для мультимодального отображения. `is_tv_observation_event()` распознаёт *чистое TV observation* отдельно от реплики: если весь читаемый текст равен TV контексту, это observation, а если игрок добавил свои слова — это обычная реплика с TV metadata.

`src/managers/conversation_event_writer.py:221-271` не требует наличия человеческого текста, если есть TV observation; сохраняет для него normalized metadata и текстовый контекст, а `src/managers/history_ui_projector.py:71-110` возвращает TV часть в UI, не смешивая её с голосом персонажа. `src/ui/chat/message_renderer.py:428-623` собирает TV кадры и metadata в `ImageSeriesWidget`, в т.ч. при нескольких кадрах; `src/ui/chat/image_series_widget.py` рисует последовательность и TV атрибуты. При входящем запросе `src/game_connections/handlers/actions/create_task.py:171-175,378-384` передаёт TV сведения в generation context, но удаляет транзитное TV observation из persistent fallback game state, чтобы последующие запросы не считали старый кадр текущим.

При сжатии/восстановлении истории `src/controllers/history_controller.py:1795-1818` следит за повторением TV контекста и его статусом наблюдения. Следовательно, user text, subtitle transcription, timed screen frames и TV observation должны иметь отдельную provenance и разные правила отображения/попадания в prompt.

## Граничные сценарии паритета

- TV наблюдение **без** пользовательского текста и **без** изображений: сохраняется как событие; нельзя отбросить как пустое сообщение.
- Текст игрока **вместе с** TV observation: сохранить текст как авторскую реплику, TV отдельно; `is_tv_observation_event` не должен подавлять пользователя.
- Серия кадров до 8: соблюдать порядок oldest_first и соответствие playback timestamps кадрам, не интерпретировать кадры как снимки камеры персонажа.
- Субтитры: это слова с YouTube; не вкладывать их в речь игрока или игровые события.
- После потери нового TV context: fallback game state не должен повторно объявить прошлый фрагмент ролика текущим.
- Неизвестный `source` и нечисловые/NaN/inf времена: безопасная нормализация, отсутствие ложной provenance.

## Источники и пределы

`src/core/tv_observation.py:7-78`; `src/game_connections/handlers/actions/create_task.py:171-175,378-384`; `src/managers/conversation_event_writer.py:221-271`; `src/managers/history_ui_projector.py:71-110`; `src/controllers/history_controller.py:1795-1818`; `src/ui/chat/message_renderer.py:428-623`; `src/ui/chat/image_series_widget.py`. Дополнительные source fixtures: `src/utils/Testing/test_tv_observation.py`, `src/utils/Testing/test_reaction_batch_prompt.py`. Тесты не запускались. Детали действующего Unity YouTube screen producer/frame capture, streaming frame batching и декодирования оставлены для отдельного Unity-side аудита. Сравнение GUI-фреймворков и дизайн нового Rust storage не выполнялись.
