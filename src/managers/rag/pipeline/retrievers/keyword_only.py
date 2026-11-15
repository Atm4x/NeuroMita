from __future__ import annotations

from typing import Any, List

from managers.rag.rag_utils import rag_clean_text, keyword_score, json_loads_list, entity_alias_phrases, fts_morph_expand_token
from ..types import Candidate, QueryState
from ..config import RAGConfig
from ..repositories import HistoryRepository, MemoryRepository


class KeywordOnlyRetriever:
    """Keyword recall, including embedded rows when vector retrieval is off."""
    name = "keyword_only"

    def __init__(
        self,
        *,
        history_repo: HistoryRepository,
        memory_repo: MemoryRepository,
        rag: Any,  # kept for db access during transition
        cfg: RAGConfig,
    ):
        self.history_repo = history_repo
        self.memory_repo = memory_repo
        self.rag = rag
        self.cfg = cfg

    def retrieve(self, qs: QueryState) -> List[Candidate]:
        if not qs.keywords:
            return []

        out: list[Candidate] = []
        with self.rag.db.connection() as conn:
            cur = conn.cursor()
            if self.cfg.search_memory:
                out.extend(self._memories(cur, qs))
            if self.cfg.search_history:
                out.extend(self._histories(cur, qs))
        return out

    def _lookup_terms(self, keywords: list[str]) -> list[str]:
        if not self.cfg.lemmatization:
            return keywords
        return list(dict.fromkeys(
            form for keyword in keywords
            for form in fts_morph_expand_token(keyword, max_forms=16)
        ))

    def _memories(self, cur, qs: QueryState) -> list[Candidate]:
        out: list[Candidate] = []

        search_keywords = list(qs.keywords) + entity_alias_phrases(qs.user_query)
        rows = self.memory_repo.keyword_rows(
            cur,
            keywords=self._lookup_terms(qs.keywords) + entity_alias_phrases(qs.user_query),
            limit=int(self.cfg.kw_sql_limit),
            unembedded_only=self.cfg.vector_search_enabled,
            memory_mode=self.cfg.memory_mode,
        )
        for rd in rows:
            mid = int(rd.get("eternal_id") or 0)
            if mid <= 0:
                continue

            content_raw = rd.get("content")
            content_clean = rag_clean_text(str(content_raw or ""))

            try:
                text = content_clean + " " + " ".join(json_loads_list(rd.get("entities")))
                _, matches = keyword_score(qs.keywords, text, lemmatize=self.cfg.lemmatization)
                _, alias_hits = keyword_score(search_keywords[len(qs.keywords):], text)
                kw = (matches + alias_hits) / len(search_keywords)
            except Exception:
                kw = 0.0

            if kw < float(self.cfg.kw_min_score or 0.0):
                continue

            parts = json_loads_list(rd.get("participants"))
            out.append(Candidate(
                source="memory",
                id=mid,
                content=content_raw,
                meta={
                    "type": rd.get("type"),
                    "priority": rd.get("priority"),
                    "date_created": rd.get("date_created"),
                    "participants": parts,
                    "entities": rd.get("entities"),
                },
                features={"sim": 0.0, "kw": float(kw), "lex": 0.0, "time": 0.0, "entity": 0.0, "prio": 0.0},
            ))

        return out

    def _histories(self, cur, qs: QueryState) -> list[Candidate]:
        out: list[Candidate] = []

        rows = self.history_repo.keyword_rows(
            cur,
            keywords=self._lookup_terms(qs.keywords),
            limit=int(self.cfg.kw_sql_limit),
            unembedded_only=self.cfg.vector_search_enabled,
        )
        for rd in rows:
            hid = int(rd.get("id") or 0)
            if hid <= 0:
                continue

            content_raw = rd.get("content")
            content_clean = rag_clean_text(str(content_raw or ""))

            try:
                kw, _ = keyword_score(qs.keywords, content_clean, lemmatize=self.cfg.lemmatization)
            except Exception:
                kw = 0.0

            if kw < float(self.cfg.kw_min_score or 0.0):
                continue

            parts = json_loads_list(rd.get("participants"))
            out.append(Candidate(
                source="history",
                id=hid,
                content=content_raw,
                meta={
                    "role": rd.get("role"),
                    "date": rd.get("timestamp"),
                    "message_id": rd.get("message_id"),
                    "speaker": str(rd.get("speaker") or "").strip() or None,
                    "target": str(rd.get("target") or "").strip() or None,
                    "participants": parts,
                    "entities": rd.get("entities"),
                },
                features={"sim": 0.0, "kw": float(kw), "lex": 0.0, "time": 0.0, "entity": 0.0, "prio": 0.0},
            ))

        return out
