# Shared images, audio artifacts и синхронизация настроек

Статус: ACTIVE/CONDITIONAL; исследован transport контракт, генераторы camera/TV/easel и все consumers ещё не закрыты. [Сессия/transport](unity-transport.md).

## Изображения

Python объявляет shared_files_v1/root/images_dir/manifests_dir через loaded_settings. Default root NEUROMITA_BASE_DIR/GameTransfer либо cwd/GameTransfer, env NEUROMITA_SHARED_TRANSFER_DIR переопределяет. Unity использует shared transfer, только если contract заполнен и protocol подходит. IMAGE_TRANSPORT_MODE=shared_files/socket принуждает маршрут, auto использует сохранённый Unity PlayerPrefs toggle. При неготовом contract остаётся socket/base64.

Unity TryCreateManifest пишет encoded bytes в Images/unity/{timestamp_request}, manifest JSON в Manifests/unity. References относительные root, filename token очищен, manifest содержит images и delete_after_read=true. Файлы записываются синхронно перед передачей manifest reference. Failure очищает уже записанные image files; orphan directories/partial manifest требуют cleanup policy. В entrypoint не обнаружен общий byte/frame count cap.

Python collect_context_images объединяет base64 list, прямые file refs и manifest refs. Разрешает несколько совместимых имён полей. File reference resolve ограничен resolved shared root; client id создаёт подкаталог, **но общий root тоже разрешён**, поэтому это не изоляция чтения между clients. Relative search начинает с manifest parent/client roots, затем Images/Manifests/root. Разрешены также file:// refs, если resolved path попадает в root.

Base64 декодируется без strict validate; decoded bytes не проверяются как изображение здесь. Files read_bytes без отдельного byte/count limit, manifest json.load без file size cap; TCP frame8MiB не ограничивает размер shared artifacts. Ошибочные/missing paths логируются и пропускаются, request может продолжиться с частичным/пустым image set. Dedupe refs/bytes здесь нет.

delete_after_read задаётся context, затем manifest, defaulttrue; per-image flag Unity producer не читается отдельно. После успешного чтения images и manifest удаляются, пустые parent dirs удаляются до root. Manifest может попасть в cleanup даже при parse failure. Ownership передаётся core в виде bytes до generation; это не подтверждение принятия LLM. Blocked request может вообще не вызвать collect, leaving artifacts. Crash/disconnect до read тоже оставляет files; TTL/orphan collector ещё не найден.

## Audio ownership

В отличие от image refs, voiceover_path передаётся как готовый абсолютный local path. Unity LoadAudioClipFromFileAsync читает/decode→AudioClip→best-effort File.Delete. Текстовое delivery outcome, audio file load и audible playback независимы. Поздний повтор сохранённого result может ссылаться на уже удалённый WAV; retry должен учитывать regenerating audio либо durable media reference. Единый path lifetime contract отсутствует в просмотренных producers/consumers.

## Settings projection

ServerController sends selected settings + stats всех CharacterRegistry ids + settings_revision. Это **проекция**, не точная копия SettingsManager: GM_ON всегдаfalse, BEAT_SYNC_USE_FILE_TRANSFER alwaystrue, BEAT_SYNC_AUTO_INSTALL alwaysfalse. Остальные defaults/normalization зависят от ключа; ASR mode и image transport нормализуются. Смена watched setting broadcasts полный body; первоначальное connection и get_settings тоже отправляют body. Revision присутствует, monotonic application проверить в DialogueRuntimeSettings/MitaCore отдельно.

Unity SettingsUpdateHandler background parses body/settings, older values/mod_config forms поддерживаются. Stats переносятся в actor.State с persist=true либо SaveService для ещё не созданного actor; это durable effect на стороне Unity. Затем MitaCore.ApplyServerSettings либо fallback DialogueRuntimeSettings/SharedImageTransfer. Session reset очищает local stats cache. Concurrent asynchronous handlers без увиденного revision guard здесь могут применить snapshots в другом порядке; downstream guard ещё не проверен, поэтому это пока вопрос, не установленный дефект.

Дополнительная проверка downstream: MitaCore→DialogueRuntimeSettings→ServerSettings.ApplyFromDictionary guard старых revisions не содержит, AppliedSettingsRevision просто присваивается nonnegative incoming value. Stats применяются раньше этого шага. Поэтому защита от out-of-order application отсутствует во всём просмотренном пути; реальное возникновение перестановки не воспроизводилось. Auto transport в MitaCore также переустанавливает Unity PlayerPrefs toggle из MitaCameraUseFileTransfer.

## Новые требования

Определить typed media descriptors с byte limits/count/hash/format/owner/expiry, отдельно от filesystem path и режима транспорта. Согласовать retry с delete-after-read и crash recovery. Удерживать request snapshot до commit без утечки consumable events. Settings projection должна иметь явную policy, source revision и правила принятия stale updates. Допускаются совершенно новые transports/хранилища; текущие directory layouts не являются требованием переноса.

## Источники/остаток

Полностью прочитан Python shared_image_transfer.py, ServerController settings projection; Unity SharedImageTransfer основные config/write/reference/cleanup helpers, SettingsUpdateHandler до extraction stats (часть conversion helpers ещё не прочитана), NetworkController mode/path consumer. Producers FrameRecorder/TV/easel, decoder format limits, orphan cleanup и настройки consumer полностью ещё не исследованы. Файлы пользовательских изображений/аудио не открывались.
