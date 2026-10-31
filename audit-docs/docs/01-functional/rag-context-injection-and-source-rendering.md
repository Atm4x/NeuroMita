# RAG → LLM: условия обращения к памяти, формат контекста и порядок сообщений

**Назначение:** связать функцию retrieval с наблюдаемой генерацией: когда поиск запускается, какие source-specific записи формируются и как Core передаёт их в `PromptController`. **Статус:** `ACTIVE/CONDITIONAL`, зависит от выбранного персонажа, политики события и RAG settings. Источник — локальный Python snapshot, без live LLM/embedding tests.

## CAP-RAG-PROMPT-001 — eligibility automatic RAG на конкретном запросе

**Источник:** `src/controllers/model_controller.py:1360-1405,1666-1690,2001-2025`.

При генерации обычного персонажа `ModelController` создаёт отдельное поле `rag_context` в `PromptBuildRequest`. Он вычисляется **до** окончательного создания системных и пользовательских сообщений, но **только**, если персонаж не `GameMaster`, установлен `RAG_ENABLED` и `policy.react_level != 1`. Уровень реакции и GameMaster здесь функциональные ограничения потребности в справочном контексте, а не DB-свойство. Запрос поиска берётся из `user_input` при его наличии, иначе из `system_input`; если обе строки пусты, поиск не выполняется. Перед выполнением и после него обрабатывается request-level cancellation в общем generation lifecycle.

`RAG_MAX_RESULTS` (UI default в другом реестре) и `RAG_SIM_THRESHOLD` передаются `RAGManager.for_character(char_id).search_relevant`. Поэтому поисковый корпус связан с **владельцем текущей генерации**, а не с глобально выбранным в GUI персонажем. Отдельный `memory_search` tool может вызвать тот же retrieval с `config_overrides`, даже если auto-RAG отключён; его контракт изложен в [tools-and-web.md](tools-and-web.md) и [ranking](rag-query-fusion-reranking-and-result-contracts.md).

Независимо от RAG могут отработать точные core-memory triggers по тексту пользователя — это другой способ добавления контекста, не кандидат vector search. Его нельзя слить с RAG flags или индексом.

## CAP-RAG-PROMPT-002 — rendering per-source результатов

**Источник:** `src/controllers/model_controller.py:1996-2120`.

Возвращённые `Candidate` dictionaries распределяются по `source='memory'`, `'history'`, `'graph'`. Для первых двух используются **настраиваемые в наборе промптов шаблоны** `Structural/rag_memory_item.txt`, `Structural/rag_history_item.txt`, `Structural/rag_wrapper.txt` с fallback на встроенные шаблоны. RAG output не является raw JSON, как tool result: это готовый блок текстового системного контекста.

| Источник | Наблюдаемый смысл форматирования | Функциональное происхождение |
|---|---|---|
| Memory | `score`, стабильный N:id, `type`, `priority`, creation date, clipped content | возможность ссылаться на память и забывание, а не «какая-то похожая фраза» |
| History | `score`, дата, `speaker` и `target` (формат actor→target), clipped message | кто именно говорил и к кому обращался в старой беседе |
| Graph | triple content и score; отдельный `graph_block`/`entity_knowledge` при необходимости | отношение сущностей, не смешивать с цитатой сообщения |

Лимит длины одного item `RAG_CLIP_MAX_CHARS` обрезает *контент записи* до шаблонизации. Если выбранный template некорректен (KeyError/IndexError/ValueError для item), формируется встроенная строка; если wrapper не содержит `{graph_block}`, результаты graph добавляются как дополнительный `<entity_knowledge>` блок. При наличии забытых фактов выводится агрегированный `Forgotten pool: N memories`, но сами факты не обязаны попадать в выдачу стандартного active search. Rendering не равен полной persist-сериализации memory; это проекция для одного запроса.

## CAP-RAG-PROMPT-003 — отдельное `system` сообщение и приоритет свежих событий

**Источник:** `src/controllers/prompt_controller.py:938-961,1080-1081,1156-1185,1216-1225`.

`PromptController` собирает prompt из персонажа, сохранённой истории/памяти, текущего игрового состояния, локального контекста и пользовательского запроса. `rag_context` вставляется **отдельным сообщением с ролью `system`** после обычных volatile/system/memory блоков (и `core_memory_context` ранее), но **до** более свежих Unity динамических capabilities/world-state/events и `[Current State]/[System State]`. Это намеренное различие **справочной информации о прошлом** и **актуальной инструкции/состояния игрового мира**. По `ModelController.process_rag` исходный `system_input` не модифицируется и не заменяется retrieval-блоком.

При отсутствии результатов, ошибки поиска или запрете автоматической подстановки `rag_context` остаётся пустой строкой и отдельное сообщение не создаётся. Это штатное продолжение генерации, а не обязательная ошибка LLM. Хотя нынешний шаблон использует system role, не предрешается точное устройство Rust prompt builder; важна функциональная последовательность и provenance.

## Требования к новой реализации и проверки

- `REQ-RAG-PROMPT-001`: automatic injection зависит от выбранного персонажа и политики реакций, но explicit search/tool имеет самостоятельное условие доступности.
- `REQ-RAG-PROMPT-002`: renderer различает memory/history/graph provenance, score/identity/actors, пользовательские prompt templates и clipping.
- `REQ-RAG-PROMPT-003`: RAG-контекст является справочным message block; исходная актуальная инструкция и dynamic Unity state сохраняют собственные границы и порядок.
- `REQ-RAG-PROMPT-004`: отсутствие результатов или временная недоступность retrieval не запрещает обычный LLM turn; отдельные core-memory triggers работают независимо.

**Acceptance fixtures:** обычное player message vs событие system-only; `GameMaster`; `react_level=1`; auto off/tool on; one memory/history/graph/empty result; кастомный wrapper c/без graph placeholder; actor metadata; длинная запись; overlapping Unity recent event и RAG context. **Не выполнялось:** end-to-end provider prompts, реальные generative outputs и UI показ контекста. [Общий RAG](rag.md) · [Индентичность корпусов](rag-storage-retrieval-and-indexing-modes.md) · [Rank](rag-query-fusion-reranking-and-result-contracts.md).
