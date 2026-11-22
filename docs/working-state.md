# Working state

Working state is a short handoff the model writes for its own next turn: the
current focus, what it thinks the situation is, tentative assumptions, open
loops and immediate next steps. It is rendered back as a [WORKING STATE]
assistant note and is never treated as fact. It lives in process memory, per
character, and is cleared by a history reset.

## What it is not

It is not a summary of the conversation. After a plain greeting the model will
still write `focus: greeting the player` and `situation: the player entered
the room` if the field is available. That note costs tokens on every following
turn and hands the next turn an agenda nobody agreed on.

The [WORKING STATE PROTOCOL] prompt block says this plainly, and the store
enforces it: a note that does not name at least one open loop is discarded when
no note exists yet. An existing note can still be refined without loops, so a
task that is being worked down does not vanish on the turn its last loop closes.
A discarded candidate is written to the debug log rather than silently.

The check is deliberately narrow. It does not try to judge whether a loop is
meaningful, because a second interpretation layer would reject legitimate
abstract tasks.

## Enabling

The field is offered when `ENABLE_WORKING_STATE` is on and the model runs with
structured output. Characters share that switch; there is no per-character
opt-out, and no character template needs to mention it.

`WORKING_STATE_MAX_CHARS` bounds the note (default 1000, clamped to 400-2000);
the least useful parts are trimmed first.
