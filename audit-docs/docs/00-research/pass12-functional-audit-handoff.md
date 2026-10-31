# Pass 12 — функциональный аудит: handoff для продолжения

**Начало:** `2026-10-30 23:59:24 UTC`. **Обязательная контрольная отметка:** `2026-10-31 00:29:24 UTC` (30 минут wall-clock). Точное фактическое окончание будет добавлено по системным UTC часам после контрольной отметки в `research-progress.md`.

**Вход:** локальный `CodeNow.zip` с источниками под `src/`; markdown из Pass 11 (164 документа) под `audit-docs/docs`. **Итог:** все документы в одной `audit-docs/docs`, исходный Python/Unity code, legacy/obsolete не менялись. Новую Rust-архитектуру и сравнительный GUI-stack не проектировать до окончания functional audit.

## 16 новых source-grounded документов и отдельный handoff

1. [Реальная достижимость окон](../02-ui/dialog-class-reachability-and-action-outcomes.md) — `MessageProcessingDialog` как зарегистрированная реализация `protocol_pipeline`, отдельно неподтверждённый `ProtocolPipelineDialog`, случаи скрытия/reopen.
2. [Raw string events и history paging](raw-string-event-reachability-and-ui-bridges.md) — 28 raw event names в исследованной подвыборке исходников; восемь с literal сторонами отправка/подписка.
3. [RAG/Memory settings UI: 100 descriptors, 99 unique keys](../02-ui/memory-rag-registered-settings-source-index.md) — 15 builder funcs, defaults, conditional visibility.
4. [Graph ingestion](../01-functional/graph-ingestion-manual-realtime-inline-and-provenance.md) — inline structured/legacy, realtime utility, manual batch; provenance state and postprocessing.
5. [Внешние executables и native loader](../04-dependencies/external-executables-and-native-loader-functional-boundaries.md) — FFmpeg/7z/Windows interfaces vs Python AI worker ownership.
6. [Native picker/short dialogs](../02-ui/native-dialogs-and-file-input-output-workflows.md) — 16 file+directory dialogs и 8 short input dialog calls (excluding tests).
7. [Семантика подтверждений](../02-ui/confirmation-and-destructive-intent-semantic-matrix.md) — 29 user confirmations with different actual scopes.
8. [RAG presets](../02-ui/rag-preset-complete-user-journey-and-model-readiness.md) — four built-ins, custom snapshots, Apply vs preview vs missing model.
9. [Qt callback index](gui-signal-registration-callsite-index.md) — 517 static `.connect` calls across 75 source files, not 517 E2E-verified actions.
10. [RAG settings consumers](rag-settings-direct-consumer-evidence-index.md) — 96 literal references outside builder for 99 unique keys (3 special cases unresolved).
11. [RAG deterministic retrieval](../01-functional/rag-deterministic-golden-surface-and-result-types.md) — fake embedding, history/memory source identity, score features, normalized result contracts.
12. [RAG readiness state machine](../01-functional/rag-model-runtime-readiness-and-worker-generation.md) — required model targets, separate embedding/reranker, warming, worker epoch and stale response.
13. [Test suite static map](test-suite-static-validation-map.md) — 250 `utils/Testing/test_*.py` files, 2177 AST `test_*` function definitions, mapped to 12 heuristic domains. Does not imply 2177 passing tests.
14. [History UI projection](../01-functional/history-ui-projection-actor-identity-and-paging.md) — role vs real actor, speaker/target, TV observation, raw offset, request/character identity.

15. [Динамические loader registries и Core/AI scopes](../04-dependencies/dynamic-import-registries-and-runtime-capability-contracts.md) — provider/ASR/tools/installables/GUI/worker import paths и реальные error semantics.

16. [Индекс 24 production dynamic import/WinDLL/CDLL callsites](production-dynamic-import-callsite-index.md) — точный AST location, выражение аргумента и признак conditional import.

## Addressed offline validation Pass 12

| Test group (separate process invocations) | Outcome | What this shows |
|---|---:|---|
| `test_runtime_features`, `test_settings_registry`, `test_rag_preset_view_model` | 20 passed | Typed runtime settings, preset UI viewmodel |
| `test_rag_preset_model_downloads`, `test_rag_readiness`, `test_installable_catalog_loaders` | 16 passed | RAG model plan/readiness and lazy loader |
| `test_installable_catalog_service`, `test_installable_controller`, `test_rag_model_catalog` | 35 passed + 6 subtests | Catalog, operation admission, RAG model metadata |
| `test_rag_units_golden`, `test_rag_search_golden` | 18 passed + 8 subtests | Stable result identity, ordering, fake embedding fixture |
| `test_rag_restart_state`, `test_rag_runtime_context`, `test_rag_reindex_batch_size` | 14 passed | Restart model readiness, runtime context, reindex batches |
| `test_history_ui_projector_multi_mita`, `test_dialogue_sender_identity`, `test_history_epoch_guard` | 22 passed | Projection, actor identity and history reset epoch guards |
| `test_runtime_ipc`, `test_tv_observation` | 13 passed, 4 failed | Local TCP/JSON and TV content; 1 incomplete controller fixture, 3 unavailable Qt/qtawesome dependencies; no fixes |
| `test_tool_manager_lazy`, `test_ai_contour_boundaries`, `test_declarative_model_profiles` | 19 passed | Loader/AI contour/profile contracts |
| **TOTAL successful (nonoverlapping invocations)** | **157 passed + 14 subtests** | 4 failed in other invocation; **not full suite** |

**Дополнительно:** попытка запуска `test_telegram_credentials_gate.py` и `test_remote_voice_delivery.py` прервана на collection: локально отсутствуют `telethon` и `pygame`; ни один из этих двух модулей не засчитывается как выполненный. Отказы четырех проверок в другом invocation фиксируются только как границы свидетельства, без расследования или исправления старого Python.

**Важно:** тестовая выборка *не* подтверждает реальный AI worker inference, Windows hardware, Unity client или Qt GUI E2E. В `CodeNow.zip` обнаружено 251 `test_*.py` по всей `src`, но 250 внутри `src/utils/Testing`; `src/controllers/gui/api_settings/test_mixin.py` не классифицируется как самостоятельный test suite. AST-test definitions 2177 — статические узлы, а не исполненные тесты.

## Прогресс-bar с фиксированной единицей

`PRIMARY 13/20` — [█████████████░░░░░░░] **65% первичных функциональных контрактов**, `PARTIAL 7/20`. Не измеряет процент всей работы. 16 новых спецификаций повысили *глубину*, не закрыли все E2E и remaining actions. Нельзя искусственно поднять status по числу docs/tests.

| PARTIAL | Confirmed by Pass 12 | What remains |
|---|---|---|
| 05 History | captured character paging, raw/visible role identity and epoch guards | actual GUI multi-character race and cross-storage migration fixtures |
| 06 RAG/Graph | 99 keys, four graph-ingestion paths, four presets, golden result format, model runtime epoch/readiness | real models + graph/FTS mixed queries and full provenance E2E |
| 14 GUI | dialog reachability, 517 signal callsites, confirmation/picker semantics | registered handler to side-effect for every action and live Qt E2E |
| 16 Installer | catalog/readiness/model plan tests; 31 static IDs source audited in earlier pass | per-component actual status/install/repair, Windows model download E2E |
| 17 Integrations | native executables/worker boundary only | Telegram/network/remote provider/Unity live consumer |
| 19 Dependencies | Windows/system/AI executable boundaries | transitive wheels/natives DLL graph, Windows packaging |
| 20 Traceability | source/test inventory, active capability and new requirements rows | exhaustive action→capability→requirement→test and proven runtime registration |

## Starting point for Pass 13

**Не возвращаться к bug hunting.** Последовательно отобрать одну открыту ветвь, найти entrypoint/регистрацию и follow source to outcome. Рекомендуемое следующее: (a) RAG/Graph источник→вектор→пометка provenance→prompt при смешанных моделях; (b) на стороне GUI закрыть 20+ dialogs через действие→handler→observable Core side effect, а не только `.connect`; (c) сопоставить installable manifests с реальными `status/plan/initialize/repair` по всем 31 ID; (d) транзитивные runtime wheel/native bindings и обязательные не-AI зависимости Rust Core. Документировать evidence и уровень уверенности; не заявлять live E2E там, где есть только AST или mock.

**Сохранность:** перед финальной упаковкой пересчитать и проверить все относительные MD-ссылки, `164/164` документов Pass 11, отсутствие исходников в ZIP, CRC-совпадение `1024/1024` всех `.py` (`987` из `src/` + остальные scripts) против `CodeNow.zip`. Финальная проверка и отметка времени сохраняются в `research-progress.md`.
