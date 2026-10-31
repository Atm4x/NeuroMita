# NeuroMita — минимальное ядро контрактов

Новая Rust-реализация с нуля. Один процесс/одно ядро, статические Api, владельцы персонажей, субъективный контекст, очереди, эффекты, независимые presenters, типизированные settings/binding и ServerLifecycle.

Актуальные детали: [контракты](../future/minimal-contracts.md), [чеклист](../future/implementation-checklist.md), [HANDOFF](HANDOFF.md). Исторический первый срез описан [отдельно](../future/first-slice.md).

## Offline-сборка и передача веб-агенту

Выполнять из каталога проекта, чтобы Cargo прочитал .cargo/config.toml:

```sh
cd audit-docs/rust
cargo test --locked --offline
cargo clippy --locked --offline --all-targets -- -D warnings
cargo fmt --all -- --check
```

Tokio включён с full. Cargo.lock и vendor/ содержат текущий разрешённый набор зависимостей для платформ сборки. Vendor не заменяет Rust toolchain и native build tools. Минимум Rust 1.89; проверено на Rust 1.99.1 / Windows MSVC. Native aws-lc-sys требует C/CMake build environment.

Не менять line endings/содержимое vendor вручную: Cargo проверяет checksums. Исходники и лицензии vendored crates сохраняются в Git, target/ не включается.

## Запуск

Требуется GEMINI_API_KEY в окружении. Ключ не передаётся в аргументах и не печатается. Модель, персонаж и адрес listener задаются явно:

```sh
cargo run --locked --offline -- --help
cargo run --locked --offline -- --model YOUR_GEMINI_MODEL --character mita --listen 127.0.0.1:5555
cargo run --locked --offline -- --model YOUR_GEMINI_MODEL --character mita --listen 127.0.0.1:5555 --message "Привет"
```

YOUR_GEMINI_MODEL — доступный вам model ID. Стартовый состав: mita, kind-mita. Описания и промпты минимальные, без переноса всего функционала Python.

Консольные команды: /character mita, /character kind-mita, /cancel REQUEST_UUID, /quit. Ctrl+C завершает приложение; EOF ждёт отправленные данным frontend обращения. Консоль вызывает ChatPresenter и наблюдает его модель. Она не готовит Gemini wire payload и не меняет Character напрямую.

## Генерация и результаты

GenerationPreset содержит типизированный ProviderTemplate. Текущий адаптер — GeminiProvider с GeminiTemplate. URL, авторизация, wire format и обработка ответа находятся в generation/gemini. Общий GenerationProvider не предполагает HTTP или Gemini.

Авторизация Gemini соответствует исходному Python-протоколу google_gemini_default: ключ передаётся как URL query-параметр ?key=..., без x-goog-api-key/Authorization. Значение кодируется URL builder. Authenticated URL не сохраняется в trace, ключ скрывается в Debug, transport errors формируются через without_url().

HTTP-клиент reqwest собирается с json, rustls, http2 и system-proxy. Системный прокси Windows/macOS подхватывается автоматически; переменные окружения прокси также учитываются. HTTP/2 согласовывается с сервером, HTTP/1.1 остаётся доступен. Локальный адрес прокси не зашит в код. Изменения системного прокси после создания клиента требуют пересоздания клиента.

Нет каталога, CRUD, ротации и fallback пресетов. В точке сборки явно задаётся шаблон; начальные параметры Gemini: temperature 0.7, max output tokens 2048, timeout 60 секунд.

ChatApi предоставляет reply/react/initiate/send и возвращает RequestHandle. Есть Pending, Processing(Text/Voice), Finished с типизированным исходом и Cancelled.

До Accepting отмена прекращает оставшуюся работу и не применяет эффекты. После входа в Accepting отмена возвращает TooLate. Ответ и эффекты принимаются до Finished и до следующей работы того же персонажа.

Озвучка подключается через VoiceProvider. Успех возвращает текст/аудио; ошибка озвучки возвращает принятый текст и VoiceGenerationFailed. При отмене озвучки пакет отвергается. InternalError сохраняет доступный частичный текст.

По умолчанию реальный voice engine не настроен: UnavailableVoiceProvider возвращает явную ошибку, а не фиктивное аудио. Флаги озвучки начального профиля выключены.

## Настройки и binding

SettingsApi предоставляет snapshot/replace/edit/observe/flush/retry_save. Структуры разделов: VoiceSettings, CaptureSettings, InterfaceSettings. Volume валидируется как тип. Обязательные поля сериализованной конфигурации не восполняются скрытыми defaults.

SettingsPresenter.voice предоставляет bindable volume/in_launcher/in_game/voice: get, set и observe. Значение из другого источника обновляет свойство; наблюдение не вызывает повторную запись. Ошибка проверки оставляет подтверждённое значение.

Начальный CLI-профиль явно использует MemorySettingsRepository. JSON-хранение подключается через ApplicationConfig.settings: SettingsSource::Initial или Stored и JsonSettingsRepository. Ошибка сохранения наблюдаема отдельно от принятия значения; явный retry защищён от старой запоздавшей ошибки.

## Тестовый сетевой контракт

ServerLifecycle обслуживает TCP с UTF-8 JSON lines. Каждое сообщение завершается newline. Сразу после подключения приходит connected с client_id; далее settings snapshot и обновления.

Для простейшей проверки отправить строку:

```text
test
```

Она создаёт запрос с текстом test и персонажем ServerConfig.test_character. Приходит accepted с request_id, затем request_status. GuiPresenter обнаруживает эту работу независимо от сетевого исполнителя.

Структурированные команды:

```json
{"command_id":"00000000-0000-4000-8000-000000000001","command":"test"}
{"command_id":"00000000-0000-4000-8000-000000000002","command":"reply","character":"kind-mita","text":"Привет"}
{"command_id":"00000000-0000-4000-8000-000000000003","command":"settings"}
{"command_id":"00000000-0000-4000-8000-000000000004","command":"set_volume","value":55}
{"command_id":"00000000-0000-4000-8000-000000000005","command":"cancel","request_id":"REQUEST_UUID"}
```

Для нового намерения нужен новый command_id. Повтор того же ID/содержимого в окне квитанций возвращает прежний RequestId; другой payload с тем же ID даёт ошибку. Квитанции ограничены текущим соединением и ёмкостью, а не являются вечной дедупликацией.

Отмена доступна для запросов данного соединения. Отключение клиента прекращает его наблюдение, но не отменяет уже принятую работу ядра. Настройки in_game управляют запросом озвучки сетевого клиента; in_launcher — запросами presenter.

Ограничены клиенты, размер команды, выходные очереди и квитанции. Это минимальный контракт, без аутентификации и совместимости с текущим Unity wire protocol.

## Timeline, персонажи и диагностика

Timeline — Vec с EventId, branch ID и through. CharacterHandler предоставляет get_context(at); факты фильтруются по знанию персонажа. Историческое состояние минимального счётчика восстанавливается по префиксу. Старый контекст не применяется к изменившемуся Character молча.

Character владеет description/prompts/state, а живым Character владеет один CharacterHandler. Registry выдаёт handles. Разные персонажи генерируются параллельно, один персонаж — последовательно.

ChatApi::trace(id) возвращает активный или недавно завершённый RequestTrace отдельно от смыслового timeline: input, redacted preset description, контекст, подготовленный текст, переходы и фазы. Число завершённых traces ограничено discovery_buffer. Terminal RequestRecord удаляется; существующие handles сохраняют итог.

## Проверки и ограничения

Локальные тесты не требуют сети/ключа. contracts.rs проверяет настройки, IO/retry, binding, at, семантические обращения, озвучку/частичный результат/отмену, эффекты, TCP test/status/settings, повтор и фрагментированный ввод. vertical_slice.rs проверяет настоящий HTTP-адаптер формата Gemini через локальный сервер.

Ignored live_gemini.rs запускается только с явными NEUROMITA_LIVE_GEMINI_PRESET_FILE и NEUROMITA_LIVE_GEMINI_PRESET_ID. Проверка 2026-11-01 с пресетом Main / gemini-3.6-flash прошла за 1,99 секунды: ответ «Готово.». Переменные HTTP_PROXY/HTTPS_PROXY/ALL_PROXY/NO_PROXY были очищены только в тестовом процессе; использовался системный Windows-прокси. Ранний TCP timeout был вызван отсутствием system-proxy в нашей сборке reqwest. Отдельная проверка без ключа согласовала HTTP/2 с тем же хостом. Ключ не выводился, не сохранялся и не изменялся.

Нет тяжёлой SessionTimeline реализации, БД и crash recovery, Slint/TUI renderer, tools, мультимодальности, стриминга токенов и реального TTS-движка. Сейчас реализованы обсуждённые связи и минимальные исполняемые контракты.

Python/Unity-исходники не изменялись. Отдельный Git-репозиторий/workspace внутри проекта не создавался.
