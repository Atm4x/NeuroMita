# Языки, пользовательские переводы и настройки представления

**Capabilities:** CAP-I18N-001/002, CAP-UI-PREF-001. **Статус:** ACTIVE. Эта группа не использует внешнюю службу машинного перевода.

Язык интерфейса сохраняется setting LANGUAGE. Builtin JSON catalogs загружаются zip-safe через importlib.resources; внешние {base}/Localization/{code}.json перекрывают builtin. RU — исходная строка, для остальных fallback: выбранный catalog → EN catalog → inline English → исходная RU. Имя языка берётся из known display names либо _name внешнего каталога. Available list строится из найденных JSON, compact list ограничивается RU/EN. Пользователь может открыть внешний каталог: helper создаёт template/README только при их отсутствии. Для добавления нового файла UI-инструкция предлагает restart.

Фактическая смена уже доступного языка живая: set_language пишет settings, сбрасывает catalog cache, переустанавливает зарегистрированные тексты и отправляет language_changed(code). Qt notifier используется только в live layer; translation engine stdlib JSON/dict/threading. Виджеты регистрируются через weak references с setter/source pair; удалённые Qt objects отсеиваются. Dynamic views пересчитываются по signal.

TrStr хранит ru/en source pair в subclass str, чтобы declarative schema могла зарегистрировать live label. Конкатенация/format преобразует в обычную строку и теряет source metadata; непокрытые динамические labels могут обновляться иначе либо требовать restart. Options combobox сохраняют machine IDs, переводят только display labels под QSignalBlocker. Поэтому язык UI не должен изменять provider/model/enum identity. Tooltip language setting ещё говорит «после перезапуска», хотя callback вызывает live layer: UI текст и действующее поведение различаются.

General settings управляют видимостью settings sections и Sandbox panels, размером chat font/шириной bubble, timestamps, показом thinking/system notes/token-cost stats. Эти controls меняют представление, а не гарантируют отсутствия данных в истории/файлах. HIDE_PRIVATE маскирует Telegram ID/hash/phone и Google credentials в интерфейсе; исходный tooltip прямо отделяет это от шифрования/удаления/изменения отправки. Полный audit secret storage выполняется в settings/API branch.

Новая GUI должна уметь live language switch, external user catalogs/fallback, стабильные machine IDs, локальную справку другого языка и сохранённые предпочтения представления. Нужно определить coverage/status не обновившихся labels и поведение malformed locale. Текущие source-string keys/TrStr/weakref registry не являются обязательной схемой для Rust; выбор формата переводов и toolkit остаётся открытым.

Источники: localization/__init__.py, live.py и schema.py по полным translation/update paths; language_settings целиком, general settings visibility/privacy/IPC/chat controls, Sandbox panel registry. Полнота перевода всех строк/catalogs и live UI layout не проверялась, пользовательская Localization папка не открывалась и не создавалась.
