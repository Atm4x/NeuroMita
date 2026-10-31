# Русская морфология поиска и языковая нормализация текста для речи

> Исследован функциональный контракт, **а не готовая Rust-библиотека**. `src` из CodeNow.zip. Эти две языковые задачи имеют разные входы, выходы, качество и runtime-границы. Не смешивать русскую лемматизацию с TTS и не выводить из требований к первой перенос AI inference на Rust.

## CAP-LING-RAG-01 — токены и леммы поиска памяти/истории

**Статус:** `CONDITIONAL`, включается параметрами RAG. Источники: `src/managers/rag/rag_utils.py:15-32,58-240`, `src/managers/rag/pipeline/query_builder.py:11-80`, `src/managers/rag/pipeline/retrievers/keyword_only.py`, `src/managers/rag/pipeline/config.py:320-336`.

При построении поискового запроса исходный текст очищается от memory-команд и числовых pose-тегов, оставшаяся разметка снимается, пробелы нормализуются. `QueryBuilder` берёт **первичную фразу пользователя** и **расширенный контекст последних сообщений**; keywords извлекает отдельно, из расширенного контекста может брать последние токены первыми. Объединяет без дублей до configured `kw_max_terms`, в отдельном шаге получает query embedding. Структура `QueryState` хранит original/expanded query, keywords, query vector, context actors/participants (`query_builder.py:16-80`).

Токенизация `TOKEN_RE` выделяет Unicode кириллицу/латиницу/цифры; стоп-слова берутся из локального набора. Чисто цифровые токены исключаются, одно и то же normalized слово даёт одно keyword; лимит длины и количества задаются конфигурацией. Лемматизация применяется только при `lemmatize=True`: для кириллицы `pymorphy3.MorphAnalyzer().parse(token)[0].normal_form`; для прочих токенов сохраняется lowercase. Если morph unavailable, используется локальный русский stemmer только при `RAG_RU_STEMMER_ENABLED`, иначе исходная форма. Этот функциональный fallback — **не функционально эквивалентная лемма**: результат стеммера может быть не словарной формой. `keyword_score` при лемматизации нормализует обе стороны перед расчётом доли совпадений, без неё ищет word-boundary occurrences (`rag_utils.py:62-240`).

**Роль в RAG:** keyword path дополняет FTS/vector и контекст; параметр `RAG_KEYWORD_SEARCH` управляет этим каналом. Нельзя утверждать, что векторный retrieval сам требует морфологии или что все режимы поиска используют одинаковую нормализацию.

## CAP-LING-RAG-02 — морфологическое расширение FTS5

**Статус:** `CONDITIONAL` по `RAG_FTS_MORPH_EXPAND`, платформе и установленному анализатору. Источники: `src/managers/rag/rag_utils.py:244-334`, `src/managers/rag/pipeline/retrievers/fts.py:40-64`, `src/managers/rag/pipeline/config.py:333-336`.

Для FTS5 поисковый запрос преобразуется в строку `MATCH`: исходный пользовательский запрос приоритетен; только при пустом итоговом MATCH используется expanded query. Берутся ограниченное число исходных токенов (а не всех порождённых форм), стоп-слова и слишком короткие отбрасываются. Для кириллицы при включённом расширении `pymorphy3.parse()[0].lexeme` даёт набор допустимых словоформ; он вместе с исходным токеном сортируется, обрезается до `max_forms=20` на слово и комбинируется `OR`. Если анализатор недоступен, строится **prefix** `"<stem>"*` на локальном стеммере, если разрешён; иначе — `"<token>"*`. Без morph expansion действует настроенное `prefix_match` либо точная quoted-токенизация. Это влияет на полноту/точность полнотекстового поиска и является самостоятельным функциональным требованием, не просто заменой import.

FTS retrieval по `memory` и `history` выполняется независимо при `search_memory/search_history`, возвращает top-k кандидатов с BM25 рангом, score features и связанными meta. Идентичность memory candidate — `eternal_id`, history candidate — SQL `id` (`fts.py:66-181`).

## CAP-LING-SPEECH-01 — подготовка произносимого текста

**Статус:** `ACTIVE` на известных путях подготовки TTS; реальные последствия зависят от доступной голосовой модели. Источники: `src/utils/__init__.py:316-324,326-420,423-502`, `src/utils/Testing/test_num2words2_integration.py:20-42`.

Пайплайн `process_text_to_voice` (1) удаляет HTML/markup, (2) определяет язык сначала по Unicode script heuristic, затем через `langdetect` для остальных случаев, (3) разворачивает целочисленные фрагменты текста в слова посредством `num2words2`, (4) оставляет буквы, пробельные символы и ограниченную разрешённую пунктуацию, (5) схлопывает пробелы; пустой текст превращает в `...`. Код языка нормализуется (`zh-cn→zh`, `pt-br→pt_BR`, etc); неподдерживаемый `num2words2` язык fallback в английский только на `NotImplementedError`, другие ошибки оставляют исходный числовой токен. Кэш чисел действует в рамках одного вызова. Regex работает с `[-+]?\d+`, поэтому **не обещать** обработку дробных, валютных и других сложных форматов, которую код не реализует.

Это обработка текстового **представления** для TTS, а не аудио-инференс. Для функционального паритета нужны детерминированные языковые/числовые тест-кейсы и явная политика неподдерживаемого языка. Простая «замена чисел английскими словами» теряет многоязычную возможность проекта.

## Контракты и непроверенные вопросы

| Capability | Вход | Выход | Владелец действующего состояния | Проверка |
|---|---|---|---|---|
| Keyword normalize | query + settings + стоп-слова | набор нормализованных поисковых термов | RAG QueryBuilder, функции normalization | русский инфинитив/падеж, некириллическое слово, stopword, дубли |
| FTS expansion | query + prefix/morph flags | FTS5 MATCH-выражение | RAG FTSRetriever | точная форма / lexeme / fallback stem-prefix, OR, лимиты |
| TTS text prep | текст + язык(выведенный) | очищенная произносимая строка | Core speech text pipeline | RU/EN/PT-BR, отрицательное число, нули слева, markup, неверный язык |

**Требования:** `REQ-LING-01` сохранять семантически управляемый поиск русских словоформ в keyword/RAG; `REQ-LING-02` поддерживать ограниченное расширение/сопоставление словоформ в FTS и явное качество при отсутствии морфологического словаря; `REQ-LING-03` сохранять многоязычную предварительную обработку TTS-текста и чисел. Реальные Rust alternatives исследованы по первичным источникам в [niche dependency report](../04-dependencies/core-niche-alternatives-and-parity-gates.md); окончательный выбор и corpus parity не выполнены.

**Не проверено:** качество русских лексем на реальной коллекции, benchmark словарей, результаты удалённых embedding моделей, конкретные corpus fixtures и Windows live TTS. Не утверждать эквивалентность стемминга полной морфологической парадигме.

## Pass 13: точные preprocessing gates и optional fallback

Дочитаны `utils/__init__.py` imports и функции 326–502. Heuristic считает первый token **Unicode character name** среди букв; это приближение script/language, а не языковая модель. Латиница сама не выбирает язык; Kana/Hangul/CJK имеют специальные пороги; generic majority threshold 0.6. Statistical langdetect — optional import с seed=0, минимум 20 chars, sample≤800; при недоступности/ошибке возвращается None. Тогда для чисел выбирается en. Корневая requirements строка для langdetect отсутствует; это implicit optional Core dependency.

При отсутствии num2words2 import fallback возвращает str(value), не произносительную форму. Весь process_text_to_voice после этого оставляет только Unicode letters/whitespace/SAFE_PUNCT: несозданные слова из цифр могут быть отфильтрованы. Нельзя обещать сохранность числительных в режиме без конвертера. Int conversion также теряет leading zeros; повторения одного token кешируются внутри вызова.

Первая markup substitution удаляет matched `<tag>…</tag>` вместе с внутренним содержимым; второй шаг удаляет оставшиеся tags. Это не HTML parser и не общее «убрать tags, оставить весь visible text». Non-string input приводится str; пустой итог → `...`. Для нового контракта важно решить desired text retention отдельно, а не механически перенести regex.

Прямых production imports третьестороннего `regex` при текущем source search не найдено; эти helpers используют stdlib re/unicodedata. Причина requirements regex подтверждается, в частности, installed tiktoken metadata. Не считать здесь использование Unicode-name heuristic доказательством зависимости от Python regex engine.

Добавлены проверенные alternatives для language ID (whatlang/lingua и свежий langdetect port) и Unicode helpers: [версии, источники, ограничения](../04-dependencies/core-niche-alternatives-and-parity-gates.md). Наличие native algorithm не подтверждает одинаковое произношение всех языков; нужны свои fixtures с mixed scripts, short Latin, leading zeros, unsupported language, отсутствующим converter и markup.
