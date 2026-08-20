# ui/message_table_model.py, 251112
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from PySide6 import QtCore, QtGui

from data.message_model import (
    Message,
    MessageBody,
    Direction,
    MessageState,
    MessageType,
)
from data.message_repo import MessageRepository

# P139
from services.datetime_display import format_timestamp

@dataclass
class RowItem:
    msg: Message
    body: Optional[MessageBody]


class MessageTableModel(QtCore.QAbstractTableModel):
    """
    Columns:
      0 State
      1 Dir
      2 BBS
      3 From
      4 To
      5 Local MID      (recvmsgid)
      6 Subject        (bold when unread)
      7 Time           (rcvd_at for INBOUND; sent_at if SENT; 'none' if DRAFT/QUEUED)
      8 Size           (messagelen)
    """
    COLS = ("State", "Type", "BBS", "From", "To", "Local MID", "Subject", "Time", "Size")

    def __init__(self, repo: Optional[MessageRepository], parent: Optional[QtCore.QObject] = None):
        super().__init__(parent)
        self._repo = repo
        self._folderidx: Optional[int] = None
        self._rows: List[RowItem] = []
        self._sort_col = 7    # default: Time
        self._sort_asc = False

    # ---- public api ----
    def set_folder(self, folderidx: int):
        self._folderidx = folderidx
        self.refresh()

    def refresh(self):
        if self._repo is None or self._folderidx is None:
            return
        items: List[Tuple[Message, Optional[MessageBody]]] = self._repo.list_by_folder(
            self._folderidx, include_deleted=False, only_unread=False, limit=2000
        )
        self.beginResetModel()
        self._rows = [RowItem(m, b) for (m, b) in items]
        self._sort_internal()
        self.endResetModel()

    def item_at(self, row: int) -> Optional[RowItem]:
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None

    # ---- model impl ----
    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.COLS)

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if orientation == QtCore.Qt.Orientation.Horizontal and role == QtCore.Qt.DisplayRole:
            return self.COLS[section]
        return None

    def flags(self, index: QtCore.QModelIndex):
        if not index.isValid():
            return QtCore.Qt.NoItemFlags
        # drag source; selection handled in the view
        return QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsDragEnabled


    def _time_text(self, msg: Message) -> str:
        if msg.mstate in (MessageState.DRAFT, MessageState.QUEUED):
            return "none"

        return format_timestamp(
            msg.rcvd_at or msg.sent_at or "",
            include_seconds=False,
        ).display


        if msg.direction == Direction.INBOUND:
            # Prefer BBS posted time; fall back to download time
            return msg.sent_at or msg.rcvd_at or "none"

        # OUTBOUND & not Draft/Queued
        return msg.sent_at or "none"

    def _type_text(self, msg: Message) -> str:
        if msg.mtype == MessageType.BULLETIN:
            return "B"
        elif msg.mtype == MessageType.NTS:
            return "NTS"
        else:
            return ""        # or "-" if you prefer

    def _subject_sort_key(self, subject: str) -> str:
        """
        #96, 260812
        Return a normalized subject used only for sorting.

        RE:, FW:, and FWD: prefixes are ignored so replies and forwards
        sort with the original base subject.

        Examples:
            "ARES Meeting"            -> "ARES MEETING"
            "RE: ARES Meeting"        -> "ARES MEETING"
            "FW: ARES Meeting"        -> "ARES MEETING"
            "RE: FW: ARES Meeting"    -> "ARES MEETING"
        """
        text = (subject or "").strip()

        while True:
            normalized = re.sub(
                r"^(RE|FW|FWD|DELIVERED)\s*:\s*",
                "",
                text,
                flags=re.IGNORECASE,
            )

            if normalized == text:
                break

            text = normalized.strip()

        return text.upper()


    def data(self, index: QtCore.QModelIndex, role=QtCore.Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        msg = row.msg
        col = index.column()

        if role == QtCore.Qt.DisplayRole:
            if col == 0: return msg.mstate.value
            # if col == 1: return "IN" if msg.direction == Direction.INBOUND else "OUT"
            if col == 1: return self._type_text(msg)
            if col == 2: return msg.bbs_call
            if col == 3: return msg.from_call
            if col == 4: return msg.to_call
            if col == 5: return msg.recvmsgid or ""
            if col == 6: return msg.subject or ""
            if col == 7: return self._time_text(msg)
            if col == 8: return str(msg.messagelen or 0)

        # Highlight urgent messages in red
        if role == QtCore.Qt.ForegroundRole and msg.is_urgent:
            return QtGui.QBrush(QtGui.QColor("red"))

        # Bold unread subject
        # if role == QtCore.Qt.FontRole and col == 6 and not msg.is_read:   # bold col 6 only
        if role == QtCore.Qt.FontRole and not msg.is_read:                  # bold the entire row
            f = QtGui.QFont()
            f.setBold(True)
            return f

        # Sorting keys
        if role == QtCore.Qt.UserRole:
            if col == 0: return msg.mstate.value
            # if col == 1: return 0 if msg.direction == Direction.INBOUND else 1
            if col == 1: return self._type_text(msg)
            if col == 2: return msg.bbs_call or ""
            if col == 3: return msg.from_call or ""
            if col == 4: return msg.to_call or ""
            if col == 5: return msg.recvmsgid or ""
            if col == 6: return self._subject_sort_key(msg.subject)     # #96
            if col == 7: return (msg.sent_at or msg.rcvd_at or "")
            if col == 8: return int(msg.messagelen or 0)
        return None

    # ---- sorting ----
    def sort(self, column: int, order: QtCore.Qt.SortOrder = QtCore.Qt.AscendingOrder):
        self._sort_col = column
        self._sort_asc = (order == QtCore.Qt.AscendingOrder)
        self.layoutAboutToBeChanged.emit()
        self._sort_internal()
        self.layoutChanged.emit()

    def _sort_internal(self):
        key = lambda ri: self._sort_key_for_col(ri, self._sort_col)
        self._rows.sort(key=key, reverse=not self._sort_asc)

    def _sort_key_for_col(self, ri: RowItem, col: int):
        msg = ri.msg
        if col == 0: return msg.mstate.value
        # if col == 1: return 0 if msg.direction == Direction.INBOUND else 1
        if col == 1:  return self._type_text(msg)
        if col == 2: return msg.bbs_call or ""
        if col == 3: return msg.from_call or ""
        if col == 4: return msg.to_call or ""
        if col == 5: return msg.recvmsgid or ""

        if col == 6:                             # #96; sort by base subject, then chronologically, then by original subject
            return (
                self._subject_sort_key(msg.subject),
                msg.sent_at or msg.rcvd_at or "",
                msg.subject or "",
            )

        if col == 7: return self._time_text(msg) or ""
        if col == 8: return int(msg.messagelen or 0)
        return 0

    # ---- drag MIME (msgidx list) ----
    def supportedDragActions(self) -> QtCore.Qt.DropActions:
        return QtCore.Qt.CopyAction | QtCore.Qt.MoveAction

    def mimeTypes(self):
        return ["application/x-outpostx-msgids"]

    def mimeData(self, indexes):
        mids = []
        seen = set()
        for idx in indexes:
            r = idx.row()
            if r in seen:
                continue
            seen.add(r)
            ri = self.item_at(r)
            if ri and ri.msg.msgidx is not None:
                mids.append(str(int(ri.msg.msgidx)))
        md = QtCore.QMimeData()
        md.setData("application/x-outpostx-msgids", ",".join(mids).encode("utf-8"))
        return md
