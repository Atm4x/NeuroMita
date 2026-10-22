from core.error_utils import format_exception
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
import json
import datetime
import time as _time
from typing import List, Dict, Any, Optional, Tuple

from managers.database_manager import DatabaseManager
from core.state_barrier import bind_state_job, state_operation, state_job, state_access, StateUnavailable
from core.events import get_event_bus
from main_logger import logger
from core.cancellation import TaskCancelledError


from managers.rag.rag_utils import rag_clean_text
from managers.settings_manager import SettingsManager



# --- Default configuration constants ---
DEFAULT_QUERY_WEIGHT_USER = 0.7
DEFAULT_QUERY_WEIGHT_TAIL = 0.3
DEFAULT_TAIL_EXP_DECAY = 0.6
DEFAULT_SEARCH_LIMIT = 5
DEFAULT_SEARCH_THRESHOLD = 0.4
DEFAULT_EXPANDED_QUERY_MAX_CHARS = 4000
DEFAULT_RECENT_TAIL_MAX_CHARS = 1200

class RAGManager:
    """Поиск по памяти/истории. Тяжёлые ML-модели живут за границей AI engine —
    в main-процессе torch/transformers не импортируются вовсе."""

    _ACCESS_EXECUTOR: Optional[ThreadPoolExecutor] = None
    _ACCESS_EXECUTOR_LOCK: Lock = Lock()

    # Схема БД в рантайме не меняется, а построение RAGManager на каждый запрос
    # стоило двух PRAGMA table_info в hot path.
    _INSTANCES: dict[str, "RAGManager"] = {}
    _INSTANCES_LOCK: Lock = Lock()

    @classmethod
    def for_character(cls, character_id: str) -> "RAGManager":
        key = str(character_id or "")
        instance = cls._INSTANCES.get(key)
        if instance is not None:
            return instance
        with cls._INSTANCES_LOCK:
            instance = cls._INSTANCES.get(key)
            if instance is None:
                instance = cls(key)
                cls._INSTANCES[key] = instance
            return instance

    @classmethod
    def shutdown_executor(cls) -> None:
        with cls._ACCESS_EXECUTOR_LOCK:
            executor = cls._ACCESS_EXECUTOR
            cls._ACCESS_EXECUTOR = None
        if executor is not None:
            executor.shutdown(wait=False, cancel_futures=True)

    @classmethod
    def _get_access_executor(cls) -> ThreadPoolExecutor:
        if cls._ACCESS_EXECUTOR is None:
            with cls._ACCESS_EXECUTOR_LOCK:
                if cls._ACCESS_EXECUTOR is None:
                    cls._ACCESS_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="rag_access")
        return cls._ACCESS_EXECUTOR

    def __init__(self, character_id: str):
        self.character_id = character_id
        self.db = DatabaseManager()

        self.event_bus = get_event_bus()

        from managers.rag.pipeline.types import SchemaInfo
        from managers.rag.pipeline.repositories import HistoryRepository, MemoryRepository

        self._schema = SchemaInfo(
            history_cols=frozenset(self.db.get_table_columns("history")),
            mem_cols=frozenset(self.db.get_table_columns("memories")),
        )
        self.history_repo = HistoryRepository(self.db, character_id, self._schema)
        self.memory_repo = MemoryRepository(self.db, character_id, self._schema)

        from managers.rag.embedding import RagEmbedder
        self._embedder = RagEmbedder()

        self._embed_failed_warned: bool = False  # warn once when embed model unavailable

    def get_forgotten_count(self) -> int:
        """Count forgotten-but-not-deleted memories for this character."""
        if "is_forgotten" not in self._schema.mem_cols:
            return 0
        try:
            with self.db.connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT COUNT(*) FROM memories WHERE character_id=? AND is_forgotten=1 AND is_deleted=0",
                    (self.character_id,)
                )
                row = cursor.fetchone()
                return int(row[0]) if row else 0
        except Exception:
            return 0

    @property
    def schema(self):
        """Public snapshot of which optional columns exist in history/memories.

        Use this instead of the private ``_history_cols`` / ``_mem_cols``
        attributes from pipeline components.
        """
        return self._schema

    # Backward-compat shims — existing internal code that still uses
    # _history_cols / _mem_cols continues to work without change.
    @property
    def _history_cols(self):
        return self._schema.history_cols

    @property
    def _mem_cols(self):
        return self._schema.mem_cols

    # Эмбеддинг-слой вынесен в RagEmbedder (managers/rag/embedding.py);
    # ниже — тонкие делегаторы ради обратной совместимости внутренних вызовов.
    def _current_model_name(self) -> str:
        """Returns the DB key used to tag embedding rows (provider:model or bare hf_name)."""
        return self._embedder.current_model_name()

    def _current_dimensions(self) -> int:
        return self._embedder.current_dimensions()

    def _embed_via_provider(
        self,
        texts: List[str],
        is_query: bool = False,
        prefix: str = "",
    ) -> List[Optional[np.ndarray]]:
        """Embed texts through the configured embedding provider."""
        return self._embedder.embed_via_provider(texts, is_query=is_query, prefix=prefix)

    def _get_bool_setting(self, key: str, default: bool) -> bool:
        try:
            v = SettingsManager.get(key, default)
            if isinstance(v, str):
                return v.strip().lower() in ("1", "true", "yes", "on")
            return bool(v)
        except Exception:
            return bool(default)

    def _get_float_setting(self, key: str, default: float) -> float:
        try:
            return float(SettingsManager.get(key, default))
        except Exception:
            return float(default)

    def _get_int_setting(self, key: str, default: int) -> int:
        try:
            return int(SettingsManager.get(key, default))
        except Exception:
            return int(default)

    def _json_loads_list(self, s) -> list[str]:
        if not s:
            return []
        if isinstance(s, list):
            return [str(x).strip() for x in s if str(x).strip()]
        if not isinstance(s, str):
            return []
        raw = s.strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except Exception:
            pass
        return [p.strip() for p in raw.split(",") if p.strip()]

    def _parse_dt(self, s: Optional[str]) -> Optional[datetime.datetime]:
        if not s:
            return None
        raw = str(s).strip()
        if not raw:
            return None
        fmts = ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y_%H.%M", "%d.%m.%Y %H:%M")
        for f in fmts:
            try:
                return datetime.datetime.strptime(raw, f)
            except Exception:
                continue
        return None

    def _clip_text(self, s: Any, n: int) -> str:
        try:
            t = str(s or "")
        except Exception:
            return ""
        t = t.strip()
        if not t:
            return ""
        if n and len(t) > int(n):
            return t[: int(n)]
        return t

    def _l2_normalize(self, v: Optional[np.ndarray]) -> Optional[np.ndarray]:
        if v is None:
            return None
        try:
            n = float(np.linalg.norm(v))
            if not (n > 0.0):
                return v
            return (v / n).astype(np.float32, copy=False)
        except Exception:
            return v

    def _get_recent_active_contents(self, tail: int, role_filter: str = "user_only") -> list[str]:
        """
        Возвращает список контекстных текстов из активной history (самые последние -> более старые).
        role_filter:
          - "user_only"
          - "user_and_assistant"
          - "assistant_only"
        """
        out: list[str] = []
        tail_n = int(tail or 0)
        if tail_n <= 0:
            return out

        rf = str(role_filter or "user_only").strip().lower()
        if rf not in ("user_only", "user_and_assistant", "assistant_only"):
            rf = "user_only"

        conn = self.db.get_connection()
        try:
            cur = conn.cursor()
            where = "character_id=? AND is_active=1"
            params: list[Any] = [self.character_id]
            if "is_deleted" in self._history_cols:
                where += " AND is_deleted=0"
            if rf == "user_only":
                where += " AND role='user'"
            elif rf == "assistant_only":
                where += " AND role='assistant'"
            else:
                where += " AND role IN ('user', 'assistant')"

            cur.execute(
                f"""
                SELECT role, content
                FROM history
                WHERE {where}
                ORDER BY id DESC
                LIMIT ?
                """,
                tuple(params + [tail_n]),
            )
            rows = cur.fetchall() or []

            max_chars = int(SettingsManager.get("RAG_QUERY_TAIL_MAX_CHARS", DEFAULT_RECENT_TAIL_MAX_CHARS) or DEFAULT_RECENT_TAIL_MAX_CHARS)
            for _role, content in rows:
                c = rag_clean_text(self._clip_text(content, max_chars))
                if c:
                    out.append(c)
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass
        return out

    def _build_query_embedding(self, user_query: str, tail: int) -> Optional[np.ndarray]:
        """
        Два режима:
        - concat: как раньше (склейка хвоста + user_query -> один embedding)
        - weighted: отдельные embeddings + взвешенная сумма (лучше для коротких фраз игрока)
        """
        if not SettingsManager.get("RAG_VECTOR_SEARCH_ENABLED", False):
            return None
        mode = str(SettingsManager.get("RAG_QUERY_EMBED_MODE", "concat") or "concat").strip().lower()
        if mode not in ("concat", "weighted"):
            mode = "concat"

        if mode == "concat":
            qt = self._build_query_from_recent(user_query, tail=int(tail or 0))
            qt = rag_clean_text(qt)
            return self._l2_normalize(self._get_embedding(qt))

        # weighted
        w_user = float(SettingsManager.get("RAG_QUERY_WEIGHT_LAST_USER", DEFAULT_QUERY_WEIGHT_USER) or DEFAULT_QUERY_WEIGHT_USER)
        w_tail = float(SettingsManager.get("RAG_QUERY_WEIGHT_PREV_CONTEXT", DEFAULT_QUERY_WEIGHT_TAIL) or DEFAULT_QUERY_WEIGHT_TAIL)
        if w_user < 0.0:
            w_user = 0.0
        if w_tail < 0.0:
            w_tail = 0.0
        s = w_user + w_tail
        if s <= 0.0:
            w_user, w_tail = DEFAULT_QUERY_WEIGHT_USER, DEFAULT_QUERY_WEIGHT_TAIL
            s = 1.0
        # нормализуем веса (чтобы было стабильно)
        w_user /= s
        w_tail /= s

        # 1) embedding текущего user_query
        uq = rag_clean_text(str(user_query or "").strip())
        e_user = self._get_embedding(uq) if uq else None
        if e_user is not None:
            e_user = self._l2_normalize(e_user)

        # 2) embeddings хвоста (по умолчанию user_only, чтобы длинный ассистент не забивал)
        role_filter = str(SettingsManager.get("RAG_QUERY_TAIL_ROLE_FILTER", "user_only") or "user_only")
        tail_texts = self._get_recent_active_contents(int(tail or 0), role_filter=role_filter)

        e_tail: list[np.ndarray] = []
        if tail_texts and w_tail > 0.0:
            vecs = self._get_embeddings(tail_texts)
            for v in vecs or []:
                if v is None:
                    continue
                vv = self._l2_normalize(v)
                if vv is not None:
                    e_tail.append(vv)

        if e_user is None and not e_tail:
            return None

        # распределение веса хвоста: экспоненциальный спад от самого свежего к старым
        decay = float(SettingsManager.get("RAG_QUERY_TAIL_EXP_DECAY", DEFAULT_TAIL_EXP_DECAY) or DEFAULT_TAIL_EXP_DECAY)
        if not (0.0 < decay < 1.0):
            decay = DEFAULT_TAIL_EXP_DECAY

        tail_weights: list[float] = []
        if e_tail:
            raw = [(decay ** i) for i in range(len(e_tail))]  # i=0 самый свежий
            denom = float(sum(raw)) if raw else 1.0
            tail_weights = [(w_tail * (r / denom)) for r in raw]

        # суммируем
        base_vec = e_user if e_user is not None else e_tail[0]
        q = np.zeros_like(base_vec, dtype=np.float32)
        if e_user is not None and w_user > 0.0:
            q += (w_user * e_user).astype(np.float32, copy=False)
        for v, w in zip(e_tail, tail_weights):
            if w > 0.0:
                q += (w * v).astype(np.float32, copy=False)

        return self._l2_normalize(q)

    def _build_query_from_recent(self, user_query: str, tail: int = 2) -> str:
        """
        Требование: query строится из последних 1-3 сообщений (user+assistant),
        чтобы ловить местоимения/контекст.
        Мы берём хвост активной истории + текущий запрос.
        """
        parts: list[str] = []
        uq = str(user_query or "").strip()

        conn = self.db.get_connection()
        try:
            cur = conn.cursor()
            where = "character_id=? AND is_active=1"
            params: list[Any] = [self.character_id]
            if "is_deleted" in self._history_cols:
                where += " AND is_deleted=0"

            cur.execute(
                f"""
                SELECT role, content
                FROM history
                WHERE {where}
                ORDER BY id DESC
                LIMIT ?
                """,
                tuple(params + [int(tail)]),
            )
            rows = cur.fetchall() or []
            # rows сейчас от новых к старым -> развернём в хронологию
            rows = list(reversed(rows))
            for role, content in rows:
                r = str(role or "").strip().lower()
                c = str(content or "").strip()
                if not c:
                    continue
                tag = "User" if r == "user" else ("Assistant" if r == "assistant" else "Other")
                parts.append(f"{tag}: {c}")
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass

        if uq:
            parts.append(f"User: {uq}")

        # ограничим размер строки (на всякий случай)
        out = "\n".join(parts).strip()
        if len(out) > DEFAULT_EXPANDED_QUERY_MAX_CHARS:
            out = out[-DEFAULT_EXPANDED_QUERY_MAX_CHARS:]
        return out or uq

    def _blob_to_array(self, blob) -> Optional[np.ndarray]:
        """Конвертирует BLOB из SQLite обратно в проверенный numpy array."""
        if not blob:
            return None
        try:
            if len(blob) % np.dtype(np.float32).itemsize != 0:
                logger.warning("RAGManager: повреждённый embedding BLOB (размер не кратен float32)")
                return None
            vector = np.frombuffer(blob, dtype=np.float32).copy()
            expected_dim = self._current_dimensions()
            if expected_dim > 0 and vector.size != expected_dim:
                logger.warning(
                    f"RAGManager: пропущен embedding неверной размерности: "
                    f"получено {vector.size}, ожидалось {expected_dim}"
                )
                return None
            if vector.size == 0 or not np.all(np.isfinite(vector)):
                logger.warning("RAGManager: пропущен пустой или нечисловой embedding")
                return None
            return vector
        except Exception as e:
            logger.warning(f"RAGManager: не удалось декодировать embedding BLOB: {format_exception(e)}")
            return None

    def _array_to_blob(self, array: np.ndarray) -> bytes:
        """Конвертирует numpy array в байты для сохранения"""
        return self._embedder.array_to_blob(array)

    def _get_embedding(self, text: str, prefix: str = "", use_event_bus: bool = True) -> Optional[np.ndarray]:
        return self._embedder.get_embedding(text, prefix=prefix, use_event_bus=use_event_bus)

    def _get_embeddings(
        self,
        texts: List[str],
        prefix: str = "",
        use_event_bus: bool = True,
        batch_size: Optional[int] = None,
        allow_when_rag_disabled: bool = False,
        priority: str = "hot",
    ) -> List[Optional[np.ndarray]]:
        return self._embedder.get_embeddings(
            texts,
            prefix=prefix,
            use_event_bus=use_event_bus,
            batch_size=batch_size,
            allow_when_rag_disabled=allow_when_rag_disabled,
            priority=priority,
        )

    def _get_reindex_batch_size(self) -> int:
        """Use the active embedding preset batch size during bulk indexing."""
        try:
            from handlers.embedding_presets import resolve_full_config

            configured = (resolve_full_config().get("extra") or {}).get("batch_size")
            batch_size = int(configured or self._get_int_setting("RAG_EMBED_BATCH_SIZE", 16))
        except Exception:
            batch_size = self._get_int_setting("RAG_EMBED_BATCH_SIZE", 16)
        return batch_size if batch_size > 0 else 16

    # ------------------------------------------------------------------ #
    #  Sentence-level indexing helpers                                    #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _split_sentences(text: str, min_len: int = 20) -> list[str]:
        """Split text into sentences on punctuation and newline boundaries."""
        import re
        text = str(text or "").strip()
        if not text:
            return []
        # Split on sentence-ending punctuation followed by whitespace, or on newlines
        parts = re.split(r'(?<=[.!?…])\s+|\n+', text)
        return [p.strip() for p in parts if len(p.strip()) >= min_len]

    @state_job(check_result=True)
    def index_graph_entity_embeddings(self) -> int:
        """Compute graph vectors outside the state barrier and guard each write."""
        try:
            from managers.rag.graph.graph_store import GraphStore
            with state_access(wait=True):
                graph = GraphStore(self.db, self.character_id)
                entities = graph.get_entities_without_embeddings()
                model = self._current_model_name()
            vectors = self._get_embeddings([entity["name"] for entity in entities], priority="bulk") if entities else []
            count = 0
            for entity, vector in zip(entities, vectors or []):
                if vector is not None:
                    graph.store_entity_embedding(entity["id"], vector.astype(np.float32).tobytes(), model_name=model)
                    count += 1
            return count
        except (StateUnavailable, TaskCancelledError):
            raise
        except Exception as exc:
            logger.warning("RAG graph indexing failed: %s", format_exception(exc))
            return 0

    @state_job(check_result=True)
    def update_memory_embedding(self, eternal_id: int, text: str):
        """Stage a memory vector before committing against the unchanged source."""
        from managers.rag.indexing import RagIndexer
        RagIndexer(self).documents("memories", ((eternal_id, text),), single=True)

    @state_job(check_result=True)
    def update_history_embeddings(self, items: List[Tuple[int, str]], *, priority: str = "bulk") -> int:
        """Compute a batch outside state access and atomically store current results."""
        from managers.rag.indexing import RagIndexer
        return RagIndexer(self).documents("history", items or (), priority=priority)

    @state_job(check_result=True)
    def update_history_embedding(self, msg_id: int, text: str):
        """Stage one history vector without holding state access during embedding."""
        from managers.rag.indexing import RagIndexer
        RagIndexer(self).documents("history", ((msg_id, text),), single=True)


    @state_job(check_result=True)
    def search_relevant(self, query: str, limit: int = DEFAULT_SEARCH_LIMIT,
                        threshold: float = DEFAULT_SEARCH_THRESHOLD,
                        config_overrides: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Pipeline-based RAG search with selectable combiner modes:
          - union (default)
          - vector_only
          - intersect (min N methods)
          - two_stage (vector recall, others only add features; can fallback to union)

        config_overrides: dict of settings-key → value applied on top of RAGConfig.
            When provided, the RAG_ENABLED check is bypassed (tool-initiated call).
        """
        # config_overrides=None means automatic RAG: respect RAG_ENABLED flag.
        # config_overrides={} or non-None means explicit/tool call: always run.
        if config_overrides is None and not SettingsManager.get("RAG_ENABLED", False):
            return []

        # lazy imports (avoid circular)
        from managers.rag.pipeline.config import RAGConfig
        from managers.rag.pipeline.query_builder import QueryBuilder
        from managers.rag.pipeline.retrievers.vector import VectorRetriever
        from managers.rag.pipeline.retrievers.keyword_only import KeywordOnlyRetriever
        from managers.rag.pipeline.retrievers.fts import FTSRetriever
        from managers.rag.pipeline.combiner import (
            UnionCombiner,
            VectorOnlyCombiner,
            IntersectCombiner,
            TwoStageCombiner,
        )
        from managers.rag.pipeline.enrichers.common import TimeEnricher, EntityEnricher, PriorityEnricher
        from managers.rag.pipeline.reranker import LinearReranker
        from managers.rag.pipeline.debug_logger import RagDebugLogger

        cfg = RAGConfig.from_settings(limit=limit, threshold=threshold)

        # Apply per-call overrides (from tool or direct API).
        # Maps settings key → RAGConfig field name.
        if config_overrides:
            _KEY_TO_FIELD: Dict[str, str] = {
                "RAG_VECTOR_SEARCH_ENABLED": "vector_search_enabled",
                "RAG_USE_FTS": "use_fts",
                "RAG_KEYWORD_SEARCH": "kw_enabled",
                "RAG_SEARCH_MEMORY": "search_memory",
                "RAG_SEARCH_HISTORY": "search_history",
                "RAG_COMBINE_MODE": "combine_mode",
                "RAG_CROSS_ENCODER_ENABLED": "cross_encoder_enabled",
                "RAG_SEARCH_GRAPH": "search_graph",
                "RAG_USE_RRF": "use_rrf",
                "RAG_MEMORY_MODE": "memory_mode",
            }
            for key, val in config_overrides.items():
                field = _KEY_TO_FIELD.get(key)
                if field and hasattr(cfg, field):
                    setattr(cfg, field, val)

        qb = QueryBuilder(rag=self, cfg=cfg)
        _t_embed0 = _time.perf_counter()
        qs = qb.build(query)
        self._last_query_timing = {"embed_ms": (_time.perf_counter() - _t_embed0) * 1000, "rerank_ms": 0.0}

        # If no embedding AND no keywords AND no fts -> nothing to do
        if qs.query_vec is None and not qs.keywords and not cfg.use_fts:
            return []

        # --- choose retrievers (can depend on combiner mode) ---
        retrievers = []

        # vector recall (always useful if query_vec exists)
        if qs.query_vec is not None and cfg.vector_search_enabled:
            retrievers.append(VectorRetriever(
                history_repo=self.history_repo,
                memory_repo=self.memory_repo,
                rag=self,
                cfg=cfg,
            ))
        elif cfg.vector_search_enabled and qs.query_vec is None and not self._embed_failed_warned:
            self._embed_failed_warned = True
            logger.warning(
                "[RAG] Embedding model unavailable — falling back to FTS+keyword only. "
                "Vector search disabled for this session. "
                "Install torch/transformers or ensure the embedding model is loaded to restore full recall."
            )

        # keyword-only recall (embedding IS NULL candidates)
        # In two_stage we still allow it for fallback-to-union when vector set is empty.
        if cfg.kw_enabled and qs.keywords:
            retrievers.append(KeywordOnlyRetriever(
                history_repo=self.history_repo,
                memory_repo=self.memory_repo,
                rag=self,
                cfg=cfg,
            ))

        # FTS recall
        # In two_stage it is used mainly to add lex features to vector candidates (combiner decides).
        if cfg.use_fts:
            retrievers.append(FTSRetriever(
                history_repo=self.history_repo,
                memory_repo=self.memory_repo,
                rag=self,
                cfg=cfg,
            ))

        # Graph retriever (entity-relation triples from knowledge graph).
        if cfg.search_graph:
            try:
                from managers.rag.graph.graph_store import GraphStore
                gs = GraphStore(self.db, self.character_id)
                from managers.rag.pipeline.retrievers.graph import GraphRetriever
                retrievers.append(GraphRetriever(graph_store=gs, cfg=cfg))
            except Exception as e:
                logger.debug(f"[RAG][PIPE] GraphRetriever init failed (ignored): {format_exception(e)}", exc_info=True)

        # Fast path: vector_only mode -> don't even run other retrievers
        if cfg.combine_mode == "vector_only":
            retrievers = [r for r in retrievers if getattr(r, "name", "") == "vector"]

        buckets = {}
        for r in retrievers:
            try:
                with state_access(wait=True):
                    buckets[r.name] = r.retrieve(qs)
            except StateUnavailable:
                raise
            except Exception as e:
                logger.debug(f"[RAG][PIPE] retriever \'{r.name}\' failed (ignored): {format_exception(e)}", exc_info=True)
                buckets[r.name] = []

        # --- choose combiner ---
        mode = (cfg.combine_mode or "union").strip().lower()
        if cfg.use_rrf:
            from managers.rag.pipeline.combiner import RRFCombiner
            combiner = RRFCombiner(cfg=cfg)
        elif mode == "vector_only":
            combiner = VectorOnlyCombiner(cfg=cfg)
        elif mode in ("intersect", "intersect2", "intersect_n"):
            combiner = IntersectCombiner(
                cfg=cfg,
                min_methods=int(cfg.intersect_min_methods),
                require_vector=bool(cfg.intersect_require_vector),
                fallback_union=bool(cfg.intersect_fallback_union),
            )
        elif mode == "two_stage":
            combiner = TwoStageCombiner(cfg=cfg, fallback_union=bool(cfg.two_stage_fallback_union))
        else:
            combiner = UnionCombiner(cfg=cfg)

        cands = combiner.combine(buckets)

        if not cands:
            if cfg.detailed_logs:
                RagDebugLogger(rag=self, cfg=cfg).log(qs, buckets, cands)
            return []

        # --- enrich common features (time/entity/priority) ---
        enrichers = [
            TimeEnricher(rag=self, cfg=cfg),
            EntityEnricher(rag=self, cfg=cfg),
            PriorityEnricher(rag=self, cfg=cfg),
        ]
        for enr in enrichers:
            try:
                enr.enrich(qs, cands)
            except Exception as e:
                logger.debug(f"[RAG][PIPE] enricher \'{enr.name}\' failed (ignored): {format_exception(e)}", exc_info=True)

        # --- final rerank ---
        reranker = LinearReranker(cfg=cfg)
        reranker.score_all(cands)

        cands.sort(key=lambda c: float(c.score or 0.0), reverse=True)

        # --- optional cross-encoder second pass ---
        if cfg.cross_encoder_enabled and cfg.cross_encoder_model:
            try:
                from managers.rag.pipeline.cross_encoder import CrossEncoderReranker
                ce = CrossEncoderReranker.get(cfg.cross_encoder_model)
                # Adaptive top_k: for large pools cover more than fixed top_k;
                # for small pools never score FEWER than configured top_k.
                # Formula: max(top_k, n*ratio), then hard-capped by ce_max_items.
                # Examples (top_k=75, ratio=0.4, max=150):
                #   pool=62   → max(75,25)=75  → min(62,75)=62   (all, unchanged)
                #   pool=300  → max(75,120)=120 → cap(150)→120   (no change)
                #   pool=1512 → max(75,604)=604 → cap(150)→150   (4× faster)
                effective_top_k = min(len(cands),
                                      max(cfg.cross_encoder_top_k,
                                          int(len(cands) * cfg.ce_top_k_ratio)))
                if cfg.ce_max_items > 0:
                    effective_top_k = min(effective_top_k, cfg.ce_max_items)
                _t_ce0 = _time.perf_counter()
                ce.rerank(qs.user_query, cands, top_k=effective_top_k,
                          alpha=cfg.cross_encoder_alpha,
                          early_exit_score=cfg.ce_early_exit_score)
                self._last_query_timing["rerank_ms"] = (_time.perf_counter() - _t_ce0) * 1000
                cands.sort(key=lambda c: float(c.score or 0.0), reverse=True)
            except Exception as _ce_err:
                logger.debug(f"[RAG][cross_encoder] skipped: {format_exception(_ce_err)}", exc_info=True)

        if cfg.detailed_logs:
            RagDebugLogger(rag=self, cfg=cfg).log(qs, buckets, cands)

        # Enforce graph_min_results: guarantee at least N graph candidates in output
        graph_min = int(cfg.graph_min_results or 0)
        if graph_min > 0 and cfg.search_graph:
            limit = int(cfg.limit)
            top = cands[:limit]
            graph_in_top = sum(1 for c in top if c.source == "graph")
            if graph_in_top < graph_min:
                needed = graph_min - graph_in_top
                extra = [c for c in cands[limit:] if c.source == "graph"][:needed]
                if extra:
                    top = top[:limit - len(extra)] + extra
                    logger.debug(
                        f"[RAG][graph_min] bumped {len(extra)} graph triple(s) into top "
                        f"(had {graph_in_top}/{graph_min} required): "
                        + ", ".join(f'"{c.content}"' for c in extra)
                    )
                else:
                    logger.debug(
                        f"[RAG][graph_min] wanted {graph_min} graph results but only "
                        f"{graph_in_top} available in total"
                    )
            else:
                logger.debug(f"[RAG][graph_min] {graph_in_top} graph result(s) in top — requirement met")
            cands_out = top
        else:
            cands_out = cands[: int(cfg.limit)]

        if cfg.detailed_logs:
            RagDebugLogger(rag=self, cfg=cfg).log_final_output(cands_out)

        if cands_out:
            self._track_access_async(cands_out)

        # convert to old output format
        out: list[dict] = []
        for c in cands_out:
            out.append(c.to_public_dict())
        return out

    def _track_access_async(self, cands: list) -> None:
        """Fire-and-forget: increment access_count / last_accessed for retrieved items."""
        memory_ids = [c.id for c in cands if getattr(c, "source", None) == "memory"]
        graph_names: set = set()
        for c in cands:
            if getattr(c, "source", None) == "graph":
                meta = getattr(c, "meta", None) or {}
                subj = meta.get("subject", "")
                obj_ = meta.get("object", "")
                if subj:
                    graph_names.add(subj.lower())
                if obj_:
                    graph_names.add(obj_.lower())

        if not memory_ids and not graph_names:
            return

        char_id = self.character_id
        db = self.db

        def _do_track():
            now = datetime.datetime.utcnow().isoformat(timespec="seconds")
            try:
                with db.connection() as conn:
                    if memory_ids:
                        ph = ",".join("?" * len(memory_ids))
                        conn.execute(
                            f"UPDATE memories SET access_count=access_count+1, last_accessed=?"
                            f" WHERE character_id=? AND eternal_id IN ({ph})",
                            [now, char_id] + list(memory_ids),
                        )
                    if graph_names:
                        ph = ",".join("?" * len(graph_names))
                        conn.execute(
                            f"UPDATE graph_entities SET access_count=access_count+1"
                            f" WHERE character_id=? AND LOWER(name) IN ({ph})",
                            [char_id] + list(graph_names),
                        )
                    conn.commit()
            except Exception as e:
                logger.debug(f"[RAG] access tracking failed: {format_exception(e)}")

        try:
            self._get_access_executor().submit(bind_state_job(state_operation(_do_track)))
        except Exception:
            pass

    @state_job(check_result=True)
    def index_all_missing(self, progress_callback=None) -> int:
        """Index missing document, sentence and graph vectors in guarded batches."""
        from managers.rag.indexing import RagIndexer
        return RagIndexer(self).bulk(missing=True, progress_callback=progress_callback)

    @state_job(check_result=True)
    def index_all(self, progress_callback=None) -> int:
        """Recompute document vectors without holding a transaction during inference."""
        from managers.rag.indexing import RagIndexer
        return RagIndexer(self).bulk(missing=False, progress_callback=progress_callback)
