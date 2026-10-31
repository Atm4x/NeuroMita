# Транзитивные зависимости и native artifacts: локальные свидетельства

Дата: 2026-10-31. Дополнение к [реестру 84 requirements](full-requirements-runtime-evidence-ledger.md). Исследованы METADATA/RECORD **локального venv**, без импорта исследуемых пакетов, исполнения DLL, установки пакетов или изменения среды. Найден 131 dist-info/METADATA. Это не lock релиза, не состав всех managed AI environments и не доказательство использования каждой установленной библиотеки. Для разбора PE отдельно использован pefile; binaries не загружались.

## Parent dependencies теперь подтверждены metadata

| Installed parent/version | Requires-Dist без extra | Extra/условные зависимости, отдельно |
|---|---|---|
| telethon1.38.1 | pyaes, rsa | cryptg extra |
| tiktoken0.8.0 | regex>=2022.1.18, requests>=2.26 | blobfile extra |
| httpx0.27.0 | anyio, certifi, httpcore1.*, idna, sniffio | h2 — http2 extra, brotli/socks/cli отдельно; requirements проекта также задаёт h2 явно |
| pydantic2.10.6 | annotated-types, pydantic-core2.27.2, typing-extensions | email/timezone extras и Windows marker не автоматически active |
| requests2.32.3 | charset-normalizer, idna, urllib3, certifi | socks/use_chardet extras |
| mistralai1.5.1 | eval-type-backport, httpx, jsonpath-python, pydantic, python-dateutil, typing-inspect | google-auth/requests по gcp extra |
| soundfile0.13.1 | cffi, numpy | — |
| nodriver0.50.3 | mss, websockets>=14, deprecated | dev docs/format/test tools не runtime |
| pyworld0.3.5 | numpy | nose test, cython/numpy sdist |
| google-cloud-storage3.12.1 | google-auth, google-api-core, google-cloud-core, google-resumable-media, requests, google-crc32c | grpc/protobuf/tracing/testing extras и version markers отдельно |

Наличие parent в venv не доказывает production ingress: для mistralai/nodriver/pyworld/GCS прямой активный Core consumer прежним source discovery не подтверждён. Но отсутствие прямого import у pyaes/rsa/jsonpath-python/etc **уже нельзя трактовать как отсутствие причины установки**: конкретные parent edges наблюдались. Удаление parent из будущего Rust Core меняет необходимость этих Python transitives; это не отдельная потерянная пользовательская функция.

num2words2 и pymorphy3 в этой venv metadata отсутствуют. Поэтому их upstream свойства исследуются отдельно; локальное окружение не используется как oracle requirements completeness. Python tests, запускаемые другим interpreter, также не характеризуются автоматически этой metadata. Точный resolver graph требует marker/extras evaluation и lock именно целевого package set; плоский список requirements, даже с84 entries, этого не заменяет.

## Нативные файлы из wheel RECORD

Посчитаны .pyd/.dll/.exe entries, не проверена загрузка и не доказано, что каждое entry сейчас существует. Количество включает launcher EXE и optional modules, не равно числу runtime DLL dependencies.

| Distribution | Native entries | Примеры |
|---|---:|---|
| numpy1.26.0 |21| OpenBLAS DLL, _multiarray_umath.cp312-win_amd64.pyd |
| onnx1.21.0 |4| onnx_cpp2py_export.pyd и command launchers |
| pyaudio0.2.14 |1| _portaudio.cp312-win_amd64.pyd |
| pycryptodome3.21.0 |42| Crypto/Cipher/*.pyd |
| pydantic-core2.27.2 |1| _pydantic_core.cp312-win_amd64.pyd |
| pygame2.6.1 |53| SDL2.dll, SDL2_image/mixer/ttf и extension modules |
| pywin32 312 |59| win32 bindings, Pythonwin/PyISAPI and launchers |
| pywinpty3.0.5 |5| _winpty.pyd, OpenConsole.exe, conpty.dll, winpty-agent.exe |
| pyworld0.3.5 |1| pyworld.cp312-win_amd64.pyd |
| sounddevice0.5.1 |2| libportaudio64bit.dll и ASIO variant |
| soundfile0.13.1 |1| libsndfile_x64.dll |
| tiktoken0.8.0 |1| _tiktoken.cp312-win_amd64.pyd |

Для Rust Core эти файлы не становятся автоматически требуемыми DLL. Требуются функции: audio/capture/codecs/crypto/PTY/token counting; их реализации могут иметь другой native graph. SQLite, FFmpeg, Windows APIs, TDLib и OpenCV допустимо рассматривать как C/C++/system libraries под Rust host: наличие native dependency не означает необходимость Python. Inference packages/weights остаются отдельным Python contour.

Не закрыто этим свидетельством: PE delayed/dynamic imports, фактический bundled release DLL search path, требуемые VC runtime, архитектура x64/ARM, codec build flags, runtime optional features и весь граф managed layers. Эти условия относятся к воспроизводимой сборке/испытанию конкретного дистрибутива. Нельзя утверждать «нативных зависимостей нет» или «все transitives известны» по одному RECORD. Исходники/среда не изменялись.

## Дополнительная read-only PE проверка

Шесть реально существующих binaries прочитаны через pefile из локальной venv, **не загружались в процесс через LoadLibrary**. Python-B исключал создание bytecode. Direct/delay import directories разобраны; у этих шести delay entries пусты.

| Binary | Выявленные зависимости, сокращённо |
|---|---|
| pydantic_core/_pydantic_core.cp312-win_amd64.pyd | python312, bcrypt, advapi32, kernel32, ntdll, VCRUNTIME140, UCRT math/runtime/heap |
| tiktoken/_tiktoken.cp312-win_amd64.pyd | python312, bcryptprimitives, kernel32/ntdll, synchronization API-set, VCRUNTIME140, UCRT |
| _soundfile_data/libsndfile_x64.dll | SHLWAPI, KERNEL32, VCRUNTIME140, UCRT API-sets |
| _sounddevice_data/.../libportaudio64bit.dll | WINMM, ole32, SETUPAPI, KERNEL32, USER32, ADVAPI32 |
| winpty/_winpty.cp312-win_amd64.pyd | conpty.dll, winpty.dll, python312.dll, Windows API-sets/OS DLL, VCRUNTIME140/UCRT |
| pygame/SDL2_mixer.dll | SDL2.dll, WINMM, KERNEL32, msvcrt |

Это добавляет конкретные PE edges, не общий proof loadability: API-set resolution, динамическая загрузка codecs и рекурсивные dependencies DLL так не проверены. Нельзя копировать Python312 ABI dependency в требования native Rust host. Наличие Rust реализации функции также не отменяет автоматически VC/system runtime у выбранных C/C++ dependencies.

## Reverse-parent sweep всех 84 requirements

Отдельным read-only проходом разобраны **все 131 METADATA** и Requires-Dist через packaging.Requirement, parse failures 0. Metadata присутствует для 82 из 84 root distributions; отсутствуют num2words2 и pymorphy3. Найдено 916 declared edges **включая все extras/test/docs/self references**, без marker/extras resolution; это не 916 реально активных dependencies. У 54 root names есть хоть одна local parent reference, у 41 — хотя бы одна без marker. У 30 parent reference в этой venv нет: это не доказательство ненужности root.

Дополняющие конкретные parent edges (к прежнему STATIC-NOT-FOUND реестру):

| Root packages | Наблюдаемый installed parent | Что доказано и что нет |
|---|---|---|
| aiohappyeyeballs, aiosignal, attrs, frozenlist, multidict, propcache, yarl | aiohttp3.12.13 | Requires-Dist edges; сам active Core caller aiohttp от этого не появляется |
| altgraph | macholib1.16.3 | Packaging helper parent; не доказанная пользовательская Core функция |
| distro, jiter | openai1.61.1 | В venv есть SDK parent, хотя current Core работает через собственные provider transports; installed SDK не обязательно active ingress |
| eval-type-backport, jsonpath-python, python-dateutil, typing-inspect | mistralai1.5.1 | Конкретные SDK transitives; source reachability самого SDK отдельно |
| mypy-extensions | typing-inspect0.9.0 | Есть marker-free parent; прочие найденные edges относятся к checks/type extras |
| six | python-dateutil2.9.0.post0 | Compatibility dependency, не отдельный продуктовый сценарий |
| pyasn1 | rsa4.9 и pyasn1_modules0.4.2 | Crypto chain; наличие не означает собственное Core ASN.1 API |
| pycparser | cffi1.17.1 | CFFI tooling dependency |
| brotli | py7zr1.0.0 на CPython | Это не только optional HTTP compression; PyPy branch выбирает brotlicffi |
| h11 | httpcore1.0.7, uvicorn0.51.0 | HTTP transport и standalone server имеют разные ingress |
| httpcore / anyio / certifi / idna / sniffio | HTTPX0.27.0 и другие HTTP parents | Parent evidence есть; конкретные HTTP features/marker conditions сохраняются |
| charset-normalizer / urllib3 | requests2.32.3 | Не самостоятельный Core web protocol |
| colorama | colorlog6.9.0, tqdm4.67.1, click8.4.2 по Windows markers | Цвет терминала; marker условный, не всякий extra считается active |
| pyaudio | SpeechRecognition3.14.1, extra=audio | Реальный parent edge, но включение extra не доказано; root requirements также задаёт pyaudio явно |
| pywin32 | portalocker3.2.0 на Windows | Есть и косвенная lock dependency; direct OS/DPAPI consumers описаны отдельно |
| platformdirs | setuptools75.8.0, extra=core; отдельно явный Beat install plan | Не найденный direct Core import не отменяет installer-owned роль |
| h2 | HTTPX/httpcore extra=http2; urllib3 extra=h2 | Отдельно Core find_spec feature probe и explicit root h2 constraint |

### Distribution name, import name и незаявленные transitives

| Root / installed version | Прямые Requires-Dist, выбранные существенные |
|---|---|
| bs4 0.0.2 | beautifulsoup4 |
| dotenv 0.9.9 | python-dotenv |
| python-chess 1.999 | chess>=1,<2 |
| ddgs9.14.3 | click>=8.1.8, primp>=1.2.3, lxml>=4.9.4; api/dht extras отдельно добавляют FastAPI/uvicorn, не обязательные для базового поиска |
| py7zr1.0.0 | texttable, pycryptodomex, brotli/brotlicffi, psutil, pyzstd, pyppmd, pybcj, multivolumefile, inflate64; tests/docs/check extras не runtime по умолчанию |
| qtawesome1.4.2 | qtpy |
| PyQt6 6.11.0 | PyQt6-sip, PyQt6-Qt6; это также Qt binary distribution, не один Python файл |
| h2 4.3.0 | hyperframe<7,>=6.1 и hpack<5,>=4.1 |
| SpeechRecognition3.14.1 | typing-extensions; на Python≥3.13 standard-aifc/audioop-lts; engine/audio extras имеют отдельные dependency sets |

Таким образом, корневые 84 строки — не полный wheel/native graph. И обратное: parent в локальной venv не делает автоматически его SDK или extras обязательным Core. Для решения о native rewrite используются [функции и реальные alternatives](core-library-alternatives-and-native-costs.md), а для воспроизводимости конкретного Python AI/backend дистрибутива нужен target lock/environment с явно выбранными extras/markers. Этот sweep ничего не устанавливал, не удалял и не импортировал из приложения.
