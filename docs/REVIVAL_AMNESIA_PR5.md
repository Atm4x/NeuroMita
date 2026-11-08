# PR5 — prompt-only revival amnesia (Python)

Companion to `VinerX/NeuroMita-Unity` branch `codex/health-mita-amnesia-pr5-20261108`, stacked on Unity PR #31. Related NeuroMita/NeuroMita-Unity#397.

## Safety and behavior
- `src/services/revival_amnesia.py` accepts only strict `NM_AMNESIA_V1|mode=...|actor=...` markers from Unity `runtime_events`, not conversational instructions or unrelated events. Last valid marker wins. Missing/invalid marker, GameMaster or disconnected Unity => `none`.
- `recent`: omit up to eight most recent **prior** dialogue messages (not the new user message) and RAG context from this prompt. Older summaries, long-term memories and character identity are still available. Eight is a provisional gameplay tuning parameter; it is **not** an exact time-since-death window.
- `identity`: suppress previous dialogue, history summary, core memory context, RAG, memory and reminder blocks from the prompt. A new system instruction asks the character not to claim missing relationships. Other world-state or template text may still identify facts, so this is *not guaranteed complete forgetting*.
- No database updates: HistoryManager, MemoryManager, RAG embeddings, chat UI and original history are untouched. Restoration requires only a new capture without a live amnesia marker or an explicit `none` marker.

## Validation
- Run `python -m unittest discover -s tests -p 'test_revival_amnesia.py'` with Python 3.10+.
- Inspect generated prompts in all three modes, especially after a new dialog turn, after restart/reconnect, and when switching between different Mitas.
- When paired with Unity, ensure `runtime_events` is routed to the intended unique CharacterType; the current type-based channel cannot distinguish duplicate instances.
- Confirm memory tables and RAG counts are unchanged.

Not run against live Python/Unity or DB in this environment. Keep as Draft.
