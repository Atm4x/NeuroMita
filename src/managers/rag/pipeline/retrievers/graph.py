"""
GraphRetriever — retrieves entity-relation triples from the graph store.

Matches query keywords and aliases against ``graph_entities.name``,
fetches 1-hop neighborhood, returns Candidates with formatted triples.
"""
from __future__ import annotations
from core.error_utils import format_exception

import logging
from typing import Any, Dict, List
from managers.rag.rag_utils import entity_alias_phrases, extract_keywords

from ..types import Candidate, QueryState
from ..config import RAGConfig

logger = logging.getLogger(__name__)


class GraphRetriever:
    name = "graph"

    def __init__(self, *, graph_store: Any, cfg: RAGConfig):
        self.gs = graph_store
        self.cfg = cfg

    def retrieve(self, qs: QueryState) -> List[Candidate]:
        if self.gs is None:
            return []

        # Vector search: embed query vs entity name embeddings.
        vec_names: List[str] = []
        if self.cfg.graph_vector_search and qs.query_vec is not None:
            try:
                vec_names = self.gs.find_by_embedding(qs.query_vec, threshold=0.55, top_k=10)
            except Exception as e:
                logger.debug(f"GraphRetriever: vector search failed: {format_exception(e)}")

        # Keyword match (always active as fallback / additive).
        kw_names = set(self._match_entities(qs.keywords, entity_alias_phrases(qs.user_query)))

        matched_names = sorted(set(vec_names) | kw_names)

        # Store matched entities in QueryState for EntityEnricher to use.
        if matched_names:
            qs.matched_entities = qs.matched_entities | set(matched_names)
        if not matched_names:
            return []

        # Fetch 1-hop relations for matched entities.
        triples = self.gs.query_by_entities(matched_names)
        if not triples:
            return []

        out: list[Candidate] = []
        seen: set[str] = set()

        for t in triples:
            subj = t.get("subject", "")
            pred = t.get("predicate", "")
            obj_ = t.get("object", "")
            raw_confidence = t.get("confidence")
            conf = min(1.0, max(0.0, float(1.0 if raw_confidence is None else raw_confidence)))
            if conf <= 0:
                continue

            triple_key = f"{subj}|{pred}|{obj_}"
            if triple_key in seen:
                continue
            seen.add(triple_key)

            # Format as readable text for the LLM.
            content = f"{subj} --{pred}--> {obj_}"

            # Score heuristic: confidence × keyword overlap.
            kw_overlap = self._keyword_overlap(qs.keywords, subj, obj_)
            direct_match = subj in kw_names or obj_ in kw_names
            evidence = conf * (0.5 + 0.5 * kw_overlap) if direct_match else conf * 0.25

            c = Candidate(
                source="graph",
                id=hash(triple_key) & 0x7FFFFFFF,
                content=content,
                meta={
                    "subject": subj,
                    "predicate": pred,
                    "object": obj_,
                    "subject_type": t.get("subject_type", ""),
                    "object_type": t.get("object_type", ""),
                    "created_at": t.get("created_at", ""),
                    "is_protected": bool(t.get("is_protected")),
                },
                features={
                    "confidence": conf,
                    "kw_overlap": kw_overlap,
                    "graph_evidence": evidence,
                },
                score=evidence,
            )
            out.append(c)

        logger.debug(f"GraphRetriever: {len(matched_names)} matched entities → {len(out)} triples")
        return out

    def _match_entities(self, keywords: List[str], aliases: List[str] | None = None) -> List[str]:
        """Match names by normalized tokens or a recognized alias."""
        if not keywords and not aliases:
            return []

        all_entities = self.gs.get_all_entities(limit=1000)
        entity_names = [e["name"] for e in all_entities]

        matched: set[str] = set()
        lemmatize = bool(getattr(self.cfg, "lemmatization", True))
        kw_lower = set(extract_keywords(" ".join(keywords), max_terms=max(12, len(keywords)),
                                       min_len=3, lemmatize=lemmatize))
        alias_names = {alias.casefold() for alias in aliases or []}

        for ename in entity_names:
            terms = set(extract_keywords(ename, max_terms=12, min_len=3, lemmatize=lemmatize))
            if ename.casefold() in alias_names or terms.intersection(kw_lower):
                matched.add(ename)

        return sorted(matched)

    @staticmethod
    def _keyword_overlap(keywords: List[str], subj: str, obj_: str) -> float:
        """Fraction of keywords that appear in subject or object names."""
        if not keywords:
            return 0.0
        kw_set = set(extract_keywords(" ".join(keywords), max_terms=max(12, len(keywords)),
                                    min_len=3, lemmatize=True))
        tokens = set(extract_keywords(f"{subj} {obj_}", max_terms=24, min_len=3, lemmatize=True))
        hits = len(kw_set.intersection(tokens))
        return min(hits / max(len(kw_set), 1), 1.0)
