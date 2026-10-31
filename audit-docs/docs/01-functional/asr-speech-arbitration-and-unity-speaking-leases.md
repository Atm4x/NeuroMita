# Speech arbitration: local TTS, Unity speech leases and ASR capture

**Capability:** suppress the app's own spoken replies entering microphone recognition while preserving independent dialogue actors and timely recovery. **Status:** `CONDITIONAL` on active microphone and selected suppression setting; lease tracking itself is an active runtime route when speech controller exists. **Scope:** observable microphone/Unity/local audio behavior, not a proposal to reuse the Python implementation.

## Why this is a separate user feature

When Mita speaks through desktop playback or through the connected Unity game, microphone capture may otherwise transcribe the spoken answer as a new player utterance. The user may configure `MIC_MUTE_WHILE_SPEAKING`. When enabled, the capture gate must consider all concurrent speaking actors, game clients and local audio, not merely a single global boolean. The feature does **not** perform echo cancellation or alter the audio waveform; it controls whether ASR input/admission is currently permitted.

## Sources and actual flow

- Local playback: `src/controllers/audio_controller.py:60-73` publishes `Events.Audio.MITA_SPEAKING_WINDOW` with `active=True/False` when an output phase begins/ends. The local key has a stable default source `local`.
- Unity: `src/game_connections/handlers/actions/speech_state.py:10-55` maps protocol `speech_state` with `active`, `character`, optional `speech_id`/`id`, optional `duration_sec`, sender `ctx.client_id`. Strings such as `"false"`, `"0"` are parsed as false, not Python truthy strings. Events are **facts from actual game playback**, not a prediction solely from generated WAV duration.
- `src/controllers/speech_controller.py:185,842-951` subscribes to the speaking and client-disconnect events. It updates `SpeakingWindow`, then recomputes the ASR input gate; microphone tests temporarily disable ASR input independently.
- `src/managers/speaking_window.py:22-141` owns lease keys `(source, speech_id)`; for older game clients without an ID, `character` provides a fallback key. `active=False` retires the matching lease, not all currently speaking actors.

## Lease-state contract

| Input | Interpretation | Source |
|---|---|---|
| `active=True`, key not previously closed | Create/refresh a speech lease with deadline | `speaking_window.py:50-71` |
| Positive finite `duration_sec` | Deadline = min(duration + 5 seconds, 180 seconds) | `:111-125` |
| Unknown/invalid duration | Default 60-second lease, protecting against lost end events | `:34-38,111-125` |
| `active=False` for key | Remove that lease; preserve other leases; add 0.4s trailing mute window | `:73-79,126-129` |
| Unity client disconnect | Remove all leases for that client, remember closed-source identity (up to 64) to reject late starts | `:81-92,131-139`; `speech_controller.py:944-949` |
| Deadline elapsed | Expire lease; continued ASR block depends on other leases or trailing window | `speaking_window.py:94-110` |
| `MIC_MUTE_WHILE_SPEAKING=false` | Active leases can still be recorded but are not passed as blocked-until to input gate | `speech_controller.py:865-882` |

This clock is monotonic rather than wall time. Multiple game clients and characters can speak concurrently; one client disconnect cannot release unrelated voices. A trailing window accommodates playback and delayed VAD result emission.

## Input-gate interaction and acknowledgement

`SpeechController._sync_input_gate` (`src/controllers/speech_controller.py:864-901`) configures global ASR gate using `ASR_INPUT_MODE` (`radio` or PTT), `MIC_ACTIVE`, active microphone-test sessions and speaking lease `blocked_until` (if muting enabled). Reconfiguration invalidates game-owned pending transcripts and may send `Server.SEND_ASR_CAPTURE_STATE` with `session_cancelled`, generation and reason.

The game-specific PTT/radio request handler (`:904-943`) re-checks player-turn ownership **after event delivery**. Wrong owner gets `input_not_owned`; accepted/active states are acknowledged with command generation and a reason such as `capture_not_ready`, `microphone_test`, `microphone_disabled`, `speech_blocked`, `capture_requires_release`, or `capture_busy`. A speaking lease is thus only one of several independent admission criteria.

`src/services/microphone_monitor.py:127-213` emits `MICROPHONE_TEST_CHANGED(active, session_id)` while user listens to a preview, and `_on_microphone_test_changed` manages a set of those sessions (`speech_controller.py:895-905`). Recording/ASR is inhibited during microphone testing independently of whether Mita is speaking.

## Capabilities and minimum new-system requirements

- `CAP-SPEECH-ARBITER-001` (`CONDITIONAL`): prevent self-voice capture during configured speaking periods, local and Unity. `REQ-SPEECH-ARBITER-001`: admission derives from actual concurrent playback sources and user option, not just presence of a generated audio file.
- `CAP-SPEECH-ARBITER-002` (`CONDITIONAL`): coordinate multiple simultaneous game speakers/clients. `REQ-SPEECH-ARBITER-002`: retiring one utterance/client must not end another active speaking lease; stale disconnected-client events must not lock microphone.
- `CAP-SPEECH-ARBITER-003` (`ACTIVE/CONDITIONAL`): separate player-turn ownership, PTT/radio state, microphone testing and speaking suppression. `REQ-SPEECH-ARBITER-003`: the game receives a reasoned acknowledgement whenever an input command is rejected or invalidated.
- `CAP-SPEECH-ARBITER-004` (`ACTIVE`): fail-safe timed release when no end-of-speech event arrives. `REQ-SPEECH-ARBITER-004`: bound an orphaned speaking lease and retain a short tail so ASR does not wake during playback decay.

## Proposed validation cases (not executed here)

1. Local playback start/end, muted and unmuted; verify radio/PTT handling and UI indicator.
2. Two simultaneous game utterances from different actors; end one first, the other still holds gate.
3. Disconnect one game client while another speaks; drop a late `active=True` from disconnected client.
4. Omit end event; validate deadline expiration. Reject NaN duration and textual `"false"`.
5. Start microphone monitor while ASR/game capture is active; verify explicit cancellation reason and restoration after test.
6. Attempt game ASR activation by an actor that does not own the current player turn.

**Not verified:** Unity-client availability of this protocol across deployed revisions, physical microphone echo, device latency and exact user perception under simultaneous audio. Only static source paths examined. **Related:** [ASR capture](speech-input.md), [microphone selection](microphone-physical-identity-backends-and-monitoring.md), [Unity admission](unity-dialogue-admission.md), [voice playback](voice-output.md).
