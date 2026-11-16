"""Transient, character-scoped references to recently retrieved evidence."""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import re
from threading import RLock


def is_followup(query: str) -> bool:
    from managers.rag.rag_utils import entity_alias_phrases

    if entity_alias_phrases(query):
        return False
    text = query.casefold().strip()
    return bool(re.search(
        r"\b(подробнее|подробности|продолжи|продолжай|дальше|потом|"
        r"этой истории|эту историю|об этом|про это|по этой ситуации|о н[её]м|о ней|что ещ[её].*помнишь|почему (?:она|он|ты|это)|"
        r"что (?:она|он) (?:сделала?|сказала?)|tell me more|go on|what happened next|"
        r"that story|about that|why did (?:she|he|you))\b", text,
    ))


@dataclass
class Reference:
    source: str
    identity: int
    score: float
    confirmed: int
    message_id: str = ""
    triple: tuple = ()

    @property
    def key(self):
        return self.source, self.identity


@dataclass
class Window:
    scope: tuple
    head: int
    turn: object = None
    age: int = 0
    entries: dict = field(default_factory=dict)
    query: str = ""
    topic: str = ""


class RagContinuity:
    def __init__(self):
        self._windows = {}
        self._lock = RLock()

    def search(self, rag, query, *, limit, threshold, settings):
        from managers.rag.rag_utils import entity_alias_phrases, extract_keywords

        conversation = rag._conversation()
        with self._lock:
            enabled = bool(settings.get("RAG_CONTINUITY_ENABLED", True) and settings.get("RAG_ENABLED", False))
            if not enabled or conversation is None:
                self._windows.pop(rag.character_id, None)
                return rag.search_relevant(query, limit=limit, threshold=threshold)
            runtime = conversation.runtime
            runtime.assert_current()
            timeline = runtime.timeline
            turn = runtime.turn
            head = turn.context_head if turn else timeline.branch.head_sequence
            epoch = runtime.repository.context_epoch(timeline.branch_id, rag.character_id, through=head)
            scope = (id(rag.db), timeline.branch_id, epoch)
            token = (head, turn.trigger_id, turn.input_event_ids) if turn else (head, query)
            window = self._windows.get(rag.character_id)
            if window is None or window.scope != scope or head < window.head:
                window = Window(scope, head)
                self._windows[rag.character_id] = window
            steps = max(1, min(20, int(settings.get("RAG_CONTINUITY_TURNS", 4))))
            capacity = max(1, min(20, int(settings.get("RAG_CONTINUITY_MAX_RECORDS", 4))))
            decay = max(0.1, min(0.95, float(settings.get("RAG_CONTINUITY_DECAY", 0.7))))
            followup = is_followup(query)
            if token != window.turn:
                window.age += 1
                if window.turn is not None and not followup:
                    old_words = set(extract_keywords(window.query, max_terms=12))
                    new_words = set(extract_keywords(query, max_terms=12))
                    if old_words and new_words and not old_words.intersection(new_words):
                        window.age += 1
                window.turn = token
            window.head = head
            if not followup:
                window.topic = query[:1200]
            window.query = query[:4000]
            effective = query
            if followup:
                rows = rag.recent_query_rows(2, roles=("user", "assistant"))
                if rows:
                    context = "\n".join(f"{r.get('speaker') or r['role']}: {str(r['content'])[:600]}"
                                        for r in reversed(rows))
                    effective += f"\nPrevious exchange:\n{context}"
                if window.topic:
                    effective += f"\nTopic question: {window.topic}"
            fresh = rag.search_relevant(effective, limit=limit, threshold=threshold)
            fresh_keys = {(r["source"], r["id"]) for r in fresh}
            eligible = [ref for ref in window.entries.values()
                        if 0 < window.age - ref.confirmed < steps and ref.key not in fresh_keys]
            def retention_priority(ref):
                return ref.score * decay ** (window.age - ref.confirmed)

            eligible.sort(key=retention_priority, reverse=True)
            retained = []
            for ref in eligible:
                # Shrink the old portion as its evidence ages, even on follow-ups.
                allowance = max(1, math.ceil(capacity * decay ** (window.age - ref.confirmed)))
                if len(retained) >= allowance:
                    continue
                row = self._resolve(rag, conversation, ref)
                if row is not None:
                    row.update(retained=True, retained_age=window.age - ref.confirmed,
                               retained_turns_left=steps - (window.age - ref.confirmed))
                    row["score"] = ref.score * decay ** (window.age - ref.confirmed)
                    retained.append(row)
            for rank, row in enumerate(fresh):
                signals = row.get("features") or {}
                if float(row.get("score", 0)) < threshold:
                    continue
                if row["source"] not in ("memory", "history", "graph"):
                    continue
                if float(signals.get("cross_encoder", 1.0)) < 0.05:
                    continue
                evidence = max(float(signals.get("kw", 0)), float(signals.get("sim", 0)),
                               float(signals.get("graph_evidence", 0)))
                named_lexical = (rank < 2 and bool(entity_alias_phrases(effective))
                                 and float(signals.get("lex", 0)) >= 0.5)
                if evidence < 0.34 and not named_lexical:
                    continue
                ref = Reference(row["source"], row["id"], float(row.get("score", 0)), window.age,
                                str(row.get("message_id") or ""),
                                tuple(row.get(key) for key in ("subject", "predicate", "object")))
                window.entries[ref.key] = ref
            window.entries = dict(sorted(
                ((key, ref) for key, ref in window.entries.items() if window.age - ref.confirmed < steps),
                key=lambda pair: retention_priority(pair[1]), reverse=True,
            )[:capacity])
            runtime.assert_current()
            return fresh + retained

    @staticmethod
    def _resolve(rag, conversation, ref):
        if ref.source == "graph":
            with rag.db.connection() as conn:
                row = conn.execute(
                    "SELECT s.name,r.predicate,o.name FROM graph_relations r "
                    "JOIN graph_entities s ON s.id=r.subject_id JOIN graph_entities o ON o.id=r.object_id "
                    "WHERE r.character_id=? AND s.character_id=? AND o.character_id=? "
                    "AND s.name=? AND r.predicate=? AND o.name=? AND r.confidence>0 LIMIT 1",
                    (rag.character_id, rag.character_id, rag.character_id, *ref.triple),
                ).fetchone()
            return dict(source="graph", id=ref.identity, subject=row[0], predicate=row[1], object=row[2],
                        content=f"{row[0]} --{row[1]}--> {row[2]}") if row else None
        if ref.source == "history":
            with rag.db.connection() as conn:
                exists = conn.execute(
                    "SELECT 1 FROM history WHERE character_id=? AND id=? AND message_id=? "
                    "AND is_deleted=0 AND is_active=0",
                    (rag.character_id, ref.identity, ref.message_id),
                ).fetchone()
            row = conversation.retrieval_history(rag.character_id, {ref.message_id}).get(ref.message_id) if exists else None
            return dict(row, source="history", id=ref.identity, message_id=ref.message_id) if row else None
        from managers.rag.pipeline.config import RAGConfig

        mode = RAGConfig.from_settings(limit=1, threshold=0).memory_mode
        where, params = rag.memory_repo._base_where(mode)
        with rag.db.connection() as conn:
            row = conn.execute(
                f"SELECT m.content,m.type,m.priority,m.date_created FROM memories m WHERE {where} AND m.eternal_id=?",
                (*params, ref.identity),
            ).fetchone()
        return dict(zip(("content", "type", "priority", "date_created"), row),
                    source="memory", id=ref.identity) if row else None
