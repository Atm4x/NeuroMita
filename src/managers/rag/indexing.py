from __future__ import annotations

from dataclasses import dataclass
import json

import numpy as np

from core.cancellation import TaskCancelledError
from core.error_utils import format_exception
from core.state_barrier import StateUnavailable, state_access
from main_logger import logger
from managers.rag.pipeline.retrievers.faiss_index import invalidate
from managers.rag.rag_utils import make_reindex_progress_logger
from managers.settings_manager import SettingsManager


@dataclass(frozen=True)
class IndexSource:
    identity: int
    content: str


@dataclass(frozen=True)
class PreparedEmbedding:
    source: IndexSource
    vector: bytes
    dimensions: int
    sentences: tuple[tuple[int, bytes], ...] | None


class RagIndexStore:
    """Commit derived vectors only against their unchanged, character-scoped source."""

    _IDENTITY = {"history": "id", "memories": "eternal_id"}

    def __init__(self, rag):
        self.rag = rag

    def sources(self, table, model, *, identities=None, missing=False, sentences=False):
        identity = self._IDENTITY[table]
        where = ["s.character_id=?", "s.is_deleted=0", "s.content IS NOT NULL", "s.content != ''"]
        arguments = [self.rag.character_id]
        if identities is not None:
            if not identities:
                return []
            where.append(f"s.{identity} IN ({','.join('?' for _ in identities)})")
            arguments.extend(identities)
        match = f"e.source_table=? AND e.source_id=s.{identity} AND e.character_id=s.character_id AND e.model_name=?"
        if missing or sentences:
            where.append(f"{'EXISTS' if sentences else 'NOT EXISTS'} (SELECT 1 FROM embeddings e WHERE {match})")
            arguments.extend((table, model))
        if sentences:
            where.append(f"NOT EXISTS (SELECT 1 FROM sentence_embeddings e WHERE {match})")
            arguments.extend((table, model))
        with state_access(wait=True), self.rag.db.connection() as connection:
            rows = connection.execute(f"SELECT s.{identity}, s.content FROM {table} s WHERE {' AND '.join(where)} ORDER BY s.{identity}", arguments).fetchall()
        return [IndexSource(int(key), str(content)) for key, content in rows]

    def write(self, table, model, prepared, *, sentences_only=False):
        if not prepared:
            return 0
        identity = self._IDENTITY[table]
        count = 0
        with state_access(wait=True), self.rag.db.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                for item in prepared:
                    proof = (self.rag.character_id, item.source.identity, item.source.content)
                    current = connection.execute(f"SELECT 1 FROM {table} WHERE character_id=? AND {identity}=? AND content=? AND is_deleted=0", proof).fetchone()
                    if current is None:
                        continue
                    key = (table, item.source.identity, self.rag.character_id, model)
                    if not sentences_only:
                        connection.execute(f"UPDATE {table} SET embedding=? WHERE character_id=? AND {identity}=?", (item.vector, *proof[:2]))
                        connection.execute("""INSERT OR REPLACE INTO embeddings
                            (source_table, source_id, character_id, model_name, dimensions, embedding, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))""", (*key, item.dimensions, item.vector))
                        count += 1
                    if item.sentences is not None:
                        connection.execute("DELETE FROM sentence_embeddings WHERE source_table=? AND source_id=? AND character_id=? AND model_name=?", key)
                        connection.executemany("""INSERT INTO sentence_embeddings
                            (source_table, source_id, character_id, model_name, sentence_idx, embedding, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))""", [(*key, position, vector) for position, vector in item.sentences])
                        if sentences_only:
                            count += len(item.sentences)
                connection.commit()
            except BaseException:
                connection.rollback()
                raise
            if count:
                invalidate(self.rag.character_id, model, table)
        return count


class RagIndexer:
    """Separate provider computation from short, generation-checked persistence."""

    def __init__(self, rag):
        self.rag = rag
        self.store = RagIndexStore(rag)

    @staticmethod
    def _text_key(value):
        return "\n".join(line.strip() for line in value.splitlines()).strip()

    @classmethod
    def _matches_requested_text(cls, source, requested):
        if cls._text_key(source) == cls._text_key(requested):
            return True
        try:
            original = json.loads(requested)
        except (ValueError, TypeError):
            return False
        if not isinstance(original, dict):
            return False
        extracted = original.get("text") or original.get("content") or original.get("value") or original.get("summary")
        return isinstance(extracted, str) and cls._text_key(source) == cls._text_key(extracted)

    def _vector(self, vector, dimensions):
        if vector is None:
            return None
        vector = np.asarray(vector, dtype=np.float32)
        if vector.ndim != 1 or not vector.size or not np.all(np.isfinite(vector)) or (dimensions and vector.size != dimensions):
            return None
        return self.rag._array_to_blob(vector), int(vector.size)

    def _sentences(self, text, batch_size, dimensions):
        minimum = int(SettingsManager.get("RAG_SENTENCE_MIN_LEN", 20) or 20)
        sentences = self.rag._split_sentences(text, min_len=minimum)
        if not sentences:
            return ()
        with state_access(wait=True):
            pass
        vectors = self.rag._get_embeddings(sentences, batch_size=batch_size, priority="bulk") or []
        return tuple((position, encoded[0]) for position, vector in enumerate(vectors[:len(sentences)])
                     if (encoded := self._vector(vector, dimensions)) is not None)

    def _prepare(self, sources, texts, vectors, dimensions, *, batch_size, sentences):
        prepared = []
        for source, text, vector in zip(sources, texts, vectors):
            encoded = self._vector(vector, dimensions)
            if encoded is not None:
                sentence_vectors = self._sentences(text, batch_size, encoded[1]) if sentences else None
                prepared.append(PreparedEmbedding(source, *encoded, sentence_vectors))
        return prepared

    def documents(self, table, items, *, priority="hot", single=False):
        normalized = {int(key): str(text).strip() for key, text in items if key and str(text or "").strip()}
        if not normalized:
            return 0
        try:
            model, dimensions = self.rag._current_model_name(), self.rag._current_dimensions()
            sources = self.store.sources(table, model, identities=tuple(normalized))
            sources = [source for source in sources if self._matches_requested_text(source.content, normalized[source.identity])]
            texts = [source.content.strip() for source in sources]
            if not sources:
                return 0
            vectors = ([self.rag._get_embedding(texts[0])] if single else self.rag._get_embeddings(texts, priority=priority)) or []
            prepared = self._prepare(sources, texts, vectors, dimensions, batch_size=self.rag._get_reindex_batch_size(),
                sentences=bool(SettingsManager.get("RAG_SENTENCE_LEVEL", False)))
            return self.store.write(table, model, prepared)
        except (StateUnavailable, TaskCancelledError):
            raise
        except Exception as exc:
            logger.warning("RAG indexing failed (%s): %s", table, format_exception(exc))
            return 0

    def bulk(self, *, missing, progress_callback=None):
        try:
            model, dimensions = self.rag._current_model_name(), self.rag._current_dimensions()
            sources = {table: self.store.sources(table, model, missing=missing) for table in ("history", "memories")}
            total = sum(map(len, sources.values()))
            batch_size = self.rag._get_reindex_batch_size()
            sentences = bool(SettingsManager.get("RAG_SENTENCE_LEVEL", False))
            progress = make_reindex_progress_logger(self.rag, "index_all_missing" if missing else "index_all", total,
                extra_meta=f"model={model} | batch_size={batch_size}")
            processed = updated = 0
            progress.start()
            for table, records in sources.items():
                for offset in range(0, len(records), batch_size):
                    chunk = records[offset:offset + batch_size]
                    texts = [source.content for source in chunk]
                    vectors = self.rag._get_embeddings(texts, batch_size=batch_size, allow_when_rag_disabled=True, priority="bulk") or []
                    prepared = self._prepare(chunk, texts, vectors, dimensions, batch_size=batch_size, sentences=sentences)
                    updated += self.store.write(table, model, prepared)
                    for _record in chunk:
                        processed += 1
                        if progress_callback:
                            try:
                                progress_callback(processed, total)
                            except TaskCancelledError:
                                raise
                            except Exception:
                                pass
                        progress.tick(processed=processed, updated=updated, stage=table)
            if missing and sentences:
                updated += self._missing_sentences(model, dimensions, batch_size)
            if missing and SettingsManager.get("RAG_GRAPH_VECTOR_SEARCH", False):
                self.rag.index_graph_entity_embeddings()
            progress.done(processed=processed, updated=updated)
            return updated
        except (StateUnavailable, TaskCancelledError):
            raise
        except Exception as exc:
            logger.error("RAG reindexing failed: %s", format_exception(exc), exc_info=True)
            return 0

    def _missing_sentences(self, model, dimensions, batch_size):
        updated = 0
        for table in ("history", "memories"):
            for source in self.store.sources(table, model, sentences=True):
                sentences = self._sentences(source.content, batch_size, dimensions)
                prepared = PreparedEmbedding(source, b"", dimensions, sentences)
                updated += self.store.write(table, model, (prepared,), sentences_only=True)
        return updated
