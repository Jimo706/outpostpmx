    # widgets/message_editor.py
# 251207: Production-ready editor; adds Add Signature button & signature context
"""Message editor/viewer widget (production-ready)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from datetime import datetime

from PySide6 import QtWidgets, QtCore, QtGui
from services.message_service import MessagePayload, TransportMeta

# P132
from services.message_settings import (
    load_message_settings,
    allocate_next_mid,
)
# P139
from services.datetime_display import format_timestamp


class MessageMode:
    """Simple enum-like holder for editor modes."""
    COMPOSE = "compose"
    EDIT_DRAFT = "edit_draft"
    VIEW = "view"


class AppConfigContract:
    """
    Minimal interface for AppConfig as used by this widget.

    The real AppConfig implements these methods using QSettings.
    """

    def save_window_state(self, widget: QtWidgets.QWidget, key: str) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def restore_window_state(self, widget: QtWidgets.QWidget, key: str) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def get(self, key: str, default=None):
        raise NotImplementedError

    def set(self, key: str, value):
        raise NotImplementedError


class MessageEditorWidget(QtWidgets.QWidget):
    """
    Composite widget that provides the full message editor UI.

    Contract freeze:
    - The editor is UI-only: it does not persist messages or manage folder/state.
    - It emits user actions as (MessagePayload, message_id) to a configured handler.
    - Persistence + lifecycle (draft/save/queue/send/trash) are owned by MessageService.
    - The editor may normalize display (e.g., uppercasing calls) but must not apply
      business rules beyond basic validation.
    """


    saved = QtCore.Signal(int)    # message_id for drafts
    sent = QtCore.Signal(int)     # message_id for queued
    canceled = QtCore.Signal()    # editor closed without sending/saving

    def __init__(
        self,
        mode: MessageMode = MessageMode.COMPOSE,
        config: Optional[AppConfigContract] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._mode = mode
        self._config = config
        self._dirty = False
        self._message_id: Optional[int] = None
        self._signature_ctx: Optional[dict[str, str]] = None

        self._build_ui()
        self._connect_signals()
        self.set_mode(mode)
        self._restore_font_size()

    # ---------- UI BUILD ----------
    def _build_ui(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # Toolbar row
        tb = QtWidgets.QHBoxLayout()
        tb.setContentsMargins(0, 0, 0, 0)

        self.btnSend = QtWidgets.QPushButton("Send")
        self.btnSave = QtWidgets.QPushButton("Save")

        # New: Add Signature button
        self.btnAddSignature = QtWidgets.QPushButton("Add Signature")
        self.btnAddSignature.setEnabled(False)

        self.btnClose = QtWidgets.QPushButton("Close")
        self.btnClose.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )

        # Font size controls
        self.btnFontSmaller = QtWidgets.QPushButton("A")
        self.btnFontBigger = QtWidgets.QPushButton("A")
        self.btnFontSmaller.setFixedWidth(25)               # set the button width
        self.btnFontBigger.setFixedWidth(25)                # set the button width
        f_small = self.btnFontSmaller.font()
        f_small.setPointSizeF(max(6.0, f_small.pointSizeF() * 0.9))
        self.btnFontSmaller.setFont(f_small)
        f_big = self.btnFontBigger.font()
        f_big.setPointSizeF(max(6.5, f_big.pointSizeF() * 1.25))
        self.btnFontBigger.setFont(f_big)

        tb.addWidget(self.btnSend)
        tb.addWidget(self.btnSave)
        tb.addWidget(self.btnAddSignature)

        tb.addStretch(1)

        right_tools = QtWidgets.QWidget()
        right_layout = QtWidgets.QHBoxLayout(right_tools)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        right_layout.addWidget(self.btnClose)
        right_layout.addWidget(self.btnFontSmaller)
        right_layout.addWidget(self.btnFontBigger)

        right_tools.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )

        tb.addWidget(right_tools)
        root.addLayout(tb)

        # Send group
        self.grpSend = QtWidgets.QGroupBox("Send")
        g = QtWidgets.QGridLayout(self.grpSend)         # creates a  grid of (row, column)
        g.setColumnStretch(1, 1)
        g.setColumnStretch(3, 1)

        self.cbBbs = QtWidgets.QComboBox()
        self.cbBbs.setEditable(True)            # makes the field editable
        self.edFrom = QtWidgets.QLineEdit()
        self.edTo = QtWidgets.QLineEdit()
        self.edSubject = QtWidgets.QLineEdit()
        self.cbType = QtWidgets.QComboBox()
        self.cbType.addItems(["private", "bulletin", "nts"])

        self.chkUrgent = QtWidgets.QCheckBox("Urgent")
        self.chkReqDeliv = QtWidgets.QCheckBox("Req Deliv Rcpt")
        self.chkReqRead = QtWidgets.QCheckBox("Req Read Rcpt")
        self.chkBase64 = QtWidgets.QCheckBox("Base64")

        row = 0
        g.addWidget(QtWidgets.QLabel("BBS:"), row, 0)
        g.addWidget(self.cbBbs, row, 1, 1, 3)

        # Widget	    Grid Position
        # ---------------------------
        # "From:" label	(row, 0)
        # self.edFrom	(row, 1)
        # "To:" label	(row, 1)
        # self.edTo	    (row, 1)
        row += 1
        g.addWidget(QtWidgets.QLabel("From:"), row, 0)
        g.addWidget(self.edFrom, row, 1, 1, 3)

        row += 1
        g.addWidget(QtWidgets.QLabel("To:"), row, 0)
        g.addWidget(self.edTo, row, 1, 1, 3)

        row += 1
        g.addWidget(QtWidgets.QLabel("Subject:"), row, 0)
        g.addWidget(self.edSubject, row, 1, 1, 3)

        row += 1
        self.lblTypeEdit = QtWidgets.QLabel("Type:")
        g.addWidget(self.lblTypeEdit, row, 0)

        g.addWidget(self.cbType, row, 1)
        g.addWidget(self.chkUrgent, row, 2)
        g.addWidget(self.chkReqDeliv, row, 3)

        row += 1
        g.addWidget(self.chkReqRead, row, 2)
        g.addWidget(self.chkBase64, row, 3)

        root.addWidget(self.grpSend)

        # Meta group (used in VIEW mode)
        self.grpMeta = QtWidgets.QGroupBox("Message Info")
        gm = QtWidgets.QGridLayout(self.grpMeta)
        gm.setColumnStretch(1, 1)
        gm.setColumnStretch(3, 1)

        self.lblBbs = QtWidgets.QLabel()
        self.lblFrom = QtWidgets.QLabel()
        self.lblTo = QtWidgets.QLabel()
        self.lblSubject = QtWidgets.QLabel()
        self.lblType = QtWidgets.QLabel()

        # OPEN-only supplemental display labels
        self.lblDateTime = QtWidgets.QLabel()
        self.lblLocalMid = QtWidgets.QLabel()

        # Let operators copy displayed metadata if needed.
        for lbl in (
            self.lblBbs,
            self.lblFrom,
            self.lblTo,
            self.lblSubject,
            self.lblType,
            self.lblDateTime,
            self.lblLocalMid,
        ):
            lbl.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)

        row = 0
        # DEF:  addWidget(widget, row, column, rowSpan, columnSpan)
        gm.addWidget(QtWidgets.QLabel("BBS:"), row, 0)
        gm.addWidget(self.lblBbs, row, 1)
        gm.addWidget(self.lblDateTime, row, 2, 1, 2)

        row += 1
        gm.addWidget(QtWidgets.QLabel("From:"), row, 0)
        gm.addWidget(self.lblFrom, row, 1)
        gm.addWidget(self.lblLocalMid, row, 2, 1, 2)

        row += 1
        gm.addWidget(QtWidgets.QLabel("To:"), row, 0)
        gm.addWidget(self.lblTo, row, 1, 1, 3)

        row += 1
        gm.addWidget(QtWidgets.QLabel("Subject:"), row, 0)
        gm.addWidget(self.lblSubject, row, 1, 1, 3)

        row += 1
        gm.addWidget(QtWidgets.QLabel("Type:"), row, 0)
        gm.addWidget(self.lblType, row, 1, 1, 3)

        root.addWidget(self.grpMeta)

        # Body
        self.txtBody = QtWidgets.QTextEdit()
        # 260429: Set Message text for monospace font 
        body_font = QtGui.QFont("Consolas", 10)
        body_font.setStyleHint(QtGui.QFont.StyleHint.Monospace)
        self.txtBody.setFont(body_font)   # adjust name to your widget
        self.txtBody.setLineWrapMode(QtWidgets.QTextEdit.LineWrapMode.WidgetWidth)  # was .NoWrap

        self.txtBody.setAcceptRichText(False)
        root.addWidget(self.txtBody, 1)

        # basic line edit validators (uppercase callsigns)
        self._upper_callsign_validator = QtGui.QRegularExpressionValidator(
            QtCore.QRegularExpression(r"^[A-Za-z0-9@._+\-,;]+$")
        )
        self.edFrom.setValidator(self._upper_callsign_validator)
        self.edTo.setValidator(self._upper_callsign_validator)

        # 260122, add support for normalizing call sign and email addresses
        self.edTo.editingFinished.connect(
            lambda: self.edTo.setText(
                self._normalize_addresses(self.edTo.text())
            )
        )

        self.edFrom.editingFinished.connect(
            lambda: self.edFrom.setText(
                self._normalize_addresses(self.edFrom.text())
            )
        )


    def _connect_signals(self) -> None:
        # toolbar
        self.btnSend.clicked.connect(self._on_send)
        self.btnSave.clicked.connect(self._on_save)
        self.btnAddSignature.clicked.connect(self._on_add_signature)
        self.btnClose.clicked.connect(self._on_close)
        self.btnFontSmaller.clicked.connect(lambda: self._nudge_font(-1))
        self.btnFontBigger.clicked.connect(lambda: self._nudge_font(+1))

        # body change tracking
        self.txtBody.textChanged.connect(self._mark_dirty)
        # 260514, P134
        # adds validation check ot more than body text field
        self.cbBbs.currentTextChanged.connect(self._mark_dirty)
        self.edFrom.textChanged.connect(self._mark_dirty)
        self.edTo.textChanged.connect(self._mark_dirty)
        self.edSubject.textChanged.connect(self._mark_dirty)

        # dirty tracking: message controls
        self.cbType.currentTextChanged.connect(self._mark_dirty)
        self.chkUrgent.toggled.connect(self._mark_dirty)
        self.chkReqDeliv.toggled.connect(self._mark_dirty)
        self.chkBase64.toggled.connect(self._mark_dirty)


    # ---------- MODE & PAYLOAD ----------
    def set_mode(self, mode: MessageMode) -> None:
        """Switch between COMPOSE / EDIT_DRAFT / VIEW modes."""
        self._mode = mode
        is_comp = mode in (MessageMode.COMPOSE, MessageMode.EDIT_DRAFT)
        is_view = mode == MessageMode.VIEW

        self.grpSend.setVisible(is_comp)        # is Compose
        self.grpMeta.setVisible(is_view)        # is View (As in received/sent msgs)

        for w in (
            self.cbBbs,
            self.edFrom,
            self.edTo,
            self.edSubject,
            self.cbType,
            self.chkUrgent,
        ):
            w.setEnabled(not is_view)

        self.txtBody.setReadOnly(is_view)
        self.btnSend.setVisible(is_comp)
        self.btnSave.setVisible(is_comp)
        self.btnAddSignature.setVisible(is_comp)

    # -------------------------------
    #  date/time, LMI format helpers
    # -------------------------------
    # p139
    def _format_display_datetime(self, value: str) -> str:
        return format_timestamp(value, include_seconds=False).display

    def _build_open_datetime_text(self, transport: Optional[TransportMeta]) -> str:
        """
        Build OPEN-form date/time display text.

        Rules:
        - SENT:     Sent: <sent_at>
        - RECEIVED: Sent: <sent_at> | Rec'd: <rcvd_at>
        - NEW/DRAFT/QUEUED/other: blank
        """
        if not transport:
            return ""

        state = (getattr(transport, "message_state", "") or "").strip().upper()
        sent_at = self._format_display_datetime(getattr(transport, "sent_at", "") or "")
        rcvd_at = self._format_display_datetime(getattr(transport, "rcvd_at", "") or "")

        if state == "SENT":
            return f"Sent: {sent_at}" if sent_at else ""

        if state == "RECEIVED":
            parts = []
            if sent_at:
                parts.append(f"Sent: {sent_at}")
            if rcvd_at:
                parts.append(f"Rec'd: {rcvd_at}")
            return " | ".join(parts)

        return ""



    def set_message_id(self, message_id: Optional[int]) -> None:
        """Remember the DB-backed message id (or None for new)."""
        self._message_id = message_id

    def apply_compose_defaults(
        self,
        *,
        default_to: str = "",
        request_delivery_receipt: bool = False,
        subject_prefix: str = "",
    ) -> None:
        """
        Apply Message Settings defaults to a NEW compose message only.
        """
        if self._mode != MessageMode.COMPOSE:
            return

        if default_to and not self.edTo.text().strip():
            self.edTo.setText(self._normalize_addresses(default_to))

        if request_delivery_receipt:
            self.chkReqDeliv.setChecked(True)

        if subject_prefix and not self.edSubject.text().strip():
            self.edSubject.setText(subject_prefix)

        self._dirty = False


    def set_signature_context(self, ctx: Optional[dict]) -> None:
        """Configure which signature (if any) the Add Signature button should append.

        Expected dict (from SystemConfigService.get_signature_context):

            {
                "station_signature": str,
                "tactical_signature": str,
                "preferred": "tactical" | "station" | "",
            }
        """
        self._signature_ctx = ctx or {}
        preferred = (self._signature_ctx.get("preferred") or "").strip()

        has_sig = bool(preferred)
        if hasattr(self, "btnAddSignature"):
            self.btnAddSignature.setEnabled(has_sig)


    def _normalize_addresses(self, text: str) -> str:
        """
        Normalize one or more addresses.

        Accepts a single address or a comma-separated list.

        Rules per address:
          - callsign-only => uppercase
          - email-style   => lowercase

        Output is a comma+space separated list.
        """
        raw = (text or "").strip()
        if not raw:
            return raw

        parts = [
            p.strip()
            for p in raw.replace(";", ",").split(",")
            if p.strip()
        ]

        norm = []
        for p in parts:
            if "@" in p:
                norm.append(p.lower())
            elif len(p) <= 6:
                norm.append(p.upper())
            else:
                norm.append(p.upper())  # or leave unchanged if tactical names may be longer

        return "; ".join(norm)


    def set_message(
        self,
        msg: MessagePayload,
        transport: Optional[TransportMeta] = None,
    ) -> None:
        """Populate the fields from a MessagePayload + optional transport meta."""

        # Normalize key header fields (BBS / FROM / TO) to uppercase for display
        # print(f">>>DEBUG: message_editor.MEWidget.set_message.msg.bbs_name = {msg.bbs_name}")
        self.cbBbs.setCurrentText((msg.bbs_name or "").upper())
        self.edFrom.setText((msg.from_call or "").upper())
        # remove .upper() from the to_call
        to_text = self._normalize_addresses(msg.to_call or "")
        self.edTo.setText(to_text  or "")
        self.edSubject.setText(msg.subject)

        # Type & flags
        t = (msg.type or "private").lower()
        idx = self.cbType.findText(t)
        if idx < 0:
            idx = 0
        self.cbType.setCurrentIndex(idx)

        self.chkUrgent.setChecked(bool(msg.urgent))
        self.chkReqDeliv.setChecked(bool(msg.req_delivery_rcpt))
        self.chkReqRead.setChecked(bool(msg.req_read_rcpt))
        self.chkBase64.setChecked(bool(msg.base64_encode))

        # Body
        self.txtBody.setPlainText(msg.body or "")
        self._dirty = False

        # Meta group for VIEW
        self.lblBbs.setText((msg.bbs_name or "").upper())
        self.lblFrom.setText((msg.from_call or "").upper())
        # remove .upper() from the to_call
        self.lblTo.setText(to_text or "")
        self.lblSubject.setText(msg.subject)
        self.lblType.setText(t)


        # Supplemental OPEN-form metadata: date/time and Local MID.
        date_text = self._build_open_datetime_text(transport)
        self.lblDateTime.setText(date_text)
        self.lblDateTime.setVisible(bool(date_text))

        local_mid = ""
        if transport:
            state = (getattr(transport, "message_state", "") or "").strip().upper()
            if state == "RECEIVED":
                local_mid = (getattr(transport, "local_msg_id", "") or "").strip()

        mid_text = f"Local MID: {local_mid}" if local_mid else ""
        self.lblLocalMid.setText(mid_text)
        self.lblLocalMid.setVisible(bool(mid_text))


    # Core API methods used by dialogs
    def collect_payload(self) -> MessagePayload:
        """
        Collect the current contents of the editor into a MessagePayload.

        BBS / FROM / TO are normalized to uppercase to match typical packet practice.
        """
        # remove .upper() from the to_call
        to_text = self._normalize_addresses(self.edTo.text())
        return MessagePayload(
            bbs_name=self.cbBbs.currentText().strip().upper(),
            from_call=self.edFrom.text().strip().upper(),
            to_call=to_text,
            ### to_call=self.edTo.text().strip(),
            subject=self.edSubject.text().strip(),
            body=self.txtBody.toPlainText(),
            type=self.cbType.currentText().lower(),
            urgent=self.chkUrgent.isChecked(),
            req_delivery_rcpt=self.chkReqDeliv.isChecked(),
            req_read_rcpt=self.chkReqRead.isChecked(),
            base64_encode=self.chkBase64.isChecked(),
        )

    def validate(self) -> tuple[bool, str]:
        """
        Basic validation for sending.

        You can tighten these rules later if needed.
        """
        if not self.cbBbs.currentText().strip():
            return False, "BBS is required."
        if not self.edFrom.text().strip():
            return False, "From is required."
        if not self.edTo.text().strip():
            return False, "To is required."
        if not self.edSubject.text().strip():
            return False, "Subject is required."
        return True, ""

    # ---------- BUTTON SLOTS ----------
    def _on_send(self) -> None:
        ok, err = self.validate()
        if not ok:
            QtWidgets.QMessageBox.warning(self, "Cannot Send", err)
            return

        handler = self.property("on_send")
        if not callable(handler):
            # No handler = programming/config error; keep dirty so user gets warned
            QtWidgets.QMessageBox.critical(
                self,
                "Cannot Send",
                "Internal error: no send handler is configured.",
            )
            return

        try:
            handler(self.collect_payload(), self._message_id)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(
                self,
                "Send Failed",
                f"An error occurred while sending the message:\n{exc}",
            )
            return

        self._dirty = False

    def _on_save(self) -> None:
        handler = self.property("on_save")
        if not callable(handler):
            QtWidgets.QMessageBox.critical(
                self,
                "Cannot Save",
                "Internal error: no save handler is configured.",
            )
            return

        try:
            handler(self.collect_payload(), self._message_id)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(
                self,
                "Save Failed",
                f"An error occurred while saving the message:\n{exc}",
            )
            return

        self._dirty = False

    def _on_add_signature(self) -> None:
        """Append the configured signature to the message body."""
        if not self._signature_ctx:
            return

        preferred = (self._signature_ctx.get("preferred") or "").strip()
        if preferred == "tactical":
            sig = self._signature_ctx.get("tactical_signature") or ""
        elif preferred == "station":
            sig = self._signature_ctx.get("station_signature") or ""
        else:
            return

        sig = sig.strip()
        if not sig:
            return

        self._append_signature_to_body(sig)

    def _append_signature_to_body(self, signature: str) -> None:
        """
        Append the configured signature to the message body.

        #128/260808:
        Do not add the same signature more than once.
        """
        sig = (signature or "").strip()
        if not sig:
            return

        body = self.txtBody.toPlainText()

        # Signature already present -- do not append it again.
        if sig in body:
            return

        body = body.rstrip()

        if body:
            body = body + "\n\n" + sig
        else:
            body = sig

        self.txtBody.setPlainText(body)
        # Move cursor to start so the user can keep typing
        cursor = self.txtBody.textCursor()
        cursor.movePosition(QtGui.QTextCursor.Start)    # 128, was .End
        self.txtBody.setTextCursor(cursor)
        self.txtBody.setFocus()

        self._dirty = True


    def _on_close(self) -> None:
        if self._dirty and self._mode in (MessageMode.COMPOSE, MessageMode.EDIT_DRAFT):
            resp = QtWidgets.QMessageBox.question(
                self,
                "Close without saving?",
                "You have unsaved changes. Close without saving?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No,
            )
            if resp != QtWidgets.QMessageBox.Yes:
                return
        self.canceled.emit()
        self.close()

    # -------------------------------
    # Apply Message Setting defaults
    # -------------------------------
    def apply_compose_defaults(
        self,
        *,
        default_to: str = "",
        request_delivery_receipt: bool = False,
        subject_prefix: str = "",
    ) -> None:
        """
        Apply Message Settings defaults to a NEW compose message only.

        This is intentionally called by the compose-dialog owner, not by the
        editor constructor, so replies/forwards/drafts are not accidentally changed.
        """
        if self._mode != MessageMode.COMPOSE:
            return

        if default_to and not self.edTo.text().strip():
            self.edTo.setText(self._normalize_addresses(default_to))

        if request_delivery_receipt:
            self.chkReqDeliv.setChecked(True)

        if subject_prefix and not self.edSubject.text().strip():
            self.edSubject.setText(subject_prefix)

        self._dirty = False

    def _apply_message_settings_to_new_compose(self, editor) -> None:
        if not self._config:
            return

        settings = load_message_settings(self._config)

        default_to = ""
        if settings.use_default_destination:
            default_to = settings.default_destination or ""

        # P132
        subject_prefix = ""
        if settings.add_mid_to_outbound:
            prefix = self._active_msg_id_prefix()
            if prefix:
                subject_prefix = allocate_next_mid(self._config, prefix)

        editor.apply_compose_defaults(
            default_to=default_to,
            request_delivery_receipt=settings.request_dr,
            subject_prefix=subject_prefix,
        )

    def _active_msg_id_prefix(self) -> str:
        """
        Return the active Tactical msg_id_prefix if present, otherwise Station prefix.
        """
        if not self._system_config:
            return ""

        tactical = self._system_config.get_active_tactical()
        station = self._system_config.get_active_station()

        tactical_prefix = (getattr(tactical, "msg_id_prefix", "") or "").strip().upper()
        station_prefix = (getattr(station, "msg_id_prefix", "") or "").strip().upper()

        return tactical_prefix or station_prefix


    # ---------- DIRTY TRACKING & PERSISTENCE ----------
    def _mark_dirty(self) -> None:
        self._dirty = True

    def is_dirty(self) -> bool:
        """Return True if the user has modified the form since last save/load."""
        return self._dirty

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if self._config:
            self._config.save_window_state(self, "MessageEditor")
            self._save_font_size()
        super().closeEvent(event)

    # ---------- FONT HANDLING ----------
    def _prefer_font(self, names: list[str]) -> QtGui.QFont:
        """Try to pick a font from a preference list, falling back gracefully."""
        fam = QtGui.QFont()
        for name in names:
            fam.setFamily(name)
            if QtGui.QFontInfo(fam).family().lower() == name.lower():
                return fam
        return QtGui.QFont()

    def _nudge_font(self, delta: int) -> None:
        f = self.txtBody.font()
        sz = f.pointSizeF()
        if sz <= 0:
            sz = 10.0
        sz = max(6.0, min(24.0, sz + delta))
        f.setPointSizeF(sz)
        self.txtBody.setFont(f)
        self._save_font_size()

    def _save_font_size(self) -> None:
        if not self._config:
            return
        f = self.txtBody.font()
        self._config.set("MessageEditor/fontPointSize", f.pointSizeF())

    def _restore_font_size(self) -> None:
        if not self._config:
            return
        sz = self._config.get("MessageEditor/fontPointSize", None)
        if sz is None:
            return
        f = self.txtBody.font()
        f.setPointSizeF(float(sz))
        self.txtBody.setFont(f)


    # ----------------------------------------------
    # Message form Integration 
    # 260514, P134
    # ----------------------------------------------
    def set_hosted_in_mainwindow(self, enabled: bool) -> None:
        """
        Hide embedded command buttons when this editor is hosted by MessageFormWindow.

        The QMainWindow owns Send/Save/Close/Font actions through menus and toolbars.
        Old dialog hosts can continue showing the embedded buttons.

        # NOTE:
        # These handlers are retained only for legacy dialog hosts.
        # MessageFormWindow does not use them; it owns Send/Save/Close actions directly.
        """
        visible = not enabled

        self.btnSend.setVisible(visible)
        self.btnSave.setVisible(visible)
        self.btnClose.setVisible(visible)
        self.btnFontSmaller.setVisible(visible)
        self.btnFontBigger.setVisible(visible)
        self.btnAddSignature.setVisible(visible)

        self.chkUrgent.setVisible(visible)
        self.chkReqDeliv.setVisible(visible)
        self.chkReqRead.setVisible(visible)
        self.chkBase64.setVisible(visible)        

        self.cbType.setVisible(visible)
        self.lblTypeEdit.setVisible(visible)


    def mark_clean(self) -> None:
        """Mark the editor as clean after a successful save/send/load."""
        self._dirty = False

