# data/message_repo.py
"""
OutpostX - MessageRepository
Business-logic layer on top of MessageDAO.

Responsibilities:
- Enforce/validate state transitions
- Provide idempotent inbound upsert (by bbs_call+bbsmsgno)
- Provide convenience helpers for common workflows (queue, sent, receive, move, lock, delete)
- Keep all DB I/O funneled through the DAO layer
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone

from typing import Iterable, Optional, Tuple, List
from data.message_model import Message  # adjust import to your actual model

from .message_model import (
    Message,
    MessageBody,
    MessageState,
    Direction,
    FormType,
    MessageType,
)
from .message_dao import MessageDAO


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# Allowed state transitions (lightweight guardrails)
_ALLOWED: dict[MessageState, set[MessageState]] = {
    MessageState.NEW: {MessageState.DRAFT, MessageState.QUEUED},
    MessageState.DRAFT: {MessageState.QUEUED},
    MessageState.QUEUED: {MessageState.DRAFT, MessageState.SENT},   # <- allow unqueue back to DRAFT
    MessageState.SENT: {MessageState.POST_REMOTE, MessageState.RECEIVED},
    MessageState.POST_REMOTE: {MessageState.RECEIVED},
    MessageState.RECEIVED: set(),  # terminal from repo perspective
}


@dataclass(slots=True)
class RepoConfig:
    """Repository configuration defaults.

    Folder IDs are "root folderidx" values in the folders table.
    These defaults are used when the UI/service cannot resolve the
    standard roots (Inbox/Outbox/Drafts/etc.).
    """
    default_outbound_folderidx: int = 2
    default_inbound_folderidx: int = 1
    # tune these as your UI/UX evolves


class MessageRepository:
    """
    High-level message workflow API backed by MessageDAO.

    Typical callers:
      - UI widgets that list/move/mark messages
      - SqliteMessageService for editor-driven lifecycle transitions
      - SendReceiveSession for outbound selection and inbound storage
    """
    def __init__(self, dao: MessageDAO, config: Optional[RepoConfig] = None):
        """Create a repository wrapper.

        Args:
            dao: Low-level SQLite access object.
            config: Optional RepoConfig (folder defaults).
        """
        self.dao = dao
        self.cfg = config or RepoConfig()

    # ----------------------------
    # Basic accessors
    # ----------------------------
    def get(self, msgidx: int) -> Optional[Tuple[Message, Optional[MessageBody]]]:
        """Return a message and optional body by primary key (msgidx)."""
        return self.dao.get_message(msgidx)

    def list_by_folder(
        self,
        folderidx: int,
        *,
        include_deleted: bool = False,
        only_unread: bool = False,
        limit: int = 200,
        offset: int = 0,
    ) -> List[Tuple[Message, Optional[MessageBody]]]:
        """List messages in a folder.

        Args:
            folderidx: Folder ID to list.
            include_deleted: Include soft-deleted rows.
            only_unread: Filter to unread only.
            limit/offset: Pagination.
        """

        return self.dao.list_messages_by_folder(
            folderidx,
            include_deleted=include_deleted,
            only_unread=only_unread,
            limit=limit,
            offset=offset,
        )

    # ----------------------------
    # Create / Update flows
    # ----------------------------
    def create_outbound(
        self,
        *,
        from_call: str,
        to_call: str,
        subject: str,
        body_text: str,
        bbs_call: str,
        folderidx: Optional[int] = None,
        mtype: MessageType = MessageType.PRIVATE,
        formtype: FormType = FormType.PLAIN,
        request_delivery_receipt: bool = False,
        request_read_receipt: bool = False,
        urgent: bool = False,
        encoded: bool = False,
        messageid: Optional[str] = None,
    ) -> int:
        """
        Create an outbound message as a DRAFT.

        - Direction is always OUTBOUND.
        - Initial state is DRAFT (Save = draft).
        - messagelen is computed from the body text.
        """
        msg = Message(
            bbs_call=bbs_call,
            from_call=from_call,
            to_call=to_call,
            subject=subject,
            mstate=MessageState.DRAFT,  # was NEW
            direction=Direction.OUTBOUND,
            folderidx=folderidx if folderidx is not None else self.cfg.default_outbound_folderidx,
            mtype=mtype,
            formtype=formtype,
            is_rdr=request_delivery_receipt,
            is_rrr=request_read_receipt,
            is_urgent=urgent,
            is_encoded=encoded,
            messageid=messageid,
        )
        # Compute message length from the body text
        msg.messagelen = len(body_text or "")

        body = MessageBody(msgidx=None, message=body_text)
        return self.dao.insert_message(msg, body)

    # 251113: added to support edit queued messages
    def update_outbound_from_editor(
        self,
        msgidx: int,
        *,
        bbs_call: str,
        from_call: str,
        to_call: str,
        subject: str,
        body_text: str,
        mtype: MessageType,
        formtype: FormType,
        request_delivery_receipt: bool = False,
        request_read_receipt: bool = False,
        urgent: bool = False,
        encoded: bool = False,
        messageid: Optional[str] = None,
    ) -> int:
        """
        Update all editable fields for an outbound message being edited
        in the message editor.

        Intended primarily for NEW/DRAFT outbound messages:
        - Keeps msgidx, direction, folderidx, and timestamps as-is.
        - Updates from/to/subject/BBS/type/form/flags/body.
        """
        got = self.dao.get_message(msgidx)
        if not got:
            return 0
        msg, _ = got

        # Only allow outbound edits; ignore inbound rows
        if msg.direction != Direction.OUTBOUND:
            return 0

        # Allow edits for any outbound message that has NOT been sent yet.
        # i.e., editable states: NEW, DRAFT, QUEUED
        if msg.mstate not in (MessageState.NEW, MessageState.DRAFT, MessageState.QUEUED):
            return 0

        msg.bbs_call = bbs_call
        msg.from_call = from_call
        msg.to_call = to_call
        msg.subject = subject
        msg.mtype = mtype
        msg.formtype = formtype
        msg.is_rdr = request_delivery_receipt
        msg.is_rrr = request_read_receipt
        msg.is_urgent = urgent
        msg.is_encoded = encoded
        if messageid is not None:
            msg.messageid = messageid

        # Persist header/flags/etc.
        self.dao.update_message(msg)

        # Update body using existing helper so triggers recompute messagelen
        self.update_body(msgidx, body_text)
        return msgidx



    def update_subject(self, msgidx: int, subject: str) -> int:
        got = self.dao.get_message(msgidx)
        if not got:
            return 0
        msg, _ = got
        msg.subject = subject
        return self.dao.update_message(msg)

    def update_body(self, msgidx: int, body_text: str) -> int:
        """
        Replace the message body text and recompute messagelen.
        """
        got = self.dao.get_message(msgidx)
        if not got:
            return 0
        msg, _ = got

        # Upsert body row
        with self.dao._connect() as conn:
            cur = conn.execute("SELECT 1 FROM message_bodies WHERE msgidx=?", (msgidx,))
            if cur.fetchone():
                conn.execute(
                    "UPDATE message_bodies SET message=? WHERE msgidx=?",
                    (body_text, msgidx),
                )
            else:
                conn.execute(
                    "INSERT INTO message_bodies (msgidx, message) VALUES (?, ?)",
                    (msgidx, body_text),
                )
            conn.commit()

        # Now recompute and persist message length
        msg.messagelen = len(body_text or "")
        self.dao.update_message(msg)

        return 1

    # ----------------------------
    # State transitions
    # ----------------------------
    def find_by_state(
        self,
        state: str,
        *,
        direction: str | None = None,   # <-- add
        limit: int = 200,
        offset: int = 0,
    ):
        """List messages by state (and optional direction)."""
        return self.dao.list_messages_by_state(
            state,
            direction=direction,
            limit=limit,
            offset=offset,
        )


    def _set_state(self, msgidx: int, new_state: MessageState) -> int:
        """Transition a message to a new state (best-effort guardrails)."""
        got = self.dao.get_message(msgidx)
        if not got:
            return 0
        msg, _ = got
        if new_state not in _ALLOWED.get(msg.mstate, set()):
            # For now, be permissive for RECEIVED and POST_REMOTE when direction flips or sync occurs
            # You can tighten this as your flows stabilize.
            pass
        msg.mstate = new_state
        return self.dao.update_message(msg)

    def queue_for_send(self, msgidx: int) -> int:
        """Mark an outbound message as QUEUED for send."""
        return self._set_state(msgidx, MessageState.QUEUED)

    def mark_draft(self, msgidx: int) -> int:
        """#67, 8/8/26: Return an unsent outbound message to DRAFT state."""
        return self._set_state(msgidx, MessageState.DRAFT)    

    def mark_sent(self, msgidx: int, *, sent_at_iso: Optional[str] = None) -> int:
        """Mark an outbound message as SENT and set sent_at timestamp."""
        got = self.dao.get_message(msgidx)
        if not got:
            return 0
        msg, _ = got
        msg.sent_at = sent_at_iso or _utcnow_iso()
        msg.mstate = MessageState.SENT
        return self.dao.update_message(msg)

    def mark_post_remote(self, msgidx: int) -> int:
        return self._set_state(msgidx, MessageState.POST_REMOTE)

    def mark_received(self, msgidx: int, *, rcvd_at_iso: Optional[str] = None) -> int:
        """Mark an inbound message as RECEIVED and set rcvd_at timestamp."""
        got = self.dao.get_message(msgidx)
        if not got:
            return 0
        msg, _ = got
        msg.rcvd_at = rcvd_at_iso or _utcnow_iso()
        msg.mstate = MessageState.RECEIVED
        return self.dao.update_message(msg)

    # ----------------------------
    # Idempotent inbound upsert
    # ----------------------------
    def upsert_inbound(
        self,
        *,
        bbs_call: str,
        bbsmsgno: str,
        from_call: str,
        to_call: str,
        subject: str,
        header: Optional[str],
        body_text: str,
        sent_at_normalized: Optional[str],
        rcvd_at_iso: Optional[str] = None,
        folderidx: Optional[int] = None,
        mtype: MessageType = MessageType.PRIVATE,
        formtype: FormType = FormType.PLAIN,
        recvmsgid: Optional[str] = None,
        urgent: bool = False,
        encoded: bool = False,
        request_delivery_receipt: bool = False,
        request_read_receipt: bool = False,
    ) -> int:
        """
        Create or update an INBOUND message keyed by (bbs_call, bbsmsgno).
        Respects the unique index you defined for inbound messages.
        """
        existing = self.dao.get_inbound_by_bbs_locator(bbs_call, bbsmsgno)
        if existing:
            # Update metadata/body; keep msgidx stable
            existing.from_call = from_call
            existing.to_call = to_call
            existing.subject = subject
            existing.header = header
            existing.sent_at = sent_at_normalized
            existing.rcvd_at = rcvd_at_iso or existing.rcvd_at or _utcnow_iso()
            existing.folderidx = folderidx if folderidx is not None else self.cfg.default_inbound_folderidx
            existing.mtype = mtype
            existing.formtype = formtype
            existing.recvmsgid = recvmsgid
            existing.is_urgent = urgent
            existing.is_encoded = encoded
            existing.is_rdr = request_delivery_receipt
            existing.is_rrr = request_read_receipt
            existing.direction = Direction.INBOUND
            existing.mstate = MessageState.RECEIVED
            self.dao.update_message(existing)
            self.update_body(existing.msgidx, body_text)
            return int(existing.msgidx)

        # Insert new inbound
        msg = Message(
            bbs_call=bbs_call,
            bbsmsgno=bbsmsgno,
            from_call=from_call,
            to_call=to_call,
            subject=subject,
            sent_at=sent_at_normalized,
            rcvd_at=rcvd_at_iso or _utcnow_iso(),
            mstate=MessageState.RECEIVED,
            direction=Direction.INBOUND,
            header=header,
            folderidx=folderidx if folderidx is not None else self.cfg.default_inbound_folderidx,
            mtype=mtype,
            formtype=formtype,
            recvmsgid=recvmsgid,
            is_urgent=urgent,
            is_encoded=encoded,
            is_rdr=request_delivery_receipt,
            is_rrr=request_read_receipt,
        )

        # 260103, Compute message length from the body text (addresses missing received message length)
        msg.messagelen = len(body_text or "")               
        body = MessageBody(msgidx=None, message=body_text)
        return self.dao.insert_message(msg, body)

    # ----------------------------
    # Flags / moves / deletes / locks
    # ----------------------------
    def mark_read(self, msgidx: int, read: bool = True) -> int:
        return self.dao.mark_read(msgidx, read)

    def move_to_folder(self, msgidx: int, folderidx: int) -> int:
        got = self.dao.get_message(msgidx)
        if not got:
            return 0
        msg, _ = got
        msg.folderidx = folderidx
        return self.dao.update_message(msg)

    def move_to_trash(self, msgidx: int) -> int:
        """
        Move a message to the root 'Trash' folder if it exists.
        If no Trash root is found, fall back to a soft delete.
        """
        trash_idx = self._root_folderidx_by_name("Trash")
        if trash_idx is None:
            # No Trash folder yet → fall back to soft delete semantics
            return self.soft_delete(msgidx)
        return self.move_to_folder(msgidx, trash_idx)

    # 260110; added to support moving the message once sent
    def move_to_sent(self, msgidx: int) -> int:
        """
        Move a message to the root 'Sent' folder if it exists.
        If no Sent root is found, leave folder unchanged (but still allow SENT state).
        """
        sent_idx = self._root_folderidx_by_name("Sent")
        if sent_idx is None:
            return 0
        return self.move_to_folder(msgidx, sent_idx)


    def soft_delete(self, msgidx: int) -> int:
        """
        Flag a message as deleted (is_deleted=1) without moving folders.
        Normally you should prefer move_to_trash() from the UI.
        """
        return self.dao.delete_message(msgidx, hard=False)

    def undelete(self, msgidx: int) -> int:
        got = self.dao.get_message(msgidx)
        if not got:
            return 0
        msg, _ = got
        msg.is_deleted = False
        return self.dao.update_message(msg)

    def purge_trash(self, msgidxs: Optional[Iterable[int]] = None) -> int:
        return self.dao.purge_deleted(msgidxs)

    def lock_for_edit(self, msgidx: int) -> bool:
        got = self.dao.get_message(msgidx)
        if not got:
            return False
        msg, _ = got
        if msg.is_locked:
            return False
        msg.is_locked = True
        return self.dao.update_message(msg) == 1

    def unlock(self, msgidx: int) -> bool:
        got = self.dao.get_message(msgidx)
        if not got:
            return False
        msg, _ = got
        msg.is_locked = False
        return self.dao.update_message(msg) == 1

    def unqueue_to_draft(self, msgidx: int) -> int:
        got = self.dao.get_message(msgidx)
        if not got:
            return 0
        msg, _ = got
        # Optional: clear any send-at timestamp if it was set prematurely
        # msg.sent_at = None
        msg.mstate = MessageState.DRAFT
        # keep direction OUTBOUND; keep receipts/urgent flags as-is
        return self.dao.update_message(msg)

    # ----------------------------
    # other helpers
    # ----------------------------

    def _root_folderidx_by_name(self, name: str) -> Optional[int]:
        """
        Look up a root-level folder by name (e.g., 'Trash') and
        return its folderidx, or None if not found.
        """
        with self.dao._connect() as conn:
            row = conn.execute(
                "SELECT folderidx FROM folders WHERE name=? AND parentidx IS NULL",
                (name,),
            ).fetchone()
            if not row:
                return None
            return int(row["folderidx"])


    def folder_name(self, folderidx: int) -> str:
        with self.dao._connect() as conn:
            row = conn.execute(
                "SELECT name FROM folders WHERE folderidx=?", (folderidx,)
            ).fetchone()
            return row["name"] if row else ""

    # ----------------------------
    # lock helpers
    # ----------------------------
    def acquire_lock(self, msgidx: int) -> bool:
        """
        Attempt to lock the message. Returns True if we acquired the lock,
        False if it was already locked (idempotent).
        """
        with self.dao._connect() as c:
            cur = c.execute(
                "UPDATE messages SET is_locked=1 WHERE msgidx=? AND is_locked=0",
                (msgidx,),
            )
            c.commit()
            return cur.rowcount > 0

    def release_lock(self, msgidx: int) -> bool:
        """
        Release the message lock. Returns True if we actually released it,
        False if it wasn’t locked.
        """
        with self.dao._connect() as c:
            cur = c.execute(
                "UPDATE messages SET is_locked=0 WHERE msgidx=? AND is_locked=1",
                (msgidx,),
            )
            c.commit()
            return cur.rowcount > 0

    
    # ----------------------------
    #  250801 x138
    #  DEDUPE Consolidated Code Block
    # ----------------------------
    def inbound_exists_for_dedupe(
        self,
        *,
        bbs_id: str,
        bbs_call: str,
        bbsmsgno: str,
        lm_row: Optional[dict] = None,
        area_hint: str = "",
    ) -> bool:
        """
        Unified inbound duplicate check.

        JNOS uses a listing fingerprint because JNOS message numbers are
        positional and the same bulletin may be mirrored on multiple BBSs.

        Other BBS types use the stable remote locator:
            bbs_call + bbsmsgno

        The resulting path is:    
        SendReceiveSession._retrieve_one_message()
                    |
                    v
        MessageRepository.inbound_exists_for_dedupe()
                    |
                    +-- JNOS
                    |      |
                    |      v
                    |  DAO cross-BBS comparison:
                    |      month/day
                    |      sender local-part
                    |      subject
                    |      message length
                    |
                    +-- Other BBS types
                        |
                        v
                    bbs_call + bbsmsgno

        """
        if (bbs_id or "").strip().lower() == "jnos":
            if not bbsmsgno:
                # Cannot safely identify this JNOS listing entry.
                return False

            # JNOS bbsmsgno is a synthetic fingerprint generated from the
            # listing row. Search globally because the same replicated message
            # may be present on W1XSC, W2XSC, W3XSC, and other JNOS BBSs.
            return (
                self.dao.get_inbound_by_bbsmsgno(
                    bbsmsgno=bbsmsgno,
                )
                is not None
            )

        # x138: added for non-JNOS bbs
        return (
            self.dao.get_inbound_by_bbs_locator(
                bbs_call=bbs_call,
                bbsmsgno=bbsmsgno,
            )
            is not None
        )


    # ----------------------------
    #  260801
    #  DEDUPE fingerprint check
    # ----------------------------
    # !!! Legacy JNOS field-comparison method.              !!!
    # !!! No longer used by inbound_exists_for_dedupe().    !!!
    def inbound_exists_jnos_listing_fingerprint(
        self,
        *,
        lm_row: dict,
        area_hint: str = "",
    ) -> bool:
        """
        Determine whether a JNOS listing row matches an inbound message
        already stored from any BBS.

        JNOS message numbers are positional and may differ between BBSs.
        Replicated messages are therefore matched using:

            - original sent month and day
            - normalized sender
            - subject
            - message length

        The BBS call and bulletin area are intentionally not included so
        the same replicated message is recognized across different JNOS BBSs.
        """
        mon = (
            lm_row.get("date_mon")
            or lm_row.get("month")
            or ""
        )
        mon = str(mon).strip()

        day = (
            lm_row.get("date_day")
            or lm_row.get("day")
            or ""
        )
        day = str(day).strip()

        subj = " ".join(
            str(lm_row.get("subject") or "").strip().split()
        )

        frm = (
            lm_row.get("from")
            or lm_row.get("from_call")
            or ""
        )
        frm = str(frm).strip().strip("<>").upper()

        # Cross-BBS JNOS messages may show different domains:
        #
        #   XSCEOC@W1XSC.AMPR.ORG
        #   XSCEOC@W4XSC.SCC-ARES-RACES.ORG
        #
        # For duplicate comparison, retain only the local sender name.
        if "@" in frm:
            frm = frm.split("@", 1)[0].strip()

        raw_size = (
            lm_row.get("size")
            or lm_row.get("bytes")
            or lm_row.get("messagelen")
            or ""
        )

        try:
            msg_size = int(str(raw_size).strip())
        except (TypeError, ValueError):
            # Without a usable size, do not risk skipping a valid message.
            return False

        if not mon or not day or not frm or not subj:
            # An incomplete listing row is not safe for cross-BBS dedupe.
            return False

        return self.dao.inbound_exists_jnos_listing_fingerprint(
            lm_month=mon,
            lm_day=day,
            lm_subject=subj,
            lm_from=frm,
            lm_size=msg_size,
        )
