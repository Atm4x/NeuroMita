# Python session state restoration

`SessionRestoration` coordinates the mutable Python owners behind
`SessionTimelineRuntime`. The application composition root registers the
participants and runs journal recovery before chat/server admission.
The application service depends on domain ports and the state barrier; SQLite,
character services, Qt and game processes remain in adapters.

## State ownership

| Participant | Captured state | Restore behavior |
| --- | --- | --- |
| `SQLiteCharacterState` | Live character variables, all semantic memory records, graph entities/relations/aliases | Replaces scoped records in one SQLite transaction; remaps physical graph IDs |
| `GamesSnapshot` | Chess/Sea Battle state, logical game instance, public game sessions | Pauses an acknowledged child process; restores or recreates it without replaying gameplay events |
| `CharacterRuntimeSnapshot` | Application variables, working state, reminders and timer counters | Restores owners, rebuilds history from the selected branch, invalidates memory/vector caches |
| `ModelContextSnapshot` | Per-character world observations, shared scalar observations, temporary system context | Replaces the model owner's context and clears token statistics |

The full snapshot envelope contains `snapshot_version`, scene `presence`, and
an exact participant manifest with individual versions and immutable JSON
documents. Unknown versions, mismatching rosters and invalid state fail before
mutable state application. Adding an owner requires a deliberate snapshot
migration; silently skipping unknown state is unsupported.

Configured characters are captured even if their runtime objects are unloaded.
Loaded variables include changes not yet flushed to SQLite. A character first
materialized after the save restores its initial defaults with saved persistent
overrides. An already materialized character restores the exact saved variable
set, including removed keys.

Memory/graph semantics survive while physical database row identities and
embeddings are disposable. Old history rows are invalidated, their vectors are
cleared and the target conversation projection repopulates the search cache.
Other configured character data is restored; unrelated database scopes are
left outside the participant roster.

Countdown timers save remaining duration and resume from that duration at
restore time. Calendar reminders keep their absolute deadlines. The reminder
file accepts the earlier list format and writes a versioned object retaining
the next reminder number across restarts.

## Application operations

- `runtime.checkpoint(key=..., label=...)` captures a full Python snapshot.
  Saving does not invalidate provider work. Retrying a named save returns its
  original event before recapturing changed variables or ticking timers;
  reusing the key with another label fails.
- `runtime.restore(checkpoint_id, branch_id=...,
  checkpoint_branch_id=...)` restores a full checkpoint. The optional source
  branch permits restoring a checkpoint retained in an abandoned future.
  Presence must match that checkpoint's timeline world.
- `runtime.start_session(inherit_current=True, ...)` starts a separate session
  from explicitly chosen current mutable state. It creates initial presence and
  a full initial checkpoint, with no inherited conversation prefix.
- `runtime.start_session(initial_snapshot=document, ...)` initializes a
  separate session from a validated full snapshot. Exactly one initialization
  policy is required when state owners are registered.
- `restoration.recover()` repairs an unfinished journaled transition. It can
  also be called after a runtime failure requiring recovery.

These operations run outside a model turn. Direct runtime branch activation is
blocked once state participants are registered, so it cannot leave mutable
owners attached to a different history. The lower-level `SessionTimeline`
remains usable independently for storage/domain work.

The existing character-history JSON load/export remains a separate character
conversation operation. It does not invoke full session restoration.

## Transition and failure semantics

1. Acquire exclusive application state access and drain short active operations.
   Provider calls and audio playback do not hold this barrier.
2. Pause participants. Game queues acknowledge pause and drain already accepted
   facts into the source timeline before capturing its mutable state.
3. Validate desired and source snapshots. Retain a `Before restore` checkpoint
   on the source branch, so its abandoned mutable future can be restored later.
4. Persist a journal record containing source/target branches and both snapshots.
5. Invalidate old state jobs and durable turn generations. Apply participants
   in declared dependency order, then activate the target branch.
6. Resume participants under the final selection and complete the journal.

When application fails, compensation reapplies **every** source participant,
including the one that raised after a partial mutation. Compensation uses the
same dependency order: persistent records, games, runtime caches, model context.
Successful compensation retains the source selection and reports a failed
restore. It still invalidates work that could have observed intermediate state.

Failed compensation, failed resume or uncertain journal acknowledgement leaves
state unavailable and the journal retained where possible. Recovery chooses the
desired snapshot if the durable target branch was selected, otherwise the source
snapshot. A new Python runtime can recover using the same record. An unrelated
external branch selection fails closed instead of guessing. Journal admission
and completion are idempotent; a committed operation whose acknowledgement was
lost is resolved by reading durable state.

This is coordination across owners, not a single transaction encompassing
SQLite, JSON files and GUI processes. The durable journal and compensating
application make interrupted work recoverable. The barrier assumes one
application owner per workspace in one Python process; it is not a distributed
writer lease.

## Queued work and delivery

The state barrier preserves provenance across executor/dispatcher jobs and
rejects work belonging to an obsolete state or a replaced application owner.
Copied async contexts cannot inherit another task's active access depth.
Long-lived ingress services explicitly start a fresh operation per new input.
No lock spans an LLM/TTS provider wait.

RAG indexing stages document and sentence vectors outside state access and
outside SQLite write transactions. Each batch commits under the pinned job's
generation and verifies the source character, identity, deletion flag and
unchanged content. A restore can finish while embedding inference is still
running; its late vectors cannot overwrite restored memory or refill old
search caches. Reindexing shares this path instead of maintaining separate
unprotected writers. Retrieval guards cache-building reads and rejects a
computed result if its session changed.

Task snapshots carry detached state leases. Old successful task results become
cancelled and lose their result payload when serialized or polled. Old TTS
completion cannot attach audio to a restored task; local playback checks
cancellation/state validity. Retry outbox records retain branch/context proof,
so an abandoned reply cannot become a valid retry in the restored branch.
Already delivered external messages or Unity playback are outside Python's
ability to retract.

Chess snapshots retain root FEN and the complete move sequence, including
repetition history, plus side/mode/ELO controls. Sea Battle snapshots retain
boards, ship placement/damage, turn and lifecycle state. Game view queues carry
a restore generation to reject old board frames. Restoration applies state
directly and does not replay moves, reactions or lifecycle facts.
Chess analysis workers only compute on detached boards. The GUI owner admits
their results against the request generation and exact source position.
Pausing defers completed results; restoring invalidates old analysis and
retains a pending move request as explicit intent to recompute after resume.

## Boundaries and verification

Unity scene objects, physics, Unity-owned actions and other external services
need explicit participants/protocols before claiming full physical-world
restoration. Python's saved observations are only observations. No Unity/C#
files are changed. Session/history management UI remains deferred.
Normal application startup does not automatically recreate every previously
running game; subprocess recreation is part of explicit checkpoint restore or
unfinished transition recovery.

CFMD can replace repository/workspace and journal adapters, and provide a
semantic character-state adapter. Domain checkpoints and orchestration do not
depend on CFMD-specific runtime types. The current implementation uses SQLite.

`test_session_restoration.py` exercises compensation, uncertain commits,
restart recovery, initialization policies and barrier concurrency.
`test_session_state_participants.py` checks real character stores and a combined
store/model/live-game transition. `test_game_snapshots.py` includes an offscreen
Sea Battle process, process recreation and chess repetition transfer.
`test_session_outputs.py` checks tasks, retry authority and delayed audio.
`test_session_rag.py` covers inference overlapping save/restore, content edits,
sentence batches and derived-row validation. `test_chess_engine_restoration.py`
uses a controlled engine to verify late-result rejection and pending work
without starting or downloading LC0.
The architecture smoke test runs domain/repository/coordinator code in Python
with site packages disabled.
