# Дистрибутив Python NeuroMita: сборка, bootstrap, активация и ограничения

**Scope:** рабочий контракт доставки продукта и защиты данных. Это не проектирование Rust packaging. Источники — исходники `CodeNow.zip` (локальный Git отсутствует; ревизия `38172493fa0d1caf1a5225bc1c559f095f18bb7a` ранее заявлена, но не повторно проверена). **Статус:** ACTIVE для штатных release scripts, CONDITIONAL для опциональных сборочных режимов. Сборка и запуск на Windows не проводились.

## CAP-DIST-001 — исходный release bundle

**Source:** `build.py:34-102, 105-142, 144-200, 204-240, 277-321, 390-502`; `build.env.example`.

Сборка выбирается через `BUILD_MODE` (`full`/`fast`) и `BUILD_*`; окружение переопределяет `build.env`. В обоих режимах `build.py` собирает `src` в **`NeuroMita.pyz`** ZIP_STORED, исключая определённые папки и расширения (фильтр `bin_filter`), проверяет наличие базовых Qt SVG resources, копирует `requirements.txt`, launcher assets/wiki, и скрипты `Launcher.exe`, `run.bat`, `run.py`. Full/fast отличаются наборами extra Prompts и дополнительных файлов. Условно собирает native launcher из `scripts/launcher.c` + `launcher.rc` через VS C toolchain (по умолчанию включено), либо переиспользует имеющийся EXE.

`write_distribution_metadata` пишет `Settings/distribution.json` с `schema=1`, `contour=test|release`, определяемым `BUILD_IS_TEST` (`build.py:229-240`). `BUILD_ARCHIVE` создаёт **flat ZIP**, чтобы распаковка заменяла файлы в корне установленного приложения, не добавляя обёрточную директорию (`:390-406, :491-500`). `CLEAN_OUTPUT` по умолчанию удаляет результат предыдущих сборок; защитные проверки запрещают чистить project root/корень диска; `BUILD_PRESERVE_HISTORIES`, `BUILD_PRESERVE_SETTINGS`, `BUILD_PRESERVE_FINETUNE_DATA` позволяют сохранить пользовательские директории внутри output (`:191-226`). Эти флаги — контракты процесса сборки, не обязательные устройства будущего Rust build.

`EXCLUDE_MANAGED_BACKENDS` по умолчанию исключает в копируемых директориях следы torch/NVIDIA/Triton/backend metadata из developer environment (`:166-184, :277-305`). Это предотвращает ошибочную трактовку случайно упакованных GPU пакетов как установленных на машине пользователя.

**Важно:** в данном дереве не доказан полный supply-chain build, который создаёт `libs/python/python.exe`; `build.py` не следует ошибочно считать механизмом инсталляции самого embedded Python. Конкретные `BUILD_COPY_*` зависят от внешнего `build.env` и окружения. Никакие native rebuild или ZIP release generation не исполнялись.

## CAP-DIST-002 — Windows launcher и старт

**Source:** `scripts/launcher.c:32-276`, `scripts/run.bat:1-17`, `scripts/run.py:816-864`, `launch.py:1-75`.

`Launcher.exe` — небольшой Windows C executable, не основное приложение. Он:

1. Принимает исключительно `--wait-pid N` (до 8), открывает handles процессов и дожидается их завершения **до** активации ожидающего Python update (`scripts/launcher.c:127-225`); открытие handles заранее уменьшает риск PID reuse.
2. При наличии `.update/python/pending/NeuroMita.pyz` делает `MoveFileExW(... MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)` в активный `NeuroMita.pyz`, удаляет marker/пустые staging dirs при успехе (`:72-125`). Ошибка оставляет прежний zipapp активным, pending update — нетронутым.
3. Делегирует `cmd.exe /D /S /C call run.bat`, создаёт отдельную консоль Windows и **сразу выходит**, чтобы `Launcher.exe` не оставался занят в течение работы игры (`:231-276`).

`run.bat` проверяет `libs/python/python.exe`, запускает `run.py`; `run.py` проверяет наличие `NeuroMita.pyz`, `requirements.txt`, загружает/восстанавливает core зависимости, затем исполняет embedded Python `-S NeuroMita.pyz` с явным `PYTHONPATH=Lib/core`, `NEUROMITA_RUNTIME_ROOT` и `NEUROMITA_ENVIRONMENT_DIR` (`scripts/run.py:816-859`). Код выхода `42` трактуется как сигнал уже применённого обновления — восстановить core dependency readiness и перезапустить; остальные exit codes пробрасываются наружу. `launch.py` — локальный dev wrapper для build+run по **тому же** production `run.py`, не самостоятельный функциональный runtime (`launch.py:1-11, :54-75`).

## CAP-DIST-003 — Core dependency bootstrap

**Source:** `scripts/run.py:62-94, 143-155, 340-536, 574-645, 647-778, 794-864`.

`run.py` намеренно удаляет `PYTHONHOME/PYTHONPATH` из базового окружения, задаёт `PYTHONNOUSERSITE/PYTHONSAFEPATH`, использует `-S` чтобы сторонний embedded/global site-packages не влиял на приложение (`:143-155, :838-852`). `core_is_healthy` сопоставляет requirements SHA256, Python identity, top-level entries, названия/версии/количество файлов дистрибутивов, probe imports и запрет AI distributions в core (`:482-536`). Проверка не является универсальной криптографической верификацией каждого wheel файла.

При необходимости `_CoreInstallLock` сериализует bootstrap (default timeout 900 s) (`:574-645`). `install_core_transactionally` ставит зависимости в `.core-staging-PID`, проверяет package file completeness и AI core leakage, затем `_activate_core`: существующая `Lib/core` переименовывается в backup, staging — в `Lib/core` с retry для Windows lock failures (`:690-778`). На синхронном исключении есть попытка возврата backup. Состояние записывается атомарным JSON только после activation. **Crash между переименованиями** — отдельная recovery задача; нельзя без тестов обещать полный power-loss atomic swap на произвольной ФС. Код `scripts/run.py` не делает Torch/ONNX runtime центральной зависимостью: они запрещены в `Lib/core`, их жизненный цикл — другой install layer.

## CAP-DIST-004 — канал обновлений и разделение release capabilities

**Sources:** `build.py:48-49, 229-240`; `scripts/launcher.c:72-125`; `scripts/validate_release_contract.py:29-155`; `src/release_contract.py`; `src/services/update_transaction.py`; `01-functional/launcher-and-updates.md`.

Наблюдаемые границы: build contour `test|release`, validation release assets/archive, install transactional update domain (отдельно от pip/AI Hub) и post-exit promotion zipapp native launcher. Внешние GitHub release API, версии release formats, пользователем инициируемые update scenarios, условия отката уже частично отражены в [Launcher/Updates](../01-functional/launcher-and-updates.md), не считать их автоматически полностью подтверждёнными этим build pass. Нельзя смешивать release/archive update, core dependency bootstrap и AI model install в один undifferentiated download mechanism.

## Требования к функциональному паритету

- `REQ-DIST-001`: пользователь получает дистрибутив, который запускается без системного Python/PyQt, с воспроизводимыми локальными ассетами и чётким списком обязательных файлов.
- `REQ-DIST-002`: механизм установки/обновления отделяет исполняемое приложение, core runtime dependencies, AI environments и user data; исключает утечку developer GPU artifacts.
- `REQ-DIST-003`: обновление активного исполняемого содержимого происходит после освобождения его процессами; неуспех оставляет работоспособный предыдущий экземпляр и диагностируемое pending состояние.
- `REQ-DIST-004`: launch/health/repair model явно отличает отсутствующий, повреждённый, устаревший и валидный runtime; runtime isolation нельзя выводить только из наличия файлов.
- `REQ-DIST-005`: release/test channel metadata, preservation of user data, ZIP/archive shape и metadata compatibility определяются как публичные требования, а не внутренние классы build.py.

**Возможная переорганизация:** нативный Rust Core может устранить конкретный `NeuroMita.pyz` и `Lib/core` bootstrap, но обязан сохранить пользовательские свойства самодостаточного старта, предотвращения смешивания AI dependencies, пользовательских данных, корректного atomic-ish update при блокирующих процессах и диагностики. **Rust alternatives:** исследование updater/installer/native zip libraries отложено; выбор не сделан.

## Открытые проверки

- Полная матрица release contracts по `src/release_contract.py` и `src/services/update_transaction.py` включая несовместимые архивы, checksum/signatures, offline updates и миграцию version schema.
- Supply chain создания embedded Python, его совместимости и лицензии; в ZIP видны output assumptions, но не доказан весь manufacturing pipeline.
- Тестирование Windows `MoveFileExW` при locks/crash/antivirus/OneDrive; `run.py` recovery после power loss между backup, rename и state JSON.
- Отдельные user data migration/compatibility при замене zipapp на Rust; API и форматы хранения исследуются независимо от способа сборки.

**Степень доказательности:** CONFIRMED для перечисленных source branches; HYPOTHESIS для гарантий после crash на Windows. Инсталлятор/лаунчер не исполнялся.

## Проверенный release archive contract (уточнение по `src/release_contract.py`)

**CAP-RELEASE-VALIDATE-001 — строгая публикация релиза.** Источник: `src/release_contract.py:171-325, 341-436`, `scripts/validate_release_contract.py:107-155`.

- По имени различаются `PythonBuild-{tag}.zip/.7z` (full), `PythonBuild-{tag}-Patch.zip/.7z`, `UnityBuild-{tag}.zip/.7z`, а также дополнительная full Python revision того же base tag при `python_archive_version(name) > parse_build_version(tag)` (`:171-189`). Неверно названные похожие архивы дают **error**, не silently ignored.
- Релиз обязан содержать **хотя бы один** Python full/patch. Более одного full Python / Python patch / Unity asset — **error**. Patch без full — warning: для fresh install необходим предыдущий full release (`:202-241`).
- Full Python archive обязан содержать `NeuroMita.pyz`, `requirements.txt`, `run.py`, `run.bat`, `Launcher.exe`, `libs/python/python.exe` и файлы под `Prompts/`, `assets/`, `libs/` (`:23-33, :244-271`). Вложенный `NeuroMita.pyz` должен иметь `__main__.py`, проходить ZIP test (`:157-169`). Следовательно одно лишь успешное исполнение `build.py` **не является доказательством** соответствия полного release archive контракту без embedded Python и остальных обязательных частей.
- Patch проверяется мягче: отсутствие очевидного runtime payload — warning; если он содержит `NeuroMita.pyz`, тот всё равно проверяется. Unity archive требует хотя бы один `.exe` (`:272-293`).
- Selection fallback ищет предыдущий full Python или Unity asset среди опубликованных release candidates, исключая drafts, непригодные assets, а в stable — prereleases; сортирует по published/created timestamp (`:341-436`). Это правило **источника update** и fallback availability, а не универсальный Rust install architecture.

**Нерешённое:** `validate_archive_contract` проверяет структуру/zipapp, но из прочитанного не следует, что он криптографически проверяет подпись выпуска; доверие к publisher, TLS, checksum manifest и protected testers нужно исследовать независимо. Не путать его с runtime asset checksum из updater. При будущей совместимости release channels необходимо отдельно решить, сохранять ли текущую схему именования или вводить versioned manifest с миграцией.
