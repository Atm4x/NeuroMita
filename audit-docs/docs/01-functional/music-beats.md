# Анализ музыкальных битов и кеш Beat Sync

**Capability:** CAP-BEAT-001—004. **Статус:** CONDITIONAL. Исследуется функционал Python: получение beat timeline, кеширование, подготовка backend и управление из GUI. Движение головы/анимации игрового клиента отложены.

## Сценарии и доступность

1. Игра запрашивает get_music_beats с локальным audio_path, track_name, request_id, stream, chunk_seconds, min_confidence. Action зарегистрирован в game_connections.handlers.__init__. BEAT_SYNC_ENABLED выключен — явная ошибка; пустой path — ошибка. При принятии отправляется music_beats_job_started.
2. Core сначала ищет кеш по содержимому файла. При miss запрашивает Python worker service=beats и сохраняет результат. Ответ содержит времена/условную confidence, duration, sample rate, method и оценку BPM.
3. GUI позволяет выбрать auto / установленный Beat This / установленный Librosa / DSP fallback, увидеть status/cache size, открыть AI Hub и каталог кеша, построить недостающие entries рекурсивно для каталога музыки.
4. Включение BEAT_SYNC_ENABLED планирует warmup. Установка, инициализация или удаление beat components сбрасывают proxy readiness и обновляют UI.

В settings projection Python принудительно сообщает BEAT_SYNC_USE_FILE_TRANSFER=True и BEAT_SYNC_AUTO_INSTALL=False. Обработка запроса не устанавливает пакеты автоматически. Наличие параметра auto_install в сигнатуре не означает установку во время анализа.

## Результаты, streaming и вычисление

BeatService.extract_beats_streaming сначала дожидается полного extract_beats, затем выдаёт ровно один chunk с progress=1 и chunks_total=1. chunk_seconds в этой реализации не делит аудио на участки. Action отправляет music_beats_chunk, затем music_beats_ready с summary, без повторного массива beats. В non-stream ready содержит весь массив. Ошибка выдаёт music_beats_error с request identity; partial streaming computation здесь нет.

Backend preference задаёт порядок попыток: auto/Beat This → Beat This, Librosa, DSP; Librosa → Librosa, DSP; DSP → только DSP. Инициализация strict не равна запрету fallback: в backend loop DSP всё равно может вернуть success. Worker readiness/status содержит установленные и загруженные компоненты, но active_backend проецируется из availability resolution, а не обязательно из фактического method последнего результата. Поэтому method результата — отдельное существенное поле.

Beat This использует File2Beats(checkpoint final0, CPU либо CUDA), downbeats отбрасываются, confidence выставляется1.0. Librosa загружает mono22050, beat_track даёт timestamps, confidence фиксирована0.9. DSP читает audio через soundfile, усредняет каналы, ресемплирует soxr либо линейной интерполяцией; собственный FFT/spectral-flux peak detector выдаёт относительную нормированную confidence. Одинаковое имя confidence не означает одинаковую калибровку этих методов. BPM оценивается по median intervals и приводится к диапазону70—190; для Librosa может использоваться возвращённый tempo.

Весь анализ каждого backend происходит в Python worker через asyncio.to_thread; local inference остаётся вне нового core по исходному решению пользователя. DSP/Librosa являются audio analysis, не нейросетевой зависимостью core, хотя сейчас размещены рядом с inference. Их размещение в новой системе — отдельный выбор, функционально требуется результат анализа, а не перенос NumPy в Rust.

## Кеш и пакетная подготовка

Каталог вычисляется от src project root: beat_sync_cache. Ключ — SHA256 всего файла. JSON содержит version2, source_hash/path/name, created_at, beats/duration/sr/method/bpm. Lookup проверяет только source_hash; записанная version не проверяется. Backend/model revision и min_confidence не входят в ключ и не валидируются при hit. Следовательно ранее рассчитанный timeline может вернуться после смены backend/threshold без перерасчёта.

Save делает tmp+replace, при PermissionError пишет target напрямую; errors cache save логируются и не отменяют успешный analysis result. Одинаковый hash использует одно tmp filename; синхронизация concurrent cache producers не найдена. Файл повторно хешируется при save, отдельно от lookup и анализа; привязка bytes/revision к одной immutable input snapshot отсутствует.

«Переиндексировать кеш» в GUI вызывает build_cache_for_directory: сортированный recursive обход wav/mp3/ogg/flac/aac/m4a/opus/wma, существующий hit пропускается, остальные анализируются последовательно. Это build missing entries, не принудительная замена всех прежних результатов. Отчёт scanned/cache_hits/generated/failed показывается после завершения. UI run_exclusive предотвращает повтор этого UI job; общего cancellation token/per-file progress в прочитанном build loop нет. Поддержка расширения в списке не доказывает поддержку кодека каждым выбранным backend.

## Требования к новой реализации

- Отдельные contracts: анализ файла, timeline artifact, кеш, каталог batch jobs, readiness и GUI. Внешний игровой клиент только потребляет timeline.
- Явно различать progressive computation и передачу готового timeline частями; новые API не обязаны сохранять текущее имя streaming.
- Cache identity должна отражать bytes, algorithm/model version и влияющие настройки либо хранить результат до threshold filtering. Нужны явные rebuild/invalidate semantics.
- Method, качество/fallback reason и отсутствие beats — самостоятельные результаты. Installed/loaded/usable и method выбранного трека не взаимозаменяемы.
- Bounded jobs, отмена и resource budget нужны для batch и длинных файлов. Сейчас extraction ждёт worker до3600 s; локальное прекращение ожидания не доказывает остановку native/model computation.

## Доказательства и пределы

Прочитаны GetMusicBeatsAction, BeatService целиком, beat_worker_client, BeatsService worker целиком, beat_backend_spec по choices/status/packages, BeatSettingsController/ViewModel/presentation, GUI game_settings section, ServerController warmup и forced projection. Beat install plan начало прочитано; оставшиеся component-specific install/uninstall/validation paths учитываются в installer-проходе. Реального audio analysis, cache build, установки/загрузки model weights и Unity animation тестов не было. Никакие пользовательские аудиофайлы не открывались.
