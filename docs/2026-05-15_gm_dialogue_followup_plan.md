# GM / Multi-Mita follow-up

1. Stabilize turn protocol.
- Store why the next speaker was chosen: `direct_target`, `gm_selected`, `gm_command`, `auto_round_robin`, `react_interrupt`.
- Pass that reason into the next auto-chain prompt so the selected Mita knows why she is speaking now.

2. Separate hidden GM from narrator GM at the orchestration level.
- Hidden GM should never surface in chat history/UI.
- Narrator GM may speak only as a visible scene/narration intervention.

3. Reduce inert auto-replies.
- Add a lightweight filter before auto-chain: addressed target, GM hint, long silence, or unresolved question.
- Skip forced replies when there is no real reason to answer.

4. Add short scene memory.
- Track unresolved question, current tension, silent participants, and last direct addressee.
- Feed scene digest to GM instead of long raw context.
