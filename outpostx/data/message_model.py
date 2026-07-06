# data/message_model.py
"""
Message model.

This module defines the core message dataclasses and enumerations used throughout
OutpostX. It is the canonical *schema contract* between the database layer,
message repositories, Send/Receive logic, and the UI.

Architectural role:
- Defines the in-memory representation of messages and message bodies.
- Mirrors the SQLite `messages` and `message_bodies` tables and the
  `v_messages_full` view.
- Used by MessageDAO for row mapping and by MessageRepository / services
  for lifecycle management.

Design principles:
- Message *headers/metadata* and *bodies* are modeled separately to support
  partial reads and performance optimizations.
- Lifecycle state, direction, and message type are explicit enums to avoid
  ambiguity across layers.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple, Dict, Any


# ----------------------
# Enumerations
# ----------------------
class MessageState(str, Enum):
    """
    Message lifecycle state.

    These states describe *where the message is in its lifecycle*, not how it is
    rendered in the UI.
    """
    NEW = "NEW"
    DRAFT = "DRAFT"
    QUEUED = "QUEUED"
    SENT = "SENT"
    POST_REMOTE = "POST_REMOTE"
    RECEIVED = "RECEIVED"


class Direction(str, Enum):
    """
    Transport direction of the message.
    """
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"


class FormType(str, Enum):
    """
    Structured form / rendering type.
    """
    PLAIN = "PLAIN"
    PACFORM = "PACFORM"
    ICS213 = "ICS213"
    MARS = "MARS"
    NTSF = "NTSF"
    ADDON = "ADDON"


class MessageType(int, Enum):
    """
    BBS-level message classification.
    """
    PRIVATE = 0
    NTS = 1
    BULLETIN = 2


# ----------------------
# Utility conversions
# ----------------------
def _b(i: Optional[int]) -> bool:
    """SQLite int -> bool (None/0 -> False, nonzero -> True)."""
    return bool(i) if i is not None else False


def _i(b: bool) -> int:
    """bool -> SQLite int (True -> 1, False -> 0)."""
    return 1 if b else 0


# ----------------------
# Message (header) model
# ----------------------
@dataclass
class Message:
    """
    Message header and metadata.

    This class represents the `messages` table row. It intentionally excludes
    the message body, which is stored separately in MessageBody.

    Notes
    -----
    * `bbs_call` and `bbsmsgno` uniquely identify an inbound message on a BBS.
    * `messagelen` is maintained by database triggers.
    * Folder assignment and lifecycle state are managed by MessageRepository.
    """
    # Identity (msgidx is DB-assigned PRIMARY KEY)
    msgidx: Optional[int] = None

    # Identity/routing
    bbs_call: str = ""
    bbsmsgno: Optional[str] = None
    from_call: str = ""
    to_call: str = ""
    subject: str = ""

    # Meta
    messagelen: int = 0  # maintained by trigger
    sent_at: Optional[str] = None  # ISO-8601 UTC '...Z'
    rcvd_at: Optional[str] = None  # ISO-8601 UTC '...Z'

    # State
    mstate: MessageState = MessageState.NEW
    direction: Direction = Direction.OUTBOUND

    # Flags
    is_read: bool = False
    is_deleted: bool = False
    is_urgent: bool = False
    is_encoded: bool = False
    is_locked: bool = False
    is_msgdelreq: bool = False
    has_attachment: bool = False  # FUTURE

    # Parsed header (received only)
    header: Optional[str] = None

    # Folder / typing
    folderidx: int = 0
    mtype: MessageType = MessageType.PRIVATE

    # IDs / forms
    messageid: Optional[str] = None
    formtype: FormType = FormType.PLAIN
    recvmsgid: Optional[str] = None

    # Receipts
    is_rdr: bool = False
    is_rrr: bool = False

    # ----------------------
    # Column order for INSERT (matches schema & init script)
    # ----------------------
    INSERT_COLUMNS: Tuple[str, ...] = field(init=False, default=(
        "bbs_call", "bbsmsgno", "from_call", "to_call", "subject", "messagelen",
        "sent_at", "rcvd_at", "mstate", "direction",
        "is_read", "is_deleted", "is_urgent", "is_encoded", "is_locked", "is_msgdelreq", "has_attachment",
        "header", "folderidx", "mtype", "messageid", "formtype", "recvmsgid", "is_rdr", "is_rrr"
    ))

    def to_insert_params(self) -> Tuple[Any, ...]:
        """
        Returns values tuple aligned with INSERT_COLUMNS.
        Note: messagelen is kept by trigger; pass 0 on insert.
        """
        return (
            self.bbs_call, self.bbsmsgno, self.from_call, self.to_call, self.subject, int(self.messagelen or 0),
            self.sent_at, self.rcvd_at, self.mstate.value, self.direction.value,
            _i(self.is_read), _i(self.is_deleted), _i(self.is_urgent), _i(self.is_encoded),
            _i(self.is_locked), _i(self.is_msgdelreq), _i(self.has_attachment),
            self.header, int(self.folderidx), int(self.mtype.value),
            self.messageid, self.formtype.value, self.recvmsgid, _i(self.is_rdr), _i(self.is_rrr)
        )

    def to_update_set_clause(self) -> str:
        """
        Returns a SET clause string for UPDATE excluding msgidx (e.g., 'bbs_call=?, bbsmsgno=?, ...').
        Use with `to_update_params(msgidx)` below.
        """
        return ", ".join(f"{c}=?" for c in self.INSERT_COLUMNS)

    def to_update_params(self, msgidx: int) -> Tuple[Any, ...]:
        """
        Returns parameters for UPDATE ... SET <cols> WHERE msgidx = ?.
        """
        return (*self.to_insert_params(), int(msgidx))

    # ----------------------
    # Row parsers
    # ----------------------
    @classmethod
    def from_messages_row(cls, row: Dict[str, Any]) -> "Message":
        """
        Build from a SELECT against `messages` (no body).
        Expects keys exactly matching column names.
        """
        # Allow sqlite3.Row or dict interchangeably
        if not isinstance(row, dict):
            row = dict(row)

        return cls(
            msgidx=row.get("msgidx"),
            bbs_call=row["bbs_call"],
            bbsmsgno=row.get("bbsmsgno"),
            from_call=row["from_call"],
            to_call=row["to_call"],
            subject=row.get("subject", ""),
            messagelen=int(row.get("messagelen", 0) or 0),
            sent_at=row.get("sent_at"),
            rcvd_at=row.get("rcvd_at"),
            mstate=MessageState(row["mstate"]),
            direction=Direction(row["direction"]),
            is_read=_b(row.get("is_read")),
            is_deleted=_b(row.get("is_deleted")),
            is_urgent=_b(row.get("is_urgent")),
            is_encoded=_b(row.get("is_encoded")),
            is_locked=_b(row.get("is_locked")),
            is_msgdelreq=_b(row.get("is_msgdelreq")),
            has_attachment=_b(row.get("has_attachment")),
            header=row.get("header"),
            folderidx=int(row.get("folderidx", 0) or 0),
            mtype=MessageType(int(row.get("mtype", 0) or 0)),
            messageid=row.get("messageid"),
            formtype=FormType(row["formtype"]),
            recvmsgid=row.get("recvmsgid"),
            is_rdr=_b(row.get("is_rdr")),
            is_rrr=_b(row.get("is_rrr")),
        )

    @classmethod
    def from_full_view_row(cls, row: Dict[str, Any]) -> Tuple["Message", "MessageBody | None"]:
        """
        Build from a SELECT against `v_messages_full` (joined view).
        Returns (Message, MessageBody|None).
        """
        # Allow sqlite3.Row or dict interchangeably
        if not isinstance(row, dict):
            row = dict(row)

        msg = cls.from_messages_row(row)
        body_text = row.get("body")
        body = MessageBody(msgidx=msg.msgidx, message=body_text) if body_text is not None else None
        return msg, body


# ----------------------
# Message body model
# ----------------------
@dataclass
class MessageBody:
    """
    Message body payload.

    One-to-one with Message.id. Contains only the textual body and no lifecycle
    or routing state.
    """
    msgidx: Optional[int]
    message: str

    INSERT_COLUMNS: Tuple[str, ...] = field(init=False, default=("msgidx", "message"))

    def to_insert_params(self) -> Tuple[Any, ...]:
        return (int(self.msgidx) if self.msgidx is not None else None, self.message)
