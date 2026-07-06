# data/message_dao.py
"""
OutpostX - MessageDAO
Production-focused DAO for Messages & MessageBodies (SQLite).

Assumes the DB has been initialized with message_schema.sql
and that data.message_model is available.

Key operations:
- insert_message(message, body)
- get_message(msgidx)
- list_messages_by_folder(folderidx, ...)
- update_message(message)
- delete_message(msgidx, hard=False)   # soft delete by default
- mark_read(msgidx, read=True)
- get_inbound_by_bbs_locator(bbs_call, bbsmsgno)

All writes are atomic (transaction per call).
"""

from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from .message_model import (
    Message,
    MessageBody,
)


class MessageDAO:
    """DAO for accessing messages and message_bodies.

    This class owns SQL statements and row ↔ model mapping.
    Higher-level workflow logic belongs in MessageRepository.
    """
    def __init__(self, db_path: Path | str):
        self._db_path = str(db_path)

    # ----------------------------
    # DB Connection helpers
    # ----------------------------
    def _connect(self) -> sqlite3.Connection:
        """Open a connection with Row factory and FK enforcement."""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    # ----------------------------
    # Create
    # ----------------------------
    def insert_message(self, msg: Message, body: Optional[MessageBody] = None) -> int:
        """
        Insert a Message (and optional MessageBody).
        Returns the new msgidx. Sets msg.msgidx on success.
        """
        cols = ", ".join(Message.INSERT_COLUMNS)
        qs = ", ".join("?" for _ in Message.INSERT_COLUMNS)
        sql = f"INSERT INTO messages ({cols}) VALUES ({qs})"

        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(sql, msg.to_insert_params())
            msgidx = cur.lastrowid
            msg.msgidx = msgidx

            if body and body.message is not None:
                body.msgidx = msgidx
                cur.execute(
                    f"INSERT INTO message_bodies ({', '.join(MessageBody.INSERT_COLUMNS)}) VALUES (?, ?)",
                    body.to_insert_params(),
                )

            conn.commit()
            return msgidx

    # ----------------------------
    # Read
    # ----------------------------
    def get_message(self, msgidx: int) -> Optional[Tuple[Message, Optional[MessageBody]]]:
        """Fetch a single message (and its body) by msgidx using the view."""
        sql = "SELECT * FROM v_messages_full WHERE msgidx=?"
        with self._connect() as conn:
            row = conn.execute(sql, (msgidx,)).fetchone()
            if not row:
                return None
            msg, body = Message.from_full_view_row(row)
            return msg, body


    def list_messages_by_folder(
        self,
        folderidx: int,
        *,
        include_deleted: bool = False,
        only_unread: bool = False,
        limit: int = 200,
        offset: int = 0,
        order_by: str = "rcvd_at DESC, sent_at DESC, msgidx DESC",
    ) -> List[Tuple[Message, Optional[MessageBody]]]:
        """
        List messages for a folder with common filters.

        Args:
            folderidx: Folder ID to list.
            include_deleted: Include soft-deleted rows.
            only_unread: Filter to unread only.
            limit/offset: Pagination controls.
            order_by: SQL ORDER BY clause (use with care).

        Returns:
            List of (Message, MessageBody|None) tuples.
        """
        where = ["folderidx = ?"]
        params: list = [folderidx]
        if not include_deleted:
            where.append("is_deleted = 0")
        if only_unread:
            where.append("is_read = 0")

        where_sql = " AND ".join(where)
        sql = f"""
            SELECT * FROM v_messages_full
            WHERE {where_sql}
            ORDER BY {order_by}
            LIMIT ? OFFSET ?
        """

        with self._connect() as conn:
            rows = conn.execute(sql, (*params, int(limit), int(offset))).fetchall()

        out: List[Tuple[Message, Optional[MessageBody]]] = []
        for r in rows:
            msg, body = Message.from_full_view_row(r)
            out.append((msg, body))
        return out


    def list_messages_by_state(
        self,
        mstate: str,
        *,
        direction: str | None = None,
        limit: int = 200,
        offset: int = 0,
        order_by: str = "sent_at ASC, msgidx ASC",
    ) -> List[Tuple[Message, Optional[MessageBody]]]:
        """
        List messages by lifecycle state (mstate), optionally filtered by direction.

        Primarily used by SendReceiveSession to fetch outbound QUEUED messages.
        Returns list of (Message, MessageBody|None).
        """
        where = ["mstate = ?", "is_deleted = 0"]
        params: list = [mstate]

        if direction:
            where.append("direction = ?")
            params.append(direction)

        where_sql = " AND ".join(where)
        sql = f"""
            SELECT * FROM v_messages_full
            WHERE {where_sql}
            ORDER BY {order_by}
            LIMIT ? OFFSET ?
        """

        with self._connect() as conn:
            rows = conn.execute(sql, (*params, int(limit), int(offset))).fetchall()

        out: List[Tuple[Message, Optional[MessageBody]]] = []
        for r in rows:
            msg, body = Message.from_full_view_row(r)
            out.append((msg, body))
        return out


    # ----------------------------
    # Update
    # ----------------------------
    def update_message(self, msg: Message) -> int:
        """
        Update a Message by msgidx.
        Returns number of affected rows (0 or 1).
        """
        if msg.msgidx is None:
            raise ValueError("update_message requires msg.msgidx")

        set_clause = msg.to_update_set_clause()
        sql = f"UPDATE messages SET {set_clause} WHERE msgidx=?"

        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(sql, msg.to_update_params(msg.msgidx))
            conn.commit()
            return cur.rowcount

    def mark_read(self, msgidx: int, read: bool = True) -> int:
        """Set is_read flag for a message. Returns affected rows."""
        sql = "UPDATE messages SET is_read=? WHERE msgidx=?"
        with self._connect() as conn:
            cur = conn.execute(sql, (1 if read else 0, msgidx))
            conn.commit()
            return cur.rowcount

    # ----------------------------
    # Delete (soft / hard)
    # ----------------------------
    def delete_message(self, msgidx: int, *, hard: bool = False) -> int:
        """
        Delete a message.
        - soft delete (default): sets is_deleted=1
        - hard delete: removes from messages (and cascades body via FK)
        Returns affected rows.
        """
        with self._connect() as conn:
            if hard:
                cur = conn.execute("DELETE FROM messages WHERE msgidx=?", (msgidx,))
            else:
                cur = conn.execute("UPDATE messages SET is_deleted=1 WHERE msgidx=?", (msgidx,))
            conn.commit()
            return cur.rowcount

    def purge_deleted(self, msgidxs: Optional[Iterable[int]] = None) -> int:
        """
        Permanently remove soft-deleted messages.

        Args:
            msgidxs: Optional iterable of specific msgidx values to purge.
                If omitted, purges all rows where is_deleted=1.

        Returns:
            Number of rows deleted from messages.
        """
        with self._connect() as conn:
            if msgidxs:
                placeholders = ", ".join("?" for _ in msgidxs)
                sql = f"DELETE FROM messages WHERE is_deleted=1 AND msgidx IN ({placeholders})"
                cur = conn.execute(sql, tuple(int(i) for i in msgidxs))
            else:
                cur = conn.execute("DELETE FROM messages WHERE is_deleted=1")
            conn.commit()
            return cur.rowcount


    # ----------------------------
    #  260303
    #  DEDUPE Consolidated helpers
    # ----------------------------
    def get_inbound_by_bbs_locator(self, bbs_call: str, bbsmsgno: str) -> Optional[Message]:
        """
        Look up an inbound message by (bbs_call, bbsmsgno).
        Enforces your unique index policy for inbound sync.
        """
        sql = """
            SELECT * FROM messages
            WHERE direction='INBOUND' AND bbs_call=? AND bbsmsgno=?
            LIMIT 1
        """
        with self._connect() as conn:
            row = conn.execute(sql, (bbs_call, bbsmsgno)).fetchone()
            if not row:
                return None
            return Message.from_messages_row(row)

    # ----------------------------
    #  helper for JNOS message dedup'ing
    # ----------------------------
    def inbound_exists_jnos_listing_fingerprint(
        self,
        *,
        bbs_call: str,
        lm_month: str,
        lm_day: str,
        lm_subject: str,
        lm_from: str,
        lm_to: str = "",   # <-- NEW
    ) -> bool:
        """
        JNOS inbound dedupe: LM message numbers are positional (and area-relative).

        Match on (month/day) plus prefix match on truncated LM columns (subject/from),
        and include TO (area) as a discriminator for bulletin areas (e.g., XSCPERM/XSCEVENT).

        Assumes rcvd_at is stored in ISO-8601 format.
        """
        mon_map = {
            "JAN": "01", "FEB": "02", "MAR": "03", "APR": "04",
            "MAY": "05", "JUN": "06", "JUL": "07", "AUG": "08",
            "SEP": "09", "OCT": "10", "NOV": "11", "DEC": "12",
        }
        mm = mon_map.get(lm_month.strip()[:3].upper())
        if not mm:
            return False

        try:
            dd = int(str(lm_day).strip())
        except Exception:
            return False
        dd2 = f"{dd:02d}"

        subj = (lm_subject or "").strip()
        frm = (lm_from or "").strip()
        to_ = (lm_to or "").strip()

        # Prefix matching because LM columns can be truncated
        subj_like = subj + "%" if subj else "%"
        frm_like = frm + "%" if frm else "%"

        # TO discriminator (area). If blank, don't constrain (older rows / private mail cases).
        to_like = to_.upper() + "%" if to_ else "%"


        # COALESCE function is used to return the first non-NULL value from a list of arguments
        sql = """
            SELECT 1
            FROM messages
            WHERE direction='INBOUND'
            AND bbs_call=?
            AND COALESCE(sent_at, rcvd_at) IS NOT NULL
            AND strftime('%m', datetime(COALESCE(sent_at, rcvd_at))) = ?
            AND strftime('%d', datetime(COALESCE(sent_at, rcvd_at))) = ?
            AND subject LIKE ?
            AND from_call LIKE ?
            AND UPPER(to_call) LIKE ?
            LIMIT 1
        """

        with self._connect() as conn:
            row = conn.execute(sql, (bbs_call, mm, dd2, subj_like, frm_like, to_like)).fetchone()
            return bool(row)
