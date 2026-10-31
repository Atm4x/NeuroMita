# Долговременная память

**Capability:** `CAP-MEM-001`. **Статус:** ACTIVE. **Источники:** `src/managers/memory_manager.py:39 MemoryManager`; mutation entrypoints Character structured/plain processing; HistoryController memory candidates/maintenance; DSL seed callsites 620/637. GUI mutation surface ещё исследуется.

## Назначение и данные

Персонаж хранит факты, приоритеты и ограниченные постоянно актуализируемые сводки. Память отличается от текста истории, summary диалога, session working state и объективного Unity snapshot. Внешний идентификатор N — eternal_id в character scope; SQLite id глобален. Их нельзя смешивать.

Memories: active=not deleted/not forgotten, forgotten исключены из постоянного prompt, но предназначены для RAG retrieval, deleted исключены из использования. Удаление и забывание имеют разные смыслы. Текущий комментарий о доступности forgotten в RAG ещё должен быть подтверждён search paths.

## Сценарии и выходы

Добавление/редактирование/удаление/слияние по ответу LLM или GUI; загрузка seed из шаблонов; automatic forgetting/TTL/dedup maintenance; prompt rendering; retrieval и entity tagging. Выход add обычно eternal_id, update/delete/merge bool; ошибки некоторых optional частей только логируются.

## Добавление, dedupe и идентификаторы

`add_memory:559` для fact при MEMORY_DEDUP_ENABLED ищет ближайший активный fact без islands/summary по Jaccard tokens. Нормализация lower, Latin/Cyrillic/digits, токены длиной≥3, лёгкий ru stem; это lexical similarity, не semantic embedding. Threshold default .8, clamp .5—1. При совпадении обновляет формулировку и повышает priority, возвращает существующий eternal_id.

skip_if_exists использует exact content, может вернуть ранее deleted/forgotten row в active. В этой ветви return — SQLite id, тогда как обычный add возвращает eternal_id. Это несогласованность контракта, особенно при нескольких character scopes. Seed RAG-only использует отдельный path и eternal_id.

Перед обычным insert вызывается capacity forgetting; новый eternal_id=MAX(character eternal_id)+1. Bound service operation lock сериализует вызовы одного персонажа внутри process, но unique constraint обычного eternal_id в просмотренной base schema не найден; межпроцессные writers ещё не рассмотрены. После commit embedding планируется в отдельный process-wide executor(max_workers=1). Неудача embedding не отменяет факт.

## Capacity, forgetting и TTL

Capacity default 50, минимум 1; islands не учитываются. Перед добавлением забывает до count<capacity, victims: low→normal→high, затем «ни разу не retrieved» перед retrieved (если enabled/access_count есть), затем oldest/id. Critical не забываются: capacity может быть превышена, это soft budget. Render также вызывает тот же room-making method, поэтому способен забыть один факт уже при count=capacity даже без нового insert. Требуемое поведение новой модели уточнить.

TTL optional: low default 30 days, normal/high default 0 (отключены), critical не входит в список. Date_created/last_accessed/access_weighted; последнее effective days=base×(1+log(1+access_count)×weight), default weight .5. Islands исключены. В access_weighted SQL UPDATE отсутствует character filter при записи selected eternal_ids — см. [подтверждённые дефекты/риски](../05-architecture/current-problems.md).

TTL вызывается в хвосте capacity forgetting, но early returns этого method могут до него не дойти. Есть explicit GUI callsite rag_memory_controller.py:456. Поэтому это не подтверждённый непрерывный TTL scheduler.

## Islands и seeds

Пять типов: relationship, opinion, preferences, commitments_conflicts, language. Для каждого один активный row per character, подкреплено partial UNIQUE index character_id/type и repair старых duplicates. Winner newest date, затем eternal_id/id; losers soft-deleted. Upsert обновляет row либо вставляет новый; unknown/empty отвергает. Islands не входят в normal count/chars budget, не embedding-ятся.

seed_island создаёт только если row этого type никогда не существовал, включая deleted. seed_rag_memory хранит fact с is_forgotten=1, чтобы indexed seed не попал в всегда включённый prompt; exact content dedupe может восстановить deleted, но оставляет forgotten. Без schema is_forgotten fallback — обычный add.

## Изменение, merge и maintenance

update/get content работают только для active/not-deleted, update меняет date и планирует embedding, кроме island. Delete работает и с forgotten; soft delete сохраняет строки. `merge_memories:1038` одной SQL transaction обновляет target/entities и soft-deletes source, затем recalculates budget/reembeds target. Отдельная structured memory_merge в Character использует update + ряд delete и не имеет той же атомарности.

Maintenance (`:1133`) без LLM: greedy lexical clusters по representative, keeper priority→newer→longer, merge остальных. Islands и summary исключены. Вызов от HistoryController раз в N replies, при занятости без накопления очереди. Это алгоритм эвристической дедупликации, не гарантия отсутствия потери различающихся фактов.

## Prompt и UI

`get_memory_message_blocks:1424` возвращает island block и active block отдельными system messages. Templates из Structural/*.txt могут менять представление. Facts priority/newness sorted; низ хвоста помечается RISK по heuristic, которая не полностью повторяет retrieval-aware forgetting. Chars>5000/10000 дают warning/critical подсказки модели, а не жёсткий лимит хранения. Info/examples добавляются trailer независимо от custom wrapper.

GUI CRUD, forgotten/deleted views, purge и restore ещё требуют полного прохода. Physical purge (`:1382`) optionally backup deleted в JSON, удаляет связанные embeddings/sentence_embeddings и затем rows. Backup error semantics ещё исследуются.

## Ownership, lifecycle и ошибки

Application resource manager владеет shared service, bound scopes — per character. Executors shutdown wait=False/cancel_futures; уже выполняющийся embedding может остаться. RAG initialization cached per scope; failure фиксируется unavailable для session в MemoryManager. Основной fact persistence не должен зависеть от embeddings readiness.

## Требования к новой реализации

Явные MemoryId scoped character и DB RowId; immutable states Active/Forgotten/Deleted либо эквивалентный строгий контракт. Транзакции semantic merge/reset, versioned derived embeddings, отдельный budget для islands. Dedupe/TTL/forgetting должны быть проверяемыми policies, не side effect чтения prompt. Сохранить все seed/user template сценарии, отдельно решить, какие текущие дефекты исправляются, а не воспроизводятся.

Rust alternatives пока не выбраны: lexical tokenization/стемминг относятся к core, embedding inference — к AI boundary; RAG целиком не приписывается одному процессу заранее.
