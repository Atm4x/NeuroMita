# Session Timeline

The Python backend stores conversation facts, witnessed world/game events and
checkpoints in one session timeline. SQLite is the first persistence adapter.
Domain and application code do not depend on SQLite or on CFMD runtime types.

## Ownership

| Layer | Owner | Responsibility |
| --- | --- | --- |
| Domain | `domain/timeline` | Immutable events, identities, causality, knowledge, archive validation |
| Persistence port | `domain/timeline/ports.py` | Atomic append, branch reads, receipts, transfer and selection contracts |
| Session application | `SessionTimeline` | Explicit branch operations and character projections |
| Runtime application | `SessionTimelineRuntime` | Durable active selection, pinned turns, cancellation and short effect scopes |
| State coordination | `SessionRestoration` | Full Python checkpoints, participant restore, compensation and durable recovery |
| Conversation ingress | `ConversationTimeline` | Message identity, semantic turn kind and context provenance |
| Context projection | `TimelineContext` | Disposable branch-scoped summaries verified against source facts |
| History queries | `TimelineHistoryQueries` | Bounded incremental projections, detached paging and historical reads |
| Attachments | `TimelineContent` / `TimelineAssetStore` | Content-addressed bytes and explicit image materialization |
| Storage | `infrastructure/timeline` | SQLite transactions, indexes, initial import and summary materialization |
| Existing application bridge | `TimelineHistoryView` | Existing character-history vocabulary over the authoritative timeline |

The backend composition root registers the runtime before accepting server
requests. GUI-only startup continues to use its existing disconnected services.
The database file remains `Histories/world.db`; timeline tables use the
`timeline_` prefix and do not replace unrelated character tables.

## Event and ordering laws

- `event_id`, `session_id` and `branch_id` are stable application identities.
- One external message identity resolves to exactly one fact in a branch world,
  including its inherited prefix. Sibling futures remain independent.
- `sequence` orders facts within a branch world. UTC `occurred_at` records source
  time; clock time is not used as an optimistic concurrency token.
- `reply_to`, `react_to`, `caused_by` and `observes` are explicit references.
  Adjacent events do not imply causality.
- A fact is immutable. A presentation edit or deletion adds an event affecting
  the specified character's projection; it does not rewrite the original fact.
- Technical traces, provider diagnostics and streaming chunks are not events.
  Retry receipts and derived summaries are stored separately from semantic facts.
- Payloads have immutable JSON value semantics and a versioned envelope.

Each append uses an expected branch head and a stable operation key. A matching
retry returns the original committed events even after the head advances.
Reusing a key for a different intent fails. Event insertion, observer rows,
causal links, head advancement and the receipt share one database transaction.
An empty semantic command can retain a receipt without inventing a timeline event.

## Attachments and materialization

Inline images cross the conversation boundary once. Their immutable bytes live
in `timeline_assets`; events contain typed `image_ref` values. Identity binds
the canonical media type and content bytes. Reusing an image does not duplicate
its base64 text in events, recipient histories or operation receipts.

References are validated before event publication. Materialization explicitly
loads only the requested history page or selected prompt window. It verifies
content identity and reference metadata before returning provider/UI data.
Textual summaries and metadata queries do not read image bytes. A failed command
may leave an unreachable staged asset, but it cannot publish a dangling event;
portable export includes only the reachable attachment closure.

The session archive carries each reachable asset once and validates its content
on import. Remote image URLs remain external URLs; the attachment store does not
fetch them. Existing character JSON snapshot export materializes image content
for its existing consumer vocabulary.

## Character knowledge

Observers are captured when a fact occurs. Joining later does not grant access
to prior facts; leaving prevents subsequent default scene observations.
`EventObserved` explicitly grants later knowledge of one retained fact. Its
acquisition position differs from the original event position.

`CharacterContextReset` starts a fresh character context while retaining past
facts in the session. Queued and running turns formed against the earlier
context are rejected. A later explicit observation can disclose an old fact again.

Renderable conversation and world context use the same knowledge projection.
The history retrieval index can nominate message identities, but content is
resolved from the character's current branch world. Hidden, absent or unknown
history candidates cannot inject cache content into the prompt.

## Semantic turns

`ChatAPI.reply(message_id=...)` accepts a timeline message identity or the
existing external/UI message identity. A known referenced message can supply
the current target context even when no new input text was supplied.

`ChatAPI.react(event_id=...)` validates the character's knowledge of the event.
The existing instruction ingress remains available for callers that have not
published structured events; it forms a semantic trigger before generation.

`ChatAPI.initiate(...)` creates a proactive opportunity and records the eventual
message with `caused_by`. AFK creates `PlayerInactive` and uses `react_to`.

Incoming facts are committed before the provider call. Provider failure does
not erase player input. Character messages retain the branch and context head
used to form their turn. Tool intermediate messages have distinct identities.

Player speech and private camera/TV observations are separate facts, even when
they arrive in one request. Speech has the conversation audience; a POV image
has only its observing character. The reply targets the player's message, while
a camera-only turn reacts to the observation. Both inputs are excluded from
historical context because the current request already supplies them.

Turns pin an active selection generation and a character-context epoch. Changing
the selected session, switching away and back, or resetting the character
invalidates old work. Session switches also cancel registered generation tokens.
Short state mutations use the runtime effect scope; network generation runs
outside that scope. Current input images are excluded from historical context
when already represented by the request's current image input.

Camera/TV perception is `CharacterObservation`, rather than a fabricated player
utterance. It has its own observer and produces a reaction when it triggers a turn.

## Unity and games

Python's Unity ingress publishes structured runtime/reaction events before
reaction admission. Request receipts prevent retries from reapplying old roster
changes. Active roster entries can establish presence; explicit inactive entries
can establish departure. An omitted participant in an incomplete roster is not
treated as proof of departure. Hearing flags constrain message witnesses.

Mini-games publish through their host. The game module does not synchronize
character histories. Accepted chess moves from both sides receive a stable
source identity; the move notification and its optional reaction use one fact.
Sea Battle shots and lifecycle notifications also cross the host boundary.
The GUI reaction option controls generation, not fact publication. Game-instance
selection prevents late notifications from entering another session.

Private boards and ship coordinates are not broadcast to unrelated characters.
The former globally injected mini-game context is bypassed while the timeline
runtime owns conversation context.

## Branches and checkpoints

A child references its parent and a checkpoint cutoff. It inherits only that
prefix and then owns its own events. Parent events after the cutoff remain
retained and cannot be causal targets from the child. Nested forks apply all
ancestor cutoffs. A branch marker is created atomically with the child.

`SessionTimeline.checkpoint(snapshot, ...)` is the low-level operation storing
an explicit JSON snapshot. The configured application uses
`SessionTimelineRuntime.checkpoint(...)` to capture all registered Python state
owners. Its `restore(...)` validates the snapshot, forks at the checkpoint,
restores the owners and activates the child after successful application.
The abandoned future and its final mutable state remain retained.

The coordinator journals cross-owner transitions and recovers unfinished work
before the application accepts chat/server requests. See
[Python session state restoration](session-state-restoration.md) for the
participant contract, failure semantics and session initialization policy.

Existing per-character snapshot export includes a timeline checkpoint reference.
Loading an existing character-history JSON still replaces that character's
conversation projection. It is not a full-world rollback UI.

## Initial import and portable archives

Startup imports retained active and archived character messages before accepting
requests. Deleted rows remain excluded. Original timestamps are preserved.
Matching source messages are stored once; a second character's existing saved
copy provides evidence for an explicit observation, rather than inferred global
visibility. Missing message identities derive stable identities from source rows.
The import is restartable and marks completion only after all retained records
have been processed. Completed import never repopulates a newly created session.

`SessionArchive` is a versioned, storage-independent JSON representation of one
session. It includes branch metadata, locally owned events and operation
receipts. Event identities, source timestamps, snapshots, observers and links
survive transfer. Derived caches and summaries can be rebuilt.

Import validates branch topology, contiguous sequences, inherited checkpoint
cutoffs, preceding-world causality, knowledge and exact receipt intent before
writing. Destination identity collisions reject the whole import. Import does
not overwrite another session or change its active selection.

## CFMD adapter boundary

A CFMD adapter must implement the same domain repository/workspace contracts.
One CFMD unit of work must atomically validate the expected head, publish facts
and retain retry authority. Domain branches remain explicit entities; a database
revision is not substituted for a session branch or an event identity.

CFMD history, snapshots and maintained queries can implement these operations,
but the Python domain does not emulate CFMD's universal Candidate/rebase/watch
calculus on SQLite. A candidate adapter should pass the same domain and transfer
tests and preserve the same exported session meaning.
Full Python state coordination additionally requires a `RestorationJournal`
adapter and a semantic character-state participant replacing
`SQLiteCharacterState`. Swapping only the event repository does not migrate
the character variables and memory tables.

## Current boundaries and remaining work

- Registered participants now restore character variables, semantic memory and
  graph, working state, reminders, model observations and Python mini-games.
  Unity scene/physics and external providers require their own restoration
  adapters; restoring Python observations does not restore the Unity world.
- There is no new session/branch selection UI in this change. Runtime operations
  are available to application orchestration.
- Initial import rejects conflicting retained versions of a supposedly identical
  source message rather than choosing one silently.
- Query-result exact watch and a live CFMD adapter are not implemented.
- Cold projections are reconstructed from retained facts. Live history paging
  uses a bounded incremental cache; summaries permit reading the unsummarized
  acquisition suffix. Cache loss changes performance, not session meaning.

## Local performance measurements

`python scripts/benchmark_session_timeline.py --events 50000 --repeats 5`
uses an isolated temporary database, three characters and roughly 300-character
messages. One local run measured the following; these are observations, not
portable latency guarantees or test assertions.

| Operation | Time |
| --- | ---: |
| Append 50,000 events in batches | 37.06 s total |
| Cold 50-message history page | 1,732.19 ms |
| Warm 50-message history page | 2.76 ms median |
| Context after a verified summary | 24.14 ms median |
| Point knowledge lookup | 2.77 ms median |
| Full character context reconstruction | 1,887.63 ms median |
| Full session archive export | 3,059.19 ms median |

Indexes avoid scanning an entire character history for point knowledge and
context-reset checks. Batch append decodes its committed range once. Large
unsummarized histories and cold reconstruction remain explicit costs.
The 50,000-event run overlapped the regression test process. A separate
5,000-event run appended at 5,548 events/second and paged warm history in 1.34 ms.

## Verification

The focused test files are `tests/test_session_timeline.py`,
`tests/test_timeline_conversation.py`, `tests/test_timeline_history_view.py`,
`tests/test_timeline_producers.py`, `tests/test_timeline_transfer.py`,
`tests/test_timeline_history_queries.py`, `tests/test_timeline_assets.py` and
`tests/test_timeline_randomized.py`. `tests/test_timeline_architecture.py`
guards dependency direction and runs a SQLite session/branch/archive smoke test
in a separate Python process with site packages disabled.

They cover concurrency, atomic failure, retry identity, private knowledge,
reset/disclosure, nested branches, restart, target context, camera observations,
generation cancellation, summary invalidation, game/Unity publication and archive
corruption. Randomized tests compare branch and knowledge behavior against an
independent oracle, then transfer the resulting session. Attachment tests verify
deduplication, bounded materialization and the archive's reachable closure.
Existing chat, history, native-tool and mini-game regression suites
are also exercised. All changes are Python; no Unity or `dotnet` build is needed.
The restoration suites are `tests/test_session_restoration.py`,
`tests/test_session_state_participants.py`, `tests/test_game_snapshots.py` and
`tests/test_session_outputs.py`. They include durable recovery with new runtime
owners, a real Sea Battle subprocess and a combined store/model/game restore.

Run the focused suites with `python -m unittest discover -s tests -p "test_*timeline*.py"`
from the repository root, using the project's Python environment with the existing
application dependencies installed. They also run under pytest.
For GUI regression suites set `QT_QPA_PLATFORM=offscreen` and `QT_API=pyqt6`.

The wider pre-existing suite has separate environment/baseline limitations:
two `test_unity_dialogue_routing_boundary.py` tests read C# files from an absent
sibling `VinerX_NeuroMita-Unity` checkout. `test_warm_prompt_game_state.py` calls
`_warm_base_prompt`, which is already absent from the starting release branch.
These were identified separately from Python timeline verification.
