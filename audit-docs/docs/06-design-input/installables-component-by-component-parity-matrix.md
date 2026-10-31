# Installables: per-component functional parity and runtime validation checklist

**Purpose:** prepare exhaustive verification of the **31 registered static installables** and conditional/dynamic RAG cards. This is a **validation matrix from observed Python behavior**, not a recommendation for Rust libraries. **Status:** all IDs and family policies `CONFIRMED` by source; physical install, download, Windows ACL/GPU/CPU/ONNX readiness and live inference **NOT EXECUTED** in this pass.

**Sources:** `src/installables/catalog_manifest.py:42-1042`, `src/installables/registry_builder.py:13-154`, `src/core/installables/types.py:11-157`, family implementation files in [the existing catalog investigation](../01-functional/installable-families-runtime-operations.md) and [status/probe study](../01-functional/installable-component-probe-and-operation-contracts.md).

## General fixture phases for every card

Each component has independent verification gates:

1. **Catalog:** exact `component_id`, category, friendly name, engine/model/asset distinction; metadata discoverable before heavy inference imports.
2. **Status:** initial state + missing dependency/artifact diagnostics + backend compatibility and rev/status invalidation. Catalog presence does **not** imply ready.
3. **Preview:** user receives actionable plan, including backend addition and restart/clean semantics; confirmation and task admission are separate.
4. **Execution:** install/update/reinstall/uninstall/initialize where supported; progress, cancel before/after start, server queue and manual repair semantics.
5. **Postcondition:** refresh readiness, verify actual artifact/process when relevant, and preserve other installed components/managed environments; partial failure yields a meaningful status, not invented success.
6. **Consumer activation:** select model/voice/ASR/RAG and perform one observable operation where actual model can be installed; report skip when unavailable. Consumer confirmation is distinct from installer completion.

All steps currently have `SOURCE_ONLY` evidence unless marked otherwise. This is a **plan for future tests**, not a report that 31 installs were performed.

## Exact registered static ID coverage (31/31)

| Component ID | Type and distinct fixture scenario | Essential state transitions / compatibility | Physical E2E |
|---|---|---|---|
| `backend:cpu` | Managed Python CPU runtime | missing → plan → installed/readiness; no component-owned uninstall | NOT RUN |
| `backend:cuda` | Managed Python CUDA runtime | absent GPU, version-incompatible CUDA, backend health, dependency install | NOT RUN |
| `backend:onnx` | Managed Python ONNX runtime | backend availability and provider selection vs actual model availability | NOT RUN |
| `tts:edge_tts_rvc_cuda` | Edge TTS → RVC CUDA chain | remote/base TTS vs local RVC dependencies, CUDA vs absent GPU | NOT RUN |
| `tts:silero_rvc_cuda` | Silero → RVC CUDA chain | local Silero + RVC model readiness and async output | NOT RUN |
| `tts:edge_tts_rvc_onnx` | Edge TTS → ONNX voice conversion | provider selection, ONNX artifacts, non-CUDA path | NOT RUN |
| `tts:silero_rvc_onnx` | Silero → ONNX voice conversion | distinct from Silero+CUDA, output/playback and asset ownership | NOT RUN |
| `tts:omnivoice` | OmniVoice model | package/HF download, model init, missing weights and retry | NOT RUN |
| `tts:medium` | Fish Speech baseline | dependencies, weights and playback readiness | NOT RUN |
| `tts:medium+` | Fish Speech with additional compiled backend | dependency prep, Triton compile and native runtime readiness | NOT RUN |
| `tts:medium+low` | Fish Speech with RVC | compiled model + low-layer voice conversion readiness | NOT RUN |
| `tts:high` | F5 TTS baseline | requirements+vocoder+weights, per-model init and result | NOT RUN |
| `tts:high_clf5` | F5 Cross-Lingual mode | selected voice/language-specific artifact and configuration | NOT RUN |
| `tts:high+low` | F5 + RVC | high chain and RVC voice conversion as separate requirements | NOT RUN |
| `tts:high_clf5+low` | F5 Cross-Lingual + RVC | both optional capabilities, clean/update with partial state | NOT RUN |
| `asr:google` | Cloud speech recognizer | API/network readiness distinct from local installed weights | NOT RUN |
| `asr:gigaam` | GigaAM standard | package/weights and microphone sample-rate/recognizer init | NOT RUN |
| `asr:gigaam_onnx` | GigaAM ONNX | separate backend and hardware compatibility, owner settings | NOT RUN |
| `asr:whisper` | Whisper standard | model variant/device selection, environment/weights and transcript | NOT RUN |
| `asr:whisper_onnx` | Whisper ONNX | ONNX provider status and recognizer model selection | NOT RUN |
| `beats:beat_this` | Music Beat analysis | DSP/library model selection and full/chunk music beats outcome | NOT RUN |
| `dependency:ffmpeg` | External executable | initial file check, install location, restart/path, clean/uninstall | NOT RUN |
| `dependency:opencv` | Managed optional Python module | `find_spec(cv2)` vs managed package record, camera consumer and cleanup | NOT RUN |
| `voices:all` | Aggregate voice assets | count/install only missing/outdated vs clean all, batch partial progress | NOT RUN |
| `voices:CrazyMita` | Character assets bundle | download/stamp/version, update, per-character availability | NOT RUN |
| `voices:MitaKind` | Character assets bundle | same bundle contract, distinct owner character and path | NOT RUN |
| `voices:CappieMita` | Character assets bundle | same contract; preserve other characters' voice bundles | NOT RUN |
| `voices:Mila` | Character assets bundle | same contract; validation after empty/incomplete ZIP | NOT RUN |
| `voices:ShorthairMita` | Character assets bundle | same contract; update and clean distinction | NOT RUN |
| `voices:SleepyMita` | Character assets bundle | same contract; status refresh when model selected | NOT RUN |
| `voices:GhostMita` | Character assets bundle | same contract; nonselected asset still manageable | NOT RUN |
| **31/31** | **Exact static catalog identity accounted for** | **Family policy source-backed, no per-machine result fabricated** | **0/31 RUN** |

## Dynamic / internal-only catalog entries

| ID form | Availability | Test that distinguishes it |
|---|---|---|
| `rag:embeddings` | Internal aggregate lookup, not guaranteed user-facing card | disabled RAG, remote embedding provider, local provider, missing selected model; selected effective config determines required resource |
| `rag:reranker` | Internal aggregate lookup | reranker disabled/enabled, selected cross-encoder local model, absent backend |
| `rag:embeddings:<slug>` | Dynamic **card** from configured/default/custom checkpoint identity | HF repo identity/path, user-added model, install status, model and Python packages separately |
| `rag:reranker:<slug>` | Dynamic **card** | custom CE checkpoint, cache invalidation, usage only if enabled, status/install/uninstall semantics |

The dynamic denominator is **not fixed**: current selected models and custom configurations alter it. Treating `31` as the total of all AI Hub cards is incorrect.

## Component-specific error and cancellation cases (future)

- Failed pip install, missing/unsupported GPU or backend, cannot download weights, checksum/version mismatch, disk space exhausted, file lock, and clean reinstall with partial write. These are *test situations*, not claims that today's product handles each case correctly.
- Cancel an enqueued operation and an active install; distinguish task accepted from final status and from readied AI service.
- Perform `voices:all` clean reinstall and update with some already installed, one failing download and another unrelated voice bundle. Check progress and owned asset scope.
- On startup without GUI, read catalog/status without importing Qt; verify how interactive confirmation is handled, not silently assumed.
- Start actual consumer (TTS/ASR/RAG/Beat) and exercise one inference request; no synthetic `status.ready` value can substitute for this step.

## Coverage notation

- **Catalog identity gates:** `31/31 SOURCE CONFIRMED` static IDs, dynamic denominator unbounded.
- **Family operation signatures:** source-audited (specific differences described in linked functional documents).
- **Per-machine install/runtime readiness gates:** `0/31 E2E` in this research pass.
- **Research gate 16 remains PARTIAL**: do not convert to `PRIMARY` on the strength of an exhaustive ID list or fixture plan alone.

**New parity requirement `REQ-INSTALL-FIXTURE-001`:** each statically registered installable must have its own testable identity, applicable operations, observable status transitions, component-specific consumer activation (if meaningful) and resource ownership evidence. Dynamic models need the same contract without a fixed card count.

## Pass13 — current operation outcomes, source checked

Это уточнение **исследования функций**, а не отметка выполнения31 installs. Повторно проверены общие base adapters и конкретные status/uninstall/initialize paths. `ready` ниже — результат current component predicate, не доказанный inference.

| IDs, все статические семейства | Фактическое status/install основание | Фактическое удаление/initialize |
|---|---|---|
| backend:cpu/cuda/onnx | Managed backend paths + backend service probe; component install plan пустой, required_backend запускает общий orchestrator | Component uninstall noop «managed separately»; initialize None. Удаление environment — другая administration операция |
| tts:edge_tts_rvc_cuda / silero_rvc_cuda / edge_tts_rvc_onnx / silero_rvc_onnx | IVoiceModel.status → class requirements → backend/package/module-any/runtime assets. Silero добавляет свою dependency, Edge API requirement отдельно | RVC_UNINSTALL_PACKAGES через environment-mutation pip helper; generic initialize None. Shared assets/другие компоненты нельзя считать удалёнными одним result |
| tts:omnivoice | Требования package/version и каждый REQUIRED_MODEL_FILES; pinned HF snapshot + final checker | Удаляется model_dir; plan не перечисляет uninstall общих Python packages. Generic initialize None, runtime.initialize отдельно |
| tts:medium | FishSpeech requirements, общий checkpoint и backend | uninstall fish-speech-lib + checkpoint_dir; generic initialize None |
| tts:medium+ / medium+low | Fish requirements; low также RVC chain | fish-speech-lib/triton-windows, дляlow tts-with-rvc, общий checkpoint_dir. Только эти2 ID дают compile/clear_cache initialize plan |
| tts:high / high_clf5 / high+low / high_clf5+low | F5/CLF5 selected variant, vocoder/assets, preferred torch backend; RVC variants добавляют distribution/runtime assets | Удаляются model.safetensors/vocab, cross-lingual speaking_rate; RVC package только дляlow. Не весь shared vocoder/backend и не все Python packages |
| asr:google | SpeechRecognition/sounddevice/silero_vad + CPU backend; нет model manifest. Install artifacts callback возвращаетTrue; transcribe требует сеть | Base uninstall packages/paths пустые → noop. Нет component initialize plan; recognizer.init отдельно |
| asr:gigaam | requirements + известный selected checkpoint + ненулевые manifest files | Нет override uninstall lists → base noop. init runtime отдельно |
| asr:gigaam_onnx | requirements/backend predicate; manifest сам по себе не включён в is_installed | Нет override uninstall lists → base noop. Missing weights не следует выдавать за подтверждённый functional model |
| asr:whisper | requirements + известный model manifest + все required files ненулевые | Явно faster-whisper/ctranslate2 без dependency cascade + **весь model_download_root**, а не только выбранная модель |
| asr:whisper_onnx | requirements включает config/tokenizer/encoder/decoder assets и ONNX backend | Нет override uninstall lists → base noop. Наличие generic uninstall кнопки не доказывает освобождение места |
| beats:beat_this | Beat backend snapshot installed/available и отдельный installer plan | Specialized beat uninstall; анализ/кэш не равны model initialization. «Streaming» Python transport не доказывает incremental inference |
| dependency:ffmpeg | resolved ffmpeg.exe exists; fresh install при clean | Delete executable; successful exists probe не запускает codec test |
| dependency:opencv | optional managed record или find_spec(cv2), без import/камеры | Core-installed cv2 отдельно не удаляется; managed layer ownership необходим |
| voices:CrazyMita / MitaKind / CappieMita / Mila / ShorthairMita / SleepyMita / GhostMita | Per-bundle files + manifest/version; download/extract/stamp | Owned asset paths; не uninstall TTS engine, не создание voice inference session |
| voices:all | Aggregation7 наборов, pending missing/outdated либо clean all | Batch remove установленных; partial results/другие bundles независимо |

ASR adapter generic sequence: runtime context/engine settings → pip steps → manifest download либо async install callback → final is_installed. Clean bypasses ready shortcut. ASR status при отсутствии explicit python_paths подставляет active managed environment, strict_target и target dir; metadata process поэтому не обязан импортировать heavy module из GUI sys.path. Ошибка checker даёт FAILED; false predicate и missing backend отличимы через status_from_installed. TTS adapter дополнительно выставляет NEEDS_REINSTALL по requirement details. Эти status structs не запускают реальную inference задачу.

`repair` не универсальный отдельный method: current user path может означать clean/reinstall packages, повторную загрузку artifacts либо отдельный environment reset. Generic ASR initialize None и RAG uninstall noop — явные неподдержанные операции, не незавершённость описания. Решение сделать их полноценными в новом приложении будет новым продуктовым требованием, а не копированием placeholders.

Fish compile: optional install-stage confirmation skip/нетGUI → successful postponed step; explicit compile получает CUDA device, приостанавливает AI workers, проверяет reference Models/Mila.wav, запускает Python subprocess с managed paths/compile environment, читает log и resume после исхода. Clear_cache отдельный mode. Cancel/deadline принадлежит общему operation/subprocess supervision; visibility progress не управляет GPU. В аудите subprocess/compile/удаление не запускались.

Sources перепроверены: speech_recognizer_base status/build_install/uninstall; все5 ASR requirements/is_installed и overrides (uninstall списки есть только у Whisper в этом наборе); base_model IVoiceModel.status/plan adapters; Fish/F5/Omni/RVC spec predicates и uninstall; Fish build_initialize/_compile_call; install_plan_helpers pip/remove; core/installables/helpers.status_from_installed; backend installable component. Остальные FFmpeg/OpenCV/voices/Beat/RAG contracts сверены с source-grounded семейными документами предыдущих проходов. Artifact hashes, online sources/licenses конкретных weights, hardware и physical deletion outcomes остаются стендовыми проверками, а не выдуманным результатом.
