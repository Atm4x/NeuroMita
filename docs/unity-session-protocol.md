# Joint Unity sessions (protocol 1)

Unity owns immutable world files. Python owns timeline identities, events and full
Python snapshots. `action=timeline` uses the existing game socket and returns
`type=timeline_result`, `req_id`, `ok`, `protocol_version` and `body` (or a safe
error message). Every request includes `protocol_version=1` and `command`.

`catalog` returns retained branches, editable session/branch names, the active
branch, joint checkpoints and any pending operation. `rename` accepts `identity`
and `name`; names never become filesystem paths.

1. Unity suspends input, old outputs and world writes, captures and verifies an
   immutable file, and durably journals its operation before sending `prepare`.
2. `prepare` accepts `operation_id`, `expected_branch_id`, `kind` (`checkpoint`,
   `fork`, `resume`, `new_session`) and a `snapshot` descriptor. The descriptor
   has exactly `snapshot_id`, `sha256`, `version=1`, and `scene`. Optional fields
   are `target_branch_id`, `checkpoint_id`, `name`, `label`, `legacy_save_id`.
   Python captures its full source checkpoint and suspends state admission.
   Optional `runtime_events` maps known character identities to their buffered
   string events. These are published through the existing Unity ingress under
   exclusive state ownership before capture, with stable retry receipts.
   The response contains the source and target checkpoint/Unity descriptors.
3. Unity validates and applies the target world while remaining suspended.
4. `commit` with the operation identity applies Python state through the existing
   restoration journal. Fork/new-session identities derive deterministically from
   that operation. Resume restores the existing branch and never creates a fork.
5. Unity saves the acknowledged active binding locally, then sends `ack`.
   Python only reopens admission after that acknowledgment is durable. Unity then
   completes its journal and releases gameplay.

`status` reconciles an uncertain response. Repeated identical operations retain
their result; changed intent under an old identity conflicts. `abort` is allowed
before application and restores source state. After application, recovery must
finish the recorded target. A disconnect never silently means success or abort.
One pending operation owns the workspace. Startup retains the pending authority
and closes state admission until Unity reconciles it. There is deliberately no
timeout that automatically releases an uncertain two-process transition.

The optional legacy binding preserves physical save IDs and labels `default`'s
session as `Песочница`; it does not move or delete history or Unity save files.
New sessions currently inherit the current mutable state with an independent
conversation timeline. A pristine-new-game policy requires a separate explicit
initial snapshot; it is not represented as a fake reset here.

`reconnect` reopens a retained local Unity snapshot after application restart.
It accepts the usual operation identity, `expected_branch_id` and `snapshot`.
With `kind=resume` it restores both processes to the matching joint checkpoint
without another branch. If later semantic events exist, this is rejected before
admission; `kind=fork` explicitly retains that future and restores a child instead.
Ordinary application restoration cannot bypass a pending joint operation.

Only checkpoints with a retained Unity descriptor are offered for joint restore.
Old Python-only checkpoints remain valid for their existing callers. No participant
manifest is silently changed. Resume rejects a snapshot preceding later semantic
events, preventing old mutable state from being mixed with a newer history.

Focused verification: `test_unity_sessions.py` (15 tests),
`test_session_restoration.py` (20 tests), `test_timeline_architecture.py` (2 tests).
These checks do not constitute Unity Play Mode or a live two-process test.
The complete `test_*timeline*.py` selection passes 79/79 in the project's existing
`.venv`; system Python lacks several dependencies required by that wider suite.
