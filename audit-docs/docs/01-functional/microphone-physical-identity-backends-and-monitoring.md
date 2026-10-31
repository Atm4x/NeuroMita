# Microphone identity, compatible backends and live monitor

**Status:** `CONDITIONAL` on supported sound capture backend and actual devices; user-visible Settings/ASR capability in full Core. **Sources:** `src/domain/audio_input.py`; `src/services/microphone_selection.py`; `src/infrastructure/audio/portaudio_catalog.py`; `src/infrastructure/audio/windows_endpoint_identity.py`; `src/migrations/settings/microphone_endpoint_id.py`; `src/services/microphone_monitor.py`; `src/handlers/asr_audio_devices.py`. All line references below refer to the CodeNow source snapshot, not a runtime hardware experiment.

## User intention and independent functional capabilities

A user must be able to see actual microphones, select a physical input, switch optional capture backend if several representations exist, reconnect a device and retain the intended physical selection where possible. A separate **Test microphone** operation lets a user hear the input through their default output while showing current capture level. Neither selecting a microphone nor monitoring it is an ASR transcription request; a working microphone does not mean a speech-recognition model is installed.

### Model and storage

`src/domain/audio_input.py:5-48` defines the actual value semantics:

- `MicrophoneSelection(uid, index, name, backend)` contains a stable optional Windows endpoint UID, ephemeral PortAudio index, name and optional host API choice.
- `ASRInputDevice(index,name,host_api,default_sample_rate,display_name,uid)` represents one backend-specific device; `selection` carries a stable UID when available.
- `AudioInputCatalog` separates **displayable physical devices** (`devices`) from all backend representations (`representations`), compatible choices, their mapping (`preferred_indices`), Windows default index and endpoint identity confidence (`AVAILABLE/PARTIAL/UNAVAILABLE/UNSUPPORTED`).
- The preferences owner is `MicrophoneSelectionService`; it performs lazy migration, refresh and current-device resolution (`src/services/microphone_selection.py:53-125`). It does not own the ASR model or force model initialization.

### Discovery and reconciliation

`src/infrastructure/audio/portaudio_catalog.py:36-336` enumerates PortAudio input devices. There may be several indices for the **same physical microphone** (WASAPI, DirectSound, MME). Current behavior:

1. Filter to `max_input_channels > 0`, collect host API names, optional physical endpoint UID (Windows WASAPI bridge).
2. Ignore Windows aliases for default input; filter WDM-KS because blocking capture is unsupported by this app.
3. Test mono float32 input settings at ASR `16 kHz`, or the device's native/default rate; actual capture can resample later. Unsupported capture representations are not offered.
4. Group equivalent representations by UID when available; without it, use normalized name + occurrence and a backend preference ordering **WASAPI > DirectSound > MME > other**.
5. Resolve MME's truncated 31 UTF-16-code-unit product names only when an unambiguous full name can be recovered. Preserve original representations so an advanced backend choice remains possible.

The catalog refresh may reinitialize the Python `sounddevice` PortAudio instance only when no active audio stream is using it. `portaudio_stream_scope()` tracks active scopes; a refresh during capture does not force the restart. This is observable hotplug policy, not a requirement to preserve private Python symbols.

`src/infrastructure/audio/windows_endpoint_identity.py:13-108` reads device IDs through the PortAudio WASAPI bridge + Windows COM. The stable ID is *optional*; without it the system uses a conservative legacy name/index policy, not guaranteed physical matching across all changes.

### Selecting and migrating

`resolve_microphone()` (`src/services/microphone_selection.py:20-50`): with a UID, match that physical endpoint and optional explicit backend; if identity information is missing, the caller gets `MicrophoneIdentityUnavailable` instead of silently switching to an unrelated device. Without UID, use legacy name/index/default resolution.

`src/migrations/settings/microphone_endpoint_id.py:15-72`: migration from the old index/name preference happens **only** when endpoint discovery is available, selection is still unchanged, and the physical candidate has an unambiguous UID. The previous backend preference is retained. This is not a bulk migration at package installation time; it is completed through catalog reads when conditions permit.

`MicrophoneSelectionService.resolve_current()` writes the resolved representation and backend hint back into preferences. A backend can be manually selected among `microphone_backends()` compatible representations; unavailable backend becomes a distinct error, not a silently substituted device.

## Microphone monitoring: separate playback lifecycle

`src/services/microphone_monitor.py:20-217`:

- `start(device)` transitions from `stopped` to `starting`, creates one daemon monitor thread and prevents simultaneous second monitoring sessions. `stop` requests cancellation and transitions to `stopping`; `close` joins up to two seconds.
- Emits `Events.Speech.MICROPHONE_TEST_CHANGED(active=True,session_id)` at start and `active=False` in `finally`. The session marker distinguishes monitor state transitions; the service does not emit recognized speech.
- On thread execution, validates that the selected UID still resolves to this microphone, or, for legacy selection, checks that the selected numeric index has not been reassigned to another device name.
- Opens both `sounddevice.InputStream` and `OutputStream`; input is mono, output uses up to two channels; each uses its own native sample rate. `MonitorBuffer` keeps up to 120ms of audio and performs continuous linear interpolation between input and playback clocks, with zeros on underrun.
- The input callback computes RMS and maps approximate `-60 dBFS..0 dBFS` to `0..1` visible level. State phases: `stopped / starting / listening / stopping / error`; actual failure yields a localized general error state. Session cancellation returns to stopped.
- While test audio is active, the UI receives a fact that a microphone test is running; this must be distinguished from the ASR capture engine's own recording state.

### Scenarios and edge cases

| Situation | User-visible requirement |
|---|---|
| Physical mic appears through several host APIs | Show one physical microphone by default; let user resolve among its compatible representations |
| Windows endpoint identity unavailable | Keep name/index compatibility when unambiguous; do not claim stable physical UID |
| User unplugs device while application is open | Refresh catalog and report missing/unavailable selection; never switch without evidence to unrelated physical input |
| Device's native rate differs from 16k ASR | A device can be compatible at native rate; capture and ASR resampling are separate steps |
| User starts microphone test | Hear live own input through output and see a level, without prompting any ASR inference or LLM generation |
| Test stop / window close / backend failure | Release input/output streams and publish the end of monitor session; UI observes completion or a failure state |
| GUI-only configuration | Device setting/status may remain meaningful while worker-heavy inference remains unavailable, depending on actual initialized services |

## Capability and requirement links

| Capability | Current status | Future parity requirement | Validation |
|---|---|---|---|
| `CAP-MIC-001` enumerate physical microphone inputs with backend-aware deduplication | CONDITIONAL | `REQ-MIC-001`: catalog and compatibility derived from actual capture support, do not equate one PortAudio index with one physical device | Fixture: one WASAPI+DirectSound+MME physical endpoint, second distinct endpoint |
| `CAP-MIC-002` preserve physical selection through hotplug, migration and name/index change | CONDITIONAL | `REQ-MIC-002`: persistent identity where available; express unavailable vs ambiguous instead of silent switch | Changed order/index, missing UID, renamed/duplicate microphones |
| `CAP-MIC-003` monitor microphone to local playback with level meter | CONDITIONAL | `REQ-MIC-003`: monitoring has independent start/stop/error/session lifecycle; no hidden ASR/model requirement | Mock two sample rates, stop mid-stream, stream failure, bad output device |
| `CAP-MIC-004` support backend preferences where multiple interfaces expose the same physical microphone | CONDITIONAL | `REQ-MIC-004`: compatible backend selection must be explicit and deterministic; unsupported selection must be observable | Prefer WASAPI, manual DirectSound, unsupported WDM-KS |

**Confidence:** confirmed code paths and data types; **not verified** with real Windows device, hotplug, simultaneous game microphone acquisition, actual speaker routing or sample-clock drift. **Related:** `speech-input.md`, `../02-ui/asr-model-gallery-and-settings-workflows.md`, `../04-dependencies/native-system-api-and-ai-library-ownership.md`.
