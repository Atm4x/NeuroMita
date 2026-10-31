# Pass 11: functional audit handoff, evidence and remaining gates

**Start wall-clock (UTC):** `2026-10-30 23:22:43`. **Finish wall-clock (UTC):** `2026-10-30 23:53:01 UTC`. **Scope:** Python Core snapshot in `CodeNow.zip`; functional reconstruction and parity requirements. No Rust target architecture, no GUI framework comparison, no edits to source/Legacy code, no intentional bug-hunting/fixing.

## Что добавлено именно в этом проходе

| Тема | Новый документ | Новый доказанный контракт / новое ограничение |
|---|---|---|
| DSL prompt pack execution | [main DSL](../01-functional/dsl-executable-prompt-contract.md) | source resolver/local pack, IF/SET/SEED/RUN, character/local side effects, static+volatile messages |
| Post-generation DSL | [Post-DSL](../01-functional/post-dsl-response-rules-and-debug-state.md) | regex/text/structured-field actions modify text and character state in ordering-dependent way |
| Desktop mini-games | [Chess and SeaBattle](../01-functional/minigame-chess-seabattle-state-and-character-reactions.md) | 2 distinct rule systems, child process/reaction queue, public vs hidden knowledge |
| Action-memory bridge | [requested actions + summary](../01-functional/structured-action-history-and-compression-bridge.md) | requested gameplay action kept in compressed LLM context, not Unity executed fact |
| Exact story triggers | [core-memory triggers](../01-functional/exact-core-memory-triggers-and-session-activation.md) | per-character temporary sticky story directive, separate from security authorization and vector RAG |
| External voice/capture | [microphone identity](../01-functional/microphone-physical-identity-backends-and-monitoring.md); [speech leases](../01-functional/asr-speech-arbitration-and-unity-speaking-leases.md) | stable physical endpoint ID vs PortAudio backend indices; simultaneous Unity/local speaking and microphone test gating |
| Internal messaging | [events and command/fact](../03-runtime/event-facts-command-routes-and-subscriber-lifetimes.md); [event callsite index](event-producer-consumer-callsite-index.md) | command accepted != action completed; 288 registry names, 202 direct emit/subscribe callsites, 117 with both kinds of static evidence |
| Unity ingress | [seven server request kinds](../03-runtime/unity-ingress-seven-actions-and-state-outcomes.md) | `hello/create_task/get_task_status/get_settings/get_music_beats/speech_state/asr_ptt_state`, role/ownership and async outcomes |
| GUI async behavior | [freshness/exclusive/coalescing](../02-ui/intent-workloads-and-visible-state-consistency.md); [52 direct callsites](gui-async-operation-callsite-index.md) | no stale selected photo, no parallel duplicate operation per key, no refresh-per-event overwork; only source reachability candidate |
| Headless | [runtime surface](../03-runtime/headless-core-functional-surface-and-readiness.md) | actual no-Qt Core/Unity listener vs GUI-only, readiness snapshot, shutdown, missing interactive Telegram auth |
| Static vs active | [standalone and unresolved](standalone-and-unproven-runtime-reachability.md) | avoid importing command parser, remote DSL files, experimental GameMaster scheduler or standalone web/VTT into obligatory Core without direct proof |
| Installables validation | [31 static IDs and dynamic RAG](../06-design-input/installables-component-by-component-parity-matrix.md) | per-component identity/status/plan/execute/activate gate, explicitly `0/31` live installs during pass |

## Точечная offline-проверка — НЕ общий test suite

| Запуск | Итог | Доказательство и ограничения |
|---|---|---|
| `test_mini_game_public_context.py`, `test_microphone_selection_service.py`, `test_microphone_monitor.py`, `test_dsl_random.py` | 50 passed, 1 failed, 2 subtests passed | SeaBattle expectation for player's shot wording differs from current output; old code not changed |
| `test_event_bus.py`, `test_runtime_features.py`, `test_asr_game_capture.py`, `test_live_dialogue_echo_identity.py` | 54 passed | offline event/capture mock scenarios |
| `test_speaking_window.py`, `test_asr_ptt.py`, `test_asr_session_routing.py` | 88 passed, 1 failed | one Qt-dependent test cannot import `PyQt6`, not a voice contract proof |
| `test_core_memory_triggers.py`, `test_safe_eval.py` | 21 passed | deterministic story triggers + evaluator limits |
| `test_chat_api.py` | 6 passed | semantic entrypoint through injected `ChatService` mock |
| `test_headless_runtime.py` | 6 passed | CLI options, no Qt import, fake server context and snapshot; no actual listener/Windows host |
| `test_working_state_and_action_memory.py`, `test_history_epoch_guard.py` | 19 passed | action-memory summary and stale-result guards, offline fixtures |
| `test_seabattle_lifecycle_reactions.py` | 8 passed | SeaBattle gameplay events/reaction ownership, offline mocks |
| `test_chess_move_reactions.py` | collection blocked | `ModuleNotFoundError: chess` in the auditing environment; cannot mark Chess engine behavior tested |
| `test_app_paths_prompts.py`, `test_prompt_linter.py` | 17 passed | prompt root resolution and prompt contract/lint checks, no GUI |
| `test_release_prompt_contracts.py` | collection blocked | `PyQt6` not installed in auditing environment |
| `test_get_music_beats_action.py` | 2 passed | mock request/action response of Unity beat transport, not real waveform/Beat AI |
| `test_game_link_target.py` | collection blocked | `ModuleNotFoundError: qtawesome` from game settings UI import, distinct from missing PyQt6 |
| `test_prompt_system_state.py` | 37 passed, 1 failed | expected `extra/Prompts/Crazy/Default/Context/examples.script` absent in local source snapshot, so prompt pack fixture test incomplete; no source edit |
| `test_unity_dialogue_routing_boundary.py` | collection blocked | Qt not installed; cannot mark as passed or failed behavioral test |

Summed counts over **separate invocations**: `308 passed`, `3 failed`, additional `2 subtests passed`, four separate collection-blocked modules. These are **not 308 distinct implemented requirements**; fixtures may share pathways and no provider network, Unity client, CUDA GPU, AI weight download, Qt UI, Windows hardware or full install E2E was performed. A `pytest` return code other than 0 means selected run was not green; do not round that into an overall pass.

## Source/read-only integrity

- `987/987` `.py` under `CodeNow.zip/src` compared with extracted working source by CRC32: **0 missing/changed**. Full repository content non-Python not compared in this statement.
- Previous artifact had **148 Markdown files**; all previous file paths retained in the working documentation set. New content is only under `audit-docs/docs` for the deliverable.
- Static callsite indexes use AST to find literal named calls; there are dynamic/conditional registrations that may escape this method. No inflated active status.
- All `REQ` additions were linked to source-backed specification documents; where behavior remains uncertain, status is `CONDITIONAL/UNRESOLVED` and a parity fixture is recorded.

## Gate status / next action

**Unchanged 13 PRIMARY / 7 PARTIAL** out of 20 fixed top-level research areas, not overall completion of the entire audit. Partial areas: 05 History, 06 RAG/Graph, 14 GUI, 16 Installables, 17 External, 19 Dependencies, 20 Traceability. See [coverage ledger](audit-coverage-ledger.md) for exact outstanding criteria.

**Highest value next pass:** explicitly trace modal GUI actions and dynamic event registrations to actual registered runtime consumers, reconcile remaining history/RAG rare operations, confirm optional external/network branches, build real Windows/hardware/AI install-readiness fixtures, complete source→requirement→validation closure. Keep investigating functionality rather than errors in legacy implementation.
