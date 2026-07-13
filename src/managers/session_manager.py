"""SessionManager — операции над сессиями (сейвами) в общей world.db.

Сессия — это «сейв»: изолированный набор history/memories/variables/embeddings,
помеченный колонкой session_id. Активная сессия живёт в core.session_context;
здесь — операции над ними: список, переключение, копирование (ветвление), удаление,
переименование.

Класс не зависит от слоя персонажей: чтобы после переключения перечитать
загруженных персонажей, MainController выставляет колбэк character_reloader.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from core.events import Events, get_event_bus
from core.session_context import (
    DEFAULT_SESSION_ID,
    current_session_id,
    normalize_session_id,
    set_active_session_id,  # используется в switch()
)
from main_logger import logger
from managers.database_manager import DatabaseManager
from managers.settings_manager import SettingsManager
from services.contracts import SessionService

_LAST_SESSION_SETTING = "LAST_ACTIVE_SESSION_ID"

# Таблицы, которые несут session_id и участвуют в операциях сейва.
_SESSION_TABLES = ("history", "memories", "variables", "embeddings", "sentence_embeddings")


class SessionManager(SessionService):
    def __init__(self, character_reloader: Optional[Callable[[], None]] = None) -> None:
        self.db = DatabaseManager()
        self.event_bus = get_event_bus()
        self.character_reloader = character_reloader

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _table_cols(self, cursor, table: str) -> List[str]:
        try:
            cursor.execute(f"PRAGMA table_info({self.db._q_ident(table)})")
            return [r[1] for r in cursor.fetchall() if r and len(r) > 1 and r[1]]
        except Exception:
            return []

    def _has_col(self, cursor, table: str, col: str) -> bool:
        return col in self._table_cols(cursor, table)

    # ------------------------------------------------------------------
    # active session
    # ------------------------------------------------------------------
    def current(self) -> str:
        return current_session_id()

    def restore_last_active(self) -> str:
        """Читает последнюю активную сессию из настроек (НЕ меняя активную).

        Возвращает id, чтобы вызывающий сделал switch() из исходной 'default' —
        только так сработает перечитывание персонажей."""
        try:
            return normalize_session_id(SettingsManager.get(_LAST_SESSION_SETTING, DEFAULT_SESSION_ID))
        except Exception:
            return DEFAULT_SESSION_ID

    def switch(self, session_id: str, *, reload_characters: bool = True) -> str:
        """Делает сессию активной, перечитывает персонажей и оповещает подписчиков."""
        sid = normalize_session_id(session_id)
        prev = current_session_id()
        set_active_session_id(sid)
        try:
            SettingsManager.set(_LAST_SESSION_SETTING, sid, source="session")
        except Exception:
            pass

        if reload_characters and prev != sid and self.character_reloader is not None:
            try:
                self.character_reloader()
            except Exception as e:
                logger.error(f"[SessionManager] character reload after switch failed: {e}", exc_info=True)

        try:
            self.event_bus.emit(Events.Session.CHANGED, {"session_id": sid})
        except Exception:
            pass
        logger.info(f"[SessionManager] Active session: {prev} -> {sid}")
        return sid

    # ------------------------------------------------------------------
    # listing
    # ------------------------------------------------------------------
    def list_sessions(self) -> List[Dict[str, Any]]:
        """Все сессии, присутствующие в БД, с базовой статистикой."""
        sessions: Dict[str, Dict[str, Any]] = {}
        with self.db.connection() as conn:
            cur = conn.cursor()
            for table in ("history", "memories", "variables"):
                if not self._has_col(cur, table, "session_id"):
                    continue
                try:
                    cur.execute(f"SELECT session_id, COUNT(*) FROM {self.db._q_ident(table)} GROUP BY session_id")
                    for sid, cnt in cur.fetchall():
                        sid = normalize_session_id(sid)
                        entry = sessions.setdefault(sid, {"session_id": sid, "history": 0, "memories": 0, "variables": 0})
                        entry[table] = int(cnt or 0)
                except Exception as e:
                    logger.warning(f"[SessionManager] list_sessions {table} failed: {e}")
        # активная сессия всегда присутствует в списке, даже если ещё пустая
        active = current_session_id()
        sessions.setdefault(active, {"session_id": active, "history": 0, "memories": 0, "variables": 0})
        result = list(sessions.values())
        for e in result:
            e["active"] = (e["session_id"] == active)
        result.sort(key=lambda e: (not e["active"], e["session_id"]))
        return result

    def session_exists(self, session_id: str) -> bool:
        sid = normalize_session_id(session_id)
        with self.db.connection() as conn:
            cur = conn.cursor()
            for table in ("history", "memories", "variables"):
                if not self._has_col(cur, table, "session_id"):
                    continue
                try:
                    cur.execute(f"SELECT 1 FROM {self.db._q_ident(table)} WHERE session_id=? LIMIT 1", (sid,))
                    if cur.fetchone():
                        return True
                except Exception:
                    pass
        return False

    # ------------------------------------------------------------------
    # copy (branch) / delete / rename
    # ------------------------------------------------------------------
    def copy(self, src: str, dst: str, *, overwrite: bool = False) -> bool:
        """Копирует все данные сессии src в dst (ветвление сейва).

        history получает новые id, поэтому эмбеддинги истории ремапятся; память
        ключуется на eternal_id (сохраняется), поэтому её эмбеддинги копируются как есть."""
        src = normalize_session_id(src)
        dst = normalize_session_id(dst)
        if src == dst:
            logger.warning("[SessionManager] copy: src == dst, ignored")
            return False

        with self.db.connection() as conn:
            cur = conn.cursor()
            if not overwrite and self._session_nonempty(cur, dst):
                logger.warning(f"[SessionManager] copy: dst '{dst}' not empty (use overwrite)")
                return False
            if overwrite:
                self._delete_session_rows(cur, dst)

            try:
                self._copy_history(cur, src, dst)
                self._copy_table_simple(cur, "memories", src, dst)
                self._copy_variables(cur, src, dst)
                self._copy_memory_embeddings(cur, src, dst)
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(f"[SessionManager] copy {src}->{dst} failed: {e}", exc_info=True)
                return False
        logger.info(f"[SessionManager] Copied session {src} -> {dst}")
        return True

    def clear(self, session_id: Optional[str] = None) -> bool:
        """Стирает данные сессии (history/memory/embeddings/variables), но саму сессию
        оставляет — используется при сбросе сейва в игре. Допускает активную сессию."""
        sid = normalize_session_id(session_id if session_id is not None else current_session_id())
        with self.db.connection() as conn:
            cur = conn.cursor()
            try:
                self._delete_session_rows(cur, sid)
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(f"[SessionManager] clear '{sid}' failed: {e}", exc_info=True)
                return False
        # если чистим активную — перечитать персонажей (их in-memory состояние устарело)
        if sid == current_session_id() and self.character_reloader is not None:
            try:
                self.character_reloader()
            except Exception:
                pass
        try:
            self.event_bus.emit(Events.Session.CHANGED, {"session_id": sid})
        except Exception:
            pass
        logger.info(f"[SessionManager] Cleared session '{sid}'")
        return True

    def delete(self, session_id: str) -> bool:
        sid = normalize_session_id(session_id)
        if sid == current_session_id():
            logger.warning(f"[SessionManager] delete: refusing to delete active session '{sid}'")
            return False
        with self.db.connection() as conn:
            cur = conn.cursor()
            try:
                self._delete_session_rows(cur, sid)
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(f"[SessionManager] delete '{sid}' failed: {e}", exc_info=True)
                return False
        logger.info(f"[SessionManager] Deleted session '{sid}'")
        return True

    def rename(self, old: str, new: str) -> bool:
        old = normalize_session_id(old)
        new = normalize_session_id(new)
        if old == new:
            return True
        if self.session_exists(new):
            logger.warning(f"[SessionManager] rename: target '{new}' already exists")
            return False
        with self.db.connection() as conn:
            cur = conn.cursor()
            try:
                for table in _SESSION_TABLES:
                    if self._has_col(cur, table, "session_id"):
                        cur.execute(
                            f"UPDATE {self.db._q_ident(table)} SET session_id=? WHERE session_id=?",
                            (new, old),
                        )
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(f"[SessionManager] rename {old}->{new} failed: {e}", exc_info=True)
                return False
        if current_session_id() == old:
            self.switch(new, reload_characters=False)
        logger.info(f"[SessionManager] Renamed session {old} -> {new}")
        return True

    # ------------------------------------------------------------------
    # copy/delete internals
    # ------------------------------------------------------------------
    def _session_nonempty(self, cur, sid: str) -> bool:
        for table in ("history", "memories", "variables"):
            if self._has_col(cur, table, "session_id"):
                cur.execute(f"SELECT 1 FROM {self.db._q_ident(table)} WHERE session_id=? LIMIT 1", (sid,))
                if cur.fetchone():
                    return True
        return False

    def _delete_session_rows(self, cur, sid: str) -> None:
        for table in _SESSION_TABLES:
            if self._has_col(cur, table, "session_id"):
                cur.execute(f"DELETE FROM {self.db._q_ident(table)} WHERE session_id=?", (sid,))

    def _copy_table_simple(self, cur, table: str, src: str, dst: str) -> None:
        """Копирует строки таблицы, подставляя session_id=dst; id (если есть) авто-новый."""
        cols = self._table_cols(cur, table)
        if "session_id" not in cols:
            return
        insert_cols = [c for c in cols if c != "id"]
        col_list = ", ".join(self.db._q_ident(c) for c in insert_cols)
        # session_id подставляем параметром dst, остальные колонки копируем как есть
        select_sql = ", ".join(
            "?" if c == "session_id" else self.db._q_ident(c) for c in insert_cols
        )
        cur.execute(
            f"INSERT INTO {self.db._q_ident(table)} ({col_list}) "
            f"SELECT {select_sql} FROM {self.db._q_ident(table)} WHERE session_id=?",
            (dst, src),
        )

    def _copy_variables(self, cur, src: str, dst: str) -> None:
        cur.execute(
            "INSERT INTO variables (session_id, character_id, key, value) "
            "SELECT ?, character_id, key, value FROM variables WHERE session_id=?",
            (dst, src),
        )

    def _copy_history(self, cur, src: str, dst: str) -> None:
        """Копирует history построчно, чтобы получить old_id->new_id для эмбеддингов."""
        cols = self._table_cols(cur, "history")
        if "session_id" not in cols:
            return
        insert_cols = [c for c in cols if c != "id"]
        col_list = ", ".join(self.db._q_ident(c) for c in insert_cols)
        sess_idx = insert_cols.index("session_id")

        cur.execute(f"SELECT id, {', '.join(self.db._q_ident(c) for c in insert_cols)} FROM history WHERE session_id=?", (src,))
        rows = cur.fetchall()
        id_map: Dict[int, int] = {}
        placeholders = ", ".join(["?"] * len(insert_cols))
        for row in rows:
            old_id = row[0]
            values = list(row[1:])
            values[sess_idx] = dst
            cur.execute(f"INSERT INTO history ({col_list}) VALUES ({placeholders})", values)
            id_map[int(old_id)] = int(cur.lastrowid)

        # history-эмбеддинги ключуются на history.id — ремапим source_id
        if not id_map:
            return
        for emb_table in ("embeddings", "sentence_embeddings"):
            ecols = self._table_cols(cur, emb_table)
            if "session_id" not in ecols:
                continue
            ins_cols = [c for c in ecols if c != "id"]
            cur.execute(
                f"SELECT {', '.join(self.db._q_ident(c) for c in ins_cols)} "
                f"FROM {self.db._q_ident(emb_table)} WHERE source_table='history' AND session_id=?",
                (src,),
            )
            emb_rows = cur.fetchall()
            if not emb_rows:
                continue
            src_idx = ins_cols.index("source_id")
            sess_i = ins_cols.index("session_id")
            ph = ", ".join(["?"] * len(ins_cols))
            col_l = ", ".join(self.db._q_ident(c) for c in ins_cols)
            for er in emb_rows:
                vals = list(er)
                old_src = int(vals[src_idx])
                if old_src not in id_map:
                    continue  # строка истории не скопирована — пропускаем эмбеддинг
                vals[src_idx] = id_map[old_src]
                vals[sess_i] = dst
                cur.execute(f"INSERT INTO {self.db._q_ident(emb_table)} ({col_l}) VALUES ({ph})", vals)

    def _copy_memory_embeddings(self, cur, src: str, dst: str) -> None:
        """Память ключуется на eternal_id (сохраняется при копировании), source_id не меняется."""
        for emb_table in ("embeddings", "sentence_embeddings"):
            ecols = self._table_cols(cur, emb_table)
            if "session_id" not in ecols:
                continue
            ins_cols = [c for c in ecols if c != "id"]
            col_l = ", ".join(self.db._q_ident(c) for c in ins_cols)
            select_sql = ", ".join("?" if c == "session_id" else self.db._q_ident(c) for c in ins_cols)
            cur.execute(
                f"INSERT INTO {self.db._q_ident(emb_table)} ({col_l}) "
                f"SELECT {select_sql} FROM {self.db._q_ident(emb_table)} "
                f"WHERE source_table='memories' AND session_id=?",
                (dst, src),
            )
