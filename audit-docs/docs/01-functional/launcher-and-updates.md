# Запуск игры, обновления и восстановление установки

**Capabilities:** CAP-LAUNCH-001, CAP-UPDATE-001—004. **Статус:** ACTIVE/CONDITIONAL. Это функционал Python desktop launcher, включая установку внешнего клиента; клиентская Unity implementation здесь не исследуется.

## Главная страница и процессы

Главная умеет проверить доступность обновлений Python/Unity, выбрать один или оба компонента, установить отсутствующую игру, запустить/остановить её, открыть каталог, показать progress/cancel и предложить перезапуск core. Primary button выводится из состояния: operation → starting/stopping → stop running game → pending restart → apply selected → play installed game → unavailable. Это несколько разных user intents за одной кнопкой.

HomePageController запускает найденный executable через QProcess, фиксирует starting/running/stopped/failed/exit code/error. Поиск: известные имена в target root и первом уровне, затем совпадения имени, затем первый exe. Работающий процесс может быть обнаружен через psutil даже после рестарта launcher; marker содержит PID/executable/create_time. Сопоставление учитывает path и время создания, чтобы не принять простой reuse PID за тот же процесс. Poll внешнего процесса раз в секунду.

Stop главной страницы использует terminate и delayed kill при том же process identity. Updater имеет отдельный guard: Windows WM_CLOSE для окон соответствующего executable, ожидание до5 s, kill оставшихся, ожидание до3 s и повторное сканирование; если игра ещё работает, replacement не продолжается. Это разные operations с разной политикой, их названия в UI не доказывают одинакового graceful behavior. Само process running не равно установленному game connection.

## Проверка обновлений и контуры

Сохранённый UPDATE_CONTOUR test/release задаёт Atm4x/NeuroMita либо VinerX/NeuroMita и stable channel. Есть initial inference/migration по distribution settings/старым journals; подробный приоритет всех migration branches ещё не закрыт. Updater entrypoints фактически перечитывают _get_update_target, поэтому переданный channel не является самостоятельным override источника.

Каталог загружается из release manifest, при отказе — GitHub API fallback. Release projections различают launcher/Python revision и Unity asset; новости используют тот же каталог. Check не выполняет install: результаты current/available/check_failed содержат версии, asset metadata и errors. Home автоматический check throttled600 s и зависит от UPDATE_CHECK_ON_STARTUP; manual force обходит throttle.

Test UI запрашивает TESTER_CODE перед выбранным update и сохраняет его в settings; archive decrypt failure даёт waiting_for_credentials с сохранением download для повтора. Это app-specific archive credential, не API key модели. Реальные release lists/credentials во время аудита не читались и не проверялись сетью.

## Download, архивы и результаты

Downloader поддерживает .part resume Range/If-Range с ETag/Last-Modified, до3 попыток, byte progress, cancellation между chunks, проверку ожидаемого размера/SHA256, atomic publication completed archive и metadata. Если publisher digest отсутствует, вычисляется локальный SHA256; он подтверждает дальнейшую неизменность artifact, но не независимую аутентичность издателя. Cache дополнительно сопоставляет source URL/size/hash. Недокачанные bytes сохраняются для повторного обращения; отмена не означает автоматическое продолжение при каждом старте.

Archive dispatcher распознаёт ZIP/7z/RAR по signature/extension; external7z → WinRAR, для ZIP далее PowerShell Expand-Archive → stdlib zipfile, для7z далее py7zr. Encrypted archive требует code, wrong password имеет отдельный outcome. Выполняются проверки member paths для ZIP и доступного py7zr, flatten единственного root. Общую защищённость всех external extractors/форматов этот проход не доказывает. Python zip extraction проверяет cancel между chunks; py7zr.extractall можно прервать логически только до/после вызова, heartbeat не является физической отменой.

UpdateResult явно разделяет component/ok/status/changed/cancelled/restart_required/version/error/archive_sha256/recovered. Это лучше отражает user outcome, чем bool: его __bool__ True только при ok+changed, поэтому отсутствие обновления не означает failure. Home последовательность обновляет Python, затем выбранную Unity при отсутствии cancel; partial success сохраняет требование restart Python даже при отказе второго компонента.

## Python self-update

Предпочитается patch asset, иначе full; при части patch failures fallback full, но password/cancel не вызывает такой fallback. Файлы распаковываются в staging, создаётся manifest с sizes/hashes, проверяется stage; reusable stage привязан к archive SHA256. В работающую установку накладываются изменившиеся файлы. Отсутствующие в archive старые файлы не удаляются. preserve_prompts сохраняет существующие Prompts файлы и разрешает новые. Присутствие локального файла вне архива сохраняет его; специального универсального запрета перезаписи всех Settings/Histories в overlay loop нет — фактический release payload тоже важен.

UPDATE_MODE=full в активном self-hosted installer понижается до overlay: _full_replace существует, но не вызывается этим path. Частично записанные файлы после ошибки overlay не откатываются целиком. Manifest verification проверяет применённые файлы и deferred targets; это не atomic activation всего установленного дерева.

NeuroMita.pyz никогда не подменяется этим overlay: validate ZIP/testzip/__main__, copy to pending, повторная проверка hash/size, marker .update/python/activation.json. После выхода Launcher.exe должен активировать pending artifact. app_restart передаёт current/parent PIDs в --wait-pid, затем exit43; обычный restart через run.py использует42. Если Launcher handoff не удалось запустить, restart возвращает False и pending остаётся. Нативная реализация activation в Launcher.exe в текущем проходе не найдена/не проверена; заявлен контракт Python стороны.

Locked files дают waiting_for_restart, credential failure — waiting_for_credentials, error — failed, cancellation — cancelled. Существуют durable journal/reserve и resume_pending_python_update. Он проверяет waiting_for_activation: pending still exists → restart required; active hash совпал → activated и cleanup; иначе failure. Locked-file recovery требует detached restart marker. Не всякая failed/cancelled операция автоматически возобновляется. В resume apply ветви отдельно требуется review deferred_activation return: caller не использует return _install_full_archive так же, как основной install path; единство этих outcomes пока не доказано.

## Установка и обновление внешней игры

Python формирует DirectoryInstallTransaction с target/stage/backup/journal. Target path проверяется: не root, не core/его parent, не protected exact paths/state, не junction target; существующий непустой каталог должен распознаваться как установка. Transaction проверяет ownership artifacts из journal и reparse points перед destructive operations. Это важная функция installer, не ограничение языка Rust/Python.

Download/extraction выполняются в stage. Перед commit закрывается игра, переносятся Gallery и user_data, создаётся/проверяется install manifest; user_data исключается из manifest. Stage version/executable проверяются. Commit phases: stage_ready → commit_prepared → target_backed_up → activated → completed; прежний target сохраняется как backup до verifier, при failure пробуется rollback. Stage/backup находятся рядом с target для rename на том же volume; locked rename имеет bounded retries и directory-user diagnostics.

Recovery разбирает незавершённые commit phases и либо завершает проверяемый target, либо возвращает backup. Resume читает recorded target, не только текущий UI path, и повторяет safety check. Completed/rolled_back/cancelled/failed Unity states не считаются автоматически pending. Проверка journal ownership и directory replacement не заменяет весь продуктовый crash/power-loss test; fsync/crash guarantees ещё не проверялись экспериментально.

## Требования к новой реализации

Сохранить отдельные функции check/select/download/resume/verify/apply/activate/restart/recover и наблюдаемые component outcomes. Установка ядра, внешней игры, авторского контента и optional AI environments имеют разные жизненные циклы; общий GUI progress не делает их одной транзакцией. Требуются фиксированная identity операции/installation/source, понятный scope сохранения пользовательских файлов, этапы допустимой отмены, partial success и recoverability. Новый Rust core может иметь свой updater/launcher contract с нуля; копирование нынешних overlay/journal classes не требуется.

## Доказательства и пределы

Прочитаны HomePageController целиком, HomePageViewModel dispatch/check/selection/execute/cancel/results/restart/stage по основным диапазонам; updater get info/check install/resume branches, download, overlay/verify/stage, Unity install/recovery; update_activation/app_restart; DirectoryInstallTransaction основные safety/commit/recovery и manifest verify; unity_process_guard/unity_installation; archive dispatch/stdlib ZIP/py7zr. Release selection/revision details, external extractor process implementations, cache cleanup ownership helpers, update settings UI и native launcher/build ещё требуют дочитывания. Никаких updates/downloads/extraction/process termination/restart/build во время аудита не было.
