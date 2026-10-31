# Unity ingress: seven registered Python actions and their observable outcomes

**Scope:** the Python Core's active game-link request registry, deliberately not a full audit of Unity animations/executors. **Status:** seven source-registered handlers (`ACTIVE` routes at an initialized server, individual features `CONDITIONAL`). This complements [transport](unity-transport.md), [auto-dialogue](../01-functional/unity-auto-dialogue.md), [speech leases](../01-functional/asr-speech-arbitration-and-unity-speaking-leases.md) and [Beat analysis](../01-functional/music-beats.md).

## Entry and actor ownership

`src/game_connections/handlers/__init__.py:1-25` registers exactly seven action names in `ActionRegistry`: `create_task`, `get_task_status`, `get_settings`, `get_music_beats`, `speech_state`, `asr_ptt_state`, `hello`. `src/game_connections/server.py:28-145,173-297` owns a loopback TCP listener (default `127.0.0.1:12345`), accepts newline-delimited UTF-8 JSON, checks a per-frame bound (default 8 MiB, env configurable), creates per-connection IDs with a monotonic sequence and dispatches by `action`.

The server distinguishes connections by declared `client_role`; this is not user authentication. An explicit `game` connection can own player ASR input. Anonymous legacy compatibility is separately constrained. Role and ownership matter to the `asr_ptt_state` route, but arbitrary controller/test TCP clients must not acquire the player's recognized utterances just because they connected last.

## Contract inventory

| Registered action | Expected input | Synchronous reply / asynchronous effect | Feature status and evidence |
|---|---|---|---|
| `hello` | Optional `client_role` | `hello_ack` with `protocol_version`, `session_id`, resolved `client_role`, `owns_player_input` | ACTIVE, `handlers/actions/hello.py:8-27`, `server.py:504-570` |
| `get_settings` | No special parameters | `loaded_settings` envelope from server's injected settings provider | ACTIVE once provider registered; `handlers/actions/get_settings.py:9-17`, `server.py:87-110` |
| `get_task_status` | `task_uid` (required) | Current TaskService task dictionary; for successful result enrich with voiceover path, Telegram connectivity and bounded GM settings | ACTIVE/CONDITIONAL, `handlers/actions/get_task_status.py:11-52` |
| `create_task` | Event `type`, selected actor/character/sender, `data`, `context`, participants, `req_id`, optional origin message and dialogue metadata | Creates/queues generation task, task accepted/rejected and later task_update; special handling for react, game master, media snapshots, idle, television | ACTIVE/CONDITIONAL, `handlers/actions/create_task.py:12-~600` |
| `get_music_beats` | `audio_path` required, optional `track_name`, `request_id`, `stream`, `chunk_seconds`, `min_confidence` | `music_beats_job_started`, then streaming `music_beats_chunk` and terminal `music_beats_ready`, or nonstream `music_beats_ready` with full beats; errors send `music_beats_error` | CONDITIONAL `BEAT_SYNC_ENABLED`; `handlers/actions/get_music_beats.py:16-183` |
| `speech_state` | `active`, `character`, optional `speech_id`/`id`, `duration_sec` | No standalone response payload; emits actual playback fact to the microphone speaking lease arbiter | CONDITIONAL audio/ASR; `handlers/actions/speech_state.py:10-55` |
| `asr_ptt_state` | `active` strictly bool, `generation` unsigned bounded integer, `session_id` exact connection identity, `cancelled` bool | Emits owned `Speech.ASR_PTT_STATE`; separate `asr_capture_state` acknowledgement from speech controller. Invalid owner/data receives explicit error | CONDITIONAL microphone/input turn ownership; `handlers/actions/asr_ptt_state.py:5-24`, `speech_controller.py:904-943` |

### Important distinctions

- `get_task_status` observes an existing task, it does **not** itself generate another LLM reply. On success it adds GM configuration and Telegram state, but these are not universal fields of every task result (`get_task_status.py:23-52`). `GM_READ` is false for hidden moderator outcome; hidden game-master instructions are not visible chat messages.
- `get_music_beats` has two observably different delivery modes. `stream=True` sends per-chunk beats + terminal summary (duration, count, method and BPM estimate), while `stream=False` returns all beats within one terminal body. It sets `auto_install=False`; accepting analysis requests is **not** the same as silently installing model dependencies. Feature disabled or empty audio path produces `music_beats_error` (`get_music_beats.py:45-72,81-164`).
- `speech_state` reports **playback**, `asr_ptt_state` requests **player capture**, `send_asr_text` represents **recognized player speech**, and `task_update` represents **generation**. Treating all four as a single audio message stream would lose real-world semantics.
- `create_task` handles many user/Unity event types inside one registered route. `reaction_events` is bounded to 24 nonempty events, normalizes type/count/duration, and constructs an aggregated reaction prompt (`create_task.py:53-147`). It keeps `player source`, `character identity`, actor identity and `origin_message_id` conceptually separate; see [identity](../01-functional/dialogue-actor-and-message-identity-contracts.md).
- Initial game-settings sync and ad hoc `get_settings` use a **projection**, not direct unrestricted read of every Core setting. No LLM credentials or unrelated GUI state should be assumed to cross by default. Certain GM and beat fields are normalized/overridden in the projection (`unity-media-transfer.md`).

## Capability → requirement → future test

| Capability | Required behavior | Validation outline |
|---|---|---|
| `CAP-UNITY-INGRESS-001` — session handshake and input authority | `REQ-UNITY-INGRESS-001`: player input belongs only to an eligible game actor/session; reconnect revokes stale identity | Two clients, hello roles, anonymous legacy case, reconnect, rejected PTT |
| `CAP-UNITY-INGRESS-002` — task creation/observation | `REQ-UNITY-INGRESS-002`: separate requested generation from task status/progress and actual executed game commands; preserve request/message correlation | answer/react/idle/game_master vs unsupported event, request ID, task_status success/failure |
| `CAP-UNITY-INGRESS-003` — read-only game settings projection | `REQ-UNITY-INGRESS-003`: expose only relevant normalized game settings, with an observable revision/lifecycle | initial connect, get_settings, setting edit, conditional projection |
| `CAP-UNITY-INGRESS-004` — BeatSync stream and nonstream | `REQ-UNITY-INGRESS-004`: both result shapes, progress/chunks/error, same request identity and no unapproved model installation | disabled, missing path, cached result, streaming chunks, worker failure |
| `CAP-UNITY-INGRESS-005` — independent playback/capture traffic | `REQ-UNITY-INGRESS-005`: speech playback leases and capture commands remain independent and ownership-aware | concurrent speaking, PTT denied to non-owner, explicit ack/error |

## Validation and limits

This is a source-backed **protocol semantics inventory**, not live network conformance. No Unity build was launched and no actual game event performed. Compatibility with a deployed Unity revision, exact framing of every downstream task response and long-running remote handling need integration fixtures. The existing direct `src/game_connections` handler names are *evidence of today's ingress*, not instructions to reproduce the same seven classes or RPC architecture in Rust.
