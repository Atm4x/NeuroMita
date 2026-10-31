# Event facts, command routes and subscriber lifetimes

**Scope:** active Python Core internal dispatch, not network IPC and not Python AI worker RPC. **Source snapshot:** `CodeNow.zip`; git revision remains the previously reported releases baseline, not independently verified from ZIP. **Confidence:** CONFIRMED for inspected methods/callsites; INFERRED for expectations about their ordering across domains.

## What the product needs

Many user and system actions need to reach their consumer without depending on the screen that initiated them: switch the active character, submit a message, handle successful completion of an assistant response, invalidate an AI component's installation state, or update a dialogue session panel. There are two different semantics here:

1. **An operation/command** asks some owner to act: switch character, cancel running install, start message generation.
2. **A fact/notification** says something has happened: character changed, assistant response was persisted, catalog status changed, Unity disconnected.

The current implementation transports both through `EventBus`, but it additionally exposes read-only typed services (`HistoryService`, `CharacterRegistry`, `SettingsService`, `InstallableCatalogService`, etc.). The new implementation must preserve these user-facing behaviors, not the current class or event-naming hierarchy.

## Dispatch model actually implemented

`src/core/events.py:16-49,118-327,390-425,430-518`:

- A global `EventBus` is lazily created by `get_event_bus()`. `reset_event_bus()` revives the **same instance** after shutdown, retaining subscriptions; `shutdown_event_bus()` stops it.
- Registered callbacks are weak by default, with explicit `weak=False` used for long-lived controllers; returned `EventSubscription` handles support `.close()`. Owner-based unsubscribe also exists.
- The bus rejects names beginning `get_` or containing `_get_`: read operations are meant to use typed services rather than emulate synchronous RPC over events. The `Events` registry still contains historical `GET_*` symbols; a declared name is **not** evidence of a working event route.
- `try_emit()` first snapshots live subscribers, then enqueues dispatch. No subscribers means accepted/no-op, **not proof that an action was handled**. Subscriber exceptions are logged without changing other handlers' execution.
- `COMMAND` has one serial lane; `ORDERED` uses eight keyed serial lanes; `CRITICAL` has four lanes keyed by event name; `BEST_EFFORT` uses the EventBus executor pool. Enqueue acceptance and successful application are not equivalent.
- `sync=True` is an ordering/delivery choice, not a guarantee of inline execution. Explicit `order_key`, otherwise `stream_id`, `task_uid`, `uid`, `character_id`, finally event name determine ordered grouping. ASR events use a dedicated `asr_capture` grouping.
- Event payloads may be structured dictionaries or other objects. The published dialogue runtime event carries a typed `DialogueRuntimeSnapshot`, unlike generic dict command payloads.

### Source-confirmed cross-domain routes

| Trigger/producer | Routed action or fact | Consumer / effect | Sources | Status |
|---|---|---|---|---|
| Game settings selects a character | `Character.SET_CURRENT` | `CharacterController` chooses registry character, saves/reflects current state and emits `CURRENT_CHANGED`; model/UI observe change | `src/ui/settings/game_settings.py:50-70`; `src/controllers/character_controller.py:24-75`; `src/controllers/model_controller.py:250-280` | ACTIVE |
| Chat asks to generate/cancel/remove/regenerate | `Chat.SEND_MESSAGE`, `CANCEL_ACTIVE_GENERATIONS`, `DELETE_MESSAGE`, `REGENERATE*` | `ChatController` subscribes and runs corresponding lifecycle | `src/controllers/chat_controller.py:400-426` | ACTIVE with runtime context |
| Assistant message committed | `History.MESSAGE_COMPLETED` | `HistoryController` may schedule maintenance; `GraphController` may schedule entity extraction if both RAG and graph extraction are enabled | `src/controllers/model_controller.py:1960-1974,2450-2478`; `src/controllers/history_controller.py:80-111`; `src/controllers/graph_controller.py:65-143` | CONDITIONAL graph path |
| Provider generation begins/completes/fails | `Model.ON_STARTED_RESPONSE_GENERATION`, `ON_SUCCESSFUL_RESPONSE`, `ON_FAILED_RESPONSE`, `ON_COMPRESSION_STARTED/FINISHED`, `ON_TOOL_EXECUTING/DONE` | GUI/task status projections and other subscribers | `src/controllers/model_controller.py:1250-1320,1710-1755,2610-2645`; `src/core/events.py:555-589` | ACTIVE, recipient-specific |
| Install task changes state | `Install.TASK_STARTED`, `TASK_FINISHED`, `TASK_FAILED`; async `COMPONENT_STATUS` | `InstallableController` invalidates status cache; embedding/voice/reranking controllers refresh their relevant state | `src/controllers/installable_controller.py:35-62`; `src/controllers/voice_model_controller.py:74-84`; `src/controllers/embedding_controller.py:144-157`; `src/services/installable_catalog_service.py:800-823` | ACTIVE |
| Unity dialogue context changes or disconnects | `Dialogue.RUNTIME_STATE_CHANGED`; `Server.CLIENT_DISCONNECTED` | `DialogueRuntimeStateService` creates or clears ephemeral snapshot; GUI observes projection | `src/services/dialogue_runtime_state.py:15-108` | ACTIVE when Unity path used |
| GUI-only startup | Same selected GUI command symbols | `GuiFallbackController` implements limited settings/character mutations and informative rejection for chat generation rather than starting AI services | `src/controllers/gui_fallback_controller.py:12-108` | CONDITIONAL `gui_only` |

`Events.*` also names many `GET_*` actions and source-level deprecated compatibility handlers. Their presence in `src/core/events.py:524-950` alone must **not** be counted as reachable runtime capability. The capability inventory is driven by producers + actually registered consumer + initialization path; any unverified route remains UNRESOLVED.

## Lifecycle and correctness as a behavioral contract

- **Initialization:** participating service/controller must be registered before a corresponding command is expected to have an effect. A missing subscriber can be silently accepted by the transport; no functionality should depend on delivery to an unregistered component.
- **Session ownership:** GUI and headless start modes initialize different consumer sets; read-only services and visible capabilities differ. GUI-only mode explicitly refuses message generation.
- **Ordering:** action ordering matters for repeated updates within one stream, game actor/character, installation command and ASR capture; unrelated lanes may execute concurrently. Read-after-write expectations must come from the owning service, not simply from emitting a fact.
- **Cancellation/termination:** shutdown drains dispatcher lanes up to their specified timeouts; outstanding external work can have its own lifetime. Controller close/unsubscribe and weak-lifetime management prevent background notifications from resurrecting abandoned GUI entities.
- **Observability:** trace IDs may propagate via event dict payload; drop count and log entries express saturation. Event success is not synonymous with a completed user operation.

## Domain-focused capability/requirements

- `CAP-EVENT-ROUTE-001` (`ACTIVE`): trigger domain operations from GUI or external input and deliver state notifications to independently managed consumers. `REQ-EVENT-ROUTE-001`: parity cases must distinguish command acceptance, execution and resulting fact.
- `CAP-EVENT-ROUTE-002` (`ACTIVE`): ordered streaming, task status and ASR event projection. `REQ-EVENT-ROUTE-002`: related events remain correctly ordered within a stream/capture/task; unrelated operations may progress independently.
- `CAP-EVENT-ROUTE-003` (`CONDITIONAL`): GUI-only command support, with limited settings and explicit rejection for backend-dependent actions. `REQ-EVENT-ROUTE-003`: GUI-only must not silently advertise full LLM/AI functionality.
- `CAP-EVENT-ROUTE-004` (`ACTIVE`): completion-triggered secondary work such as graph extraction, maintenance and UI projections. `REQ-EVENT-ROUTE-004`: downstream effects run only when their enabling conditions are satisfied, and failures do not retroactively imply that an assistant response was never persisted.

## Suggested parity checks, not new architecture

1. Start full Core and GUI-only separately; enumerate actual registered consumers before probing events.
2. Change character, observe identity and UI fact; send message in GUI-only, observe explicit unavailable behavior.
3. Submit two ordered fragments for the same stream, then concurrently for different streams; verify projections.
4. Commit a message with graph extraction enabled/disabled; verify conditionally scheduled extraction while preserving primary message.
5. Complete/install a component and observe status invalidation + projection; do not infer component readiness solely from task completion.
6. End a dialogue by Unity disconnect; verify ephemeral snapshot resets without deleting unrelated persisted history.

**Open gaps:** exhaustive event-producer/consumer matrix; actual subscribers for dynamically named handlers, Qt callback and old GET symbols; full process shutdown/restart E2E. **Related:** `03-runtime/background-tasks-and-events.md`, `03-runtime/conversation-session-projections.md`, `01-functional/installable-queue-admission-and-cancellation.md` (where present), `01-functional/registered-character-catalog-and-identity-contracts.md`.
