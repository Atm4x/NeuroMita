# Action receipts

A response can ask for things the game performs later: change clothes, start a
track, walk somewhere. The prompt should not assume those happened. Unity
reports back what it actually did, and the next prompt marks each requested
action with what happened to it.

## Message shape

Unity sends a small list over the existing socket:

```json
{
  "action": "action_receipt",
  "character": "Crazy",
  "data": {
    "turn_uid": "task-17",
    "receipts": [
      {"segment": 0, "field": "clothes", "index": 0, "status": "completed", "detail": "", "seq": 2}
    ]
  }
}
```

Python derives a ref from turn_uid, segment, field and index, stores the status
in a per-character ledger and answers with action_receipt_ack. A message is
limited to 64 receipts; field is at most 32 characters, segment and index are
0..255, detail is trimmed to 160 characters.

## Reachable statuses

queued: the command is in the runtime queue.
started: the runtime accepted it and is working on it.
completed: the work was observed running and then finished.
applied: a directive with no runtime follow-up was executed.
failed: the runtime reported an error, or the wait timed out.
cancelled: the command was dropped before it ran (queue reset, CancelAll,
scene unload).
rejected: the runtime refused it outright.
unknown: an unrecognised status word. Aliases are folded in first: done and ok
mean applied, error and failure mean failed, cancel and canceled mean
cancelled.

failed, rejected, applied and completed are final. queued and started are
progress states, and the prompt shows them as in progress.

## Two phases

The turn reports once when the response has been presented, then keeps
reporting. The first report carries everything known at that moment. A command
that finishes afterwards sends its own single receipt, because the response is
already over and the model still needs the real outcome on the next turn. Late
reports are therefore normal, not duplicates.

Every receipt carries seq, counted per segment, field and index for one turn.
Python ignores a report whose seq is lower than the one already stored, so a
receipt queued before the flush can never roll an action back from completed to
started. Reports with no seq are treated as 0 and can always be replaced by a
numbered one.

Within one turn Unity merges repeated reports for the same action before
sending: a progress state gives way to a newer one, and a final state is
replaced only by a worse final state. When one requested action expands into
several runtime calls, the pessimistic outcome wins, so an action is reported
as completed only when every part of it completed.

## Prompt projection

The volatile prompt block lists the actions requested by the turn, each with
its short label when a receipt exists. Actions without a receipt stay
unmarked. A cancelled action reads as [interrupted], a rejected one as
[rejected].
