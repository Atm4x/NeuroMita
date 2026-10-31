# Нишевые core-зависимости: есть ли реальные варианты Rust

Проверено 2026-10-31 по upstream source/docs и crates.io API. Это исследование доступности и границ, **не выбор архитектуры или окончательного stack**. GUI comparison исключён. Вопрос «есть ли аналог» отличаем от byte-for-byte parity, зрелости, лицензии, packaging и готовой integration NeuroMita.

## num2words2: отдельный Rust core уже существует

Фактическая функция NeuroMita — подготовка произносимого текста, замена целочисленных фрагментов по определённому языку с fallback/error policy; не обязательно вся API num2words. См. [языковой контракт](../01-functional/language-normalization-rag-morphology-and-speech-numerals.md).

**Вариант A:** upstream `num2words2-core`, отдельно от Python binding. Workspace разделён на core и py; core manifest перечисляет bigint/decimal Rust dependencies без PyO3. Public API содержит language lookup и conversion, включая русский. Это опровергает предположение, что данная функция принципиально существует только в Python. Проверены и [tag Python v1.0.20](https://raw.githubusercontent.com/gladiaio/num2words2/v1.0.20/rust/Cargo.toml), и [текущий core manifest](https://raw.githubusercontent.com/gladiaio/num2words2/master/rust/num2words2-core/Cargo.toml), и [public Rust API](https://raw.githubusercontent.com/gladiaio/num2words2/master/rust/num2words2-core/src/lib.rs).

Есть **существенное расхождение license metadata**: tag v1.0.20 workspace объявляет MIT OR Apache-2.0, а текущий master workspace прямо указывает LGPL-2.1-only и происхождение от LGPL engine. Registry num2words2-core0.1.3 ещё показывает MIT OR Apache-2.0. Нельзя считать старую metadata доказательством отсутствия LGPL obligations; требуется проверка конкретного выбранного source revision и его provenance. Фиксируется расхождение, не правовое заключение. [Текущий workspace](https://raw.githubusercontent.com/gladiaio/num2words2/master/rust/Cargo.toml).

**Вариант B:** [chislo](https://docs.rs/chislo/0.3.1/chislo/) — native Russian numbers/gender/declension, MIT. Это реальная RU альтернатива, но **не полный многоязычный replacement**. Отдельный [num2words 1.2.0](https://docs.rs/num2words/1.2.0/num2words/) имеет ограниченный список EN/FR/UK, без заявленного русского. Нельзя подставлять его в таблицу как готовый RU аналог только из-за совпадения имени. Полная языковая политика нужна из текущего функционального контракта; сочетание языковых engines или собственные правила — отдельный вариант, пока не выбран.

## pymorphy3: реальные Rust analyzers, качество требует проверки

Нужны не embeddings/inference, а normal_form и lexeme для RAG keywords/FTS, ranking неоднозначных parses и предсказуемый fallback. Stemmer/prefix — уже существующая деградация, не эквивалент словаря.

**A:** [rs-morphy4 0.1.3](https://docs.rs/rs-morphy4/0.1.3/rs_morphy4/) реализует русские анализ/словоизменение, допускает embedded/external dictionaries. Release2026-10-16, очень молодой. Cargo: Rust1.88; license expression `Apache-2.0 AND MIT AND CC-BY-SA-3.0` — нельзя сокращать до Apache: словарные данные имеют отдельные условия. [Manifest](https://raw.githubusercontent.com/LdDl/rs-morphy4/main/Cargo.toml).

**B:** [rsmorphy0.4.0](https://docs.rs/crate/rsmorphy/0.4.0) — Rust реализация pymorphy2, опубликована2018-08-26, upstream явно WIP/unstable, docs build отсутствует; code MIT/Apache, dictionary dependency отдельно. Это свидетельство наличия технологии, но слабое основание рекомендовать без build/corpus проверки. Поиск не доказывает отсутствие других реализаций.

Parity gate: выбранный dictionary revision, normal_form первого parse на омонимах, полный/ограниченный lexeme, ё/е, неизвестные слова/дефисы, sort/cap20 forms, stopwords, RU/non-RU mix и fallback. Ни одного comparative corpus run этих Rust crates здесь не выполнено. **Вывод: «на Rust совсем нет морфологии» неверен; «есть drop-in pymorphy3 той же зрелости и результатов» не доказано.**

## Optional langdetect и Unicode heuristic: отдельная core-функция

В `src/utils/__init__.py` optional langdetect не входит в корневые requirements, но используется для выбора языка произносимых числительных. Перед ним действует собственная Unicode-name heuristic; статистический detector вызывается при отсутствии heuristic result, на тексте длиной минимум 20 и sample до 800 chars, с DetectorFactory.seed=0. Это text preprocessing, не перенос TTS inference на Rust.

**A:** [whatlang 0.18.0](https://docs.rs/whatlang/0.18.0/whatlang/) определяет язык/script, confidence/reliability и allow/deny lists, MIT. Последний проверенный stable release 2025-10-16. **B:** [lingua 1.8.0](https://docs.rs/lingua/1.8.0/lingua/) даёт offline rule/statistical detection, confidence, ограничение языков, mixed-language и short-text режимы; Apache-2.0, release 2026-03-09. Lingua не требует neural network/API, но language-model assets и features имеют стоимость: upstream для default all-75 models указывает около 300 MB downloads. Это не измеренный размер нашего будущего бинарника и не benchmark.

Дополнительный кандидат **C:** [langdetect 0.1.0](https://docs.rs/langdetect/0.1.0/langdetect/) опубликован 2026-10-11, Apache-2.0, Rust 1.85. Upstream **заявляет** reproduction Python langdetect 1.0.9 с seed/Compat; сравнительный corpus здесь не запускался. [Core Cargo manifest](https://raw.githubusercontent.com/SyntaxSpirits/langdetect-rs/main/crates/langdetect/Cargo.toml) содержит Rust getrandom/regex/rustc-hash/serde_json, Python binding вынесен в отдельный workspace member. Очень свежий port нельзя выдавать за независимое подтверждение bit parity или зрелый default.

Для script heuristic доступны [unicode-script 0.5.8](https://docs.rs/unicode-script/0.5.8/unicode_script/) (MIT OR Apache-2.0, Script/Script_Extension) и [unicode_names2 4.0.0](https://github.com/progval/unicode_names2) (registry license `(MIT OR Apache-2.0) AND Unicode-DFS-2016`, char↔name). Unicode property и первый token Unicode character name — разные алгоритмы. Нельзя обещать одинаковый язык на всей кириллице, латинице и mixed CJK просто заменой одного helper другим.

Metadata versions/licenses/dates/non-yanked проверены read-only crates.io API 2026-10-31. Parity gate: короткие латинские фразы, script ambiguity, mixed language, undefined language, deterministic seed, confidence policy, unsupported numeral locale, optional package absent и Unicode data revision. Ни один из трёх detector crates здесь не собирался/исполнялся.

## Telethon: нужен user-account MTProto, Bot API недостаточно

Current Telegram voice отправляет текст внешнему боту от user session, проходит code/2FA, correlates replies/downloads и конвертирует audio. Поэтому crate для Telegram Bot API сам по себе не является заменой.

**A:** [grammers-client0.11.0](https://docs.rs/grammers-client/0.11.0/grammers_client/) — Rust MTProto client, user/bot accounts, sessions/raw TL, media; MIT OR Apache-2.0, release2026-10-15. Требуются свои API ID и корректные rate-limit/session/reconnect policies. Это существующий protocol client, не только thin HTTP Bot API wrapper.

**B:** [TDLib](https://core.telegram.org/tdlib) через [tdlib-rs1.4.0](https://docs.rs/tdlib-rs/1.4.0/tdlib_rs/) или прямую C/JSON FFI. Официальный native client поддерживает networking/encryption/local state; Rust wrapper MIT/Apache, TDLib Boost1.0. Native C++ build/link/runtime — отдельный distribution cost, не Python requirement. TDLib session storage не равен Telethon .session; переписывание с нуля не означает обязательную binary compatibility этих файлов. [TDLib license](https://github.com/tdlib/td/blob/master/LICENSE_1_0.txt).

Parity gate: code/2FA/cancel/timeout, свой request identity, reply filtering, voice media/download, flood wait/reconnect, logout/session ownership. Live Telegram login не выполнялся. Не доказана работа конкретного внешнего бота ни для одной реализации.

## tiktoken и python-chess

Token estimation имеет fallback и provenance method; provider billable usage — отдельный результат. **A:** [tiktoken-rs0.12.1](https://docs.rs/tiktoken-rs/0.12.1/tiktoken_rs/), MIT, tiktoken encodings. **B:** [Hugging Face tokenizers0.23.2](https://docs.rs/tokenizers/0.23.2/tokenizers/), Apache2, native Rust pipeline для model-specific tokenizers. Они не взаимозаменяемы для произвольной модели без нужных vocabulary/normalization/special tokens. Нужны RU/JSON/image/tool overhead fixtures и offline asset policy; новый tokenizer не превращает estimate в точный billing.

Chess rules **A:** [shakmaty0.30.2](https://docs.rs/shakmaty/0.30.2/shakmaty/) — legal moves/outcomes/FEN/SAN/UCI/variants, GPL-3.0-or-later; **B:** [cozy-chess0.3.4](https://docs.rs/cozy-chess/0.3.4/cozy_chess/) — legal generation/Chess960/UCI helpers, MIT, более узкий контракт. ДляB отдельно проверить SAN/history/repetition/claim-draw; нельзя выдавать move generator за весь python-chess API. Lc0 UCI subprocess и Maia weights остаются отдельными resources, они не исчезают после выбора rules crate.

## Срез registry и доказательства

Метаданные получены read-only GET `https://crates.io/api/v1/crates/<name>`: stable version/license/publish time/MSRV/yanked; прочитаны upstream docs указанных версий. Все названные published versions не yanked при проверке. `num2words2-core0.1.3` registry license противоречит текущему upstream — отмечено выше. Недавняя публикация не доказывает качество, старая публикация сама по себе не доказывает неисправность. No build/benchmark/native installation выполнены; нет обещания ABI/byte parity.

На исследованных niche core функциях **не выявлена возможность, для которой отсутствует какой-либо путь исполнения под Rust host без Python Core**. Это ограниченный вывод по подтверждённым функциям. Он допускает native C/C++ libraries и отдельный Python AI; не означает «весь Python requirements можно заменить одной Cargo-командой».
