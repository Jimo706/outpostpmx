# dialogs/message_form_window.py
from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from widgets.message_editor import (
    MessageEditorWidget,
    MessageMode,
    AppConfigContract,
)
from services.message_service import MessageService, MessagePayload, TransportMeta
from services.message_print_service import MessagePrintService, PrintableMessage
from ui.theme import (
    MENU_BAR_STYLE,
    toolbar_style,
    apply_base_main_window_style,
)

from services.message_settings import (
    load_message_settings,
    allocate_next_mid,
)


class MessageFormMode:
    NEW = "new"
    OPEN = "open"


class MessageFormWindow(QtWidgets.QMainWindow):
    """
    QMainWindow host for the OutpostX Message Form.

    Phase 1:
    - Hosts MessageEditorWidget as the central widget.
    - Adds menu bar, toolbar, and status bar.
    - Supports NEW and OPEN modes.
    - Does not yet replace ComposeMessageDialog/ViewMessageDialog.
    """

    saved = QtCore.Signal(int)
    sent = QtCore.Signal(int)
    deleted = QtCore.Signal(int)
    replied = QtCore.Signal(int)
    replied_all = QtCore.Signal(int)
    forwarded = QtCore.Signal(int)

    def __init__(
        self,
        *,
        mode: str,
        service: MessageService,
        config: Optional[AppConfigContract] = None,
        message_id: Optional[int] = None,
        payload: Optional[MessagePayload] = None,
        transport: Optional[TransportMeta] = None,
        printable_message: Optional[PrintableMessage] = None,
        system_config=None,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self._mode = mode
        self._service = service
        self._config = config
        self._message_id = message_id
        self._printable_message = printable_message
        self._system_config = system_config

        self.setObjectName("MessageFormWindow")
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self.setWindowTitle("New Message" if mode == MessageFormMode.NEW else "Message")

        apply_base_main_window_style(self)

        editor_mode = (
            MessageMode.VIEW
            if mode == MessageFormMode.OPEN
            else MessageMode.COMPOSE
        )

        self.editor = MessageEditorWidget(
            mode=editor_mode,
            config=self._config,
            parent=self,
        )
        self.setCentralWidget(self.editor)

        self.editor.txtBody.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.editor.txtBody.customContextMenuRequested.connect(
            self._show_body_context_menu
        )

        # required to set up for accessing the signature
        ctx = None
        if self._system_config is not None:
            try:
                ctx = self._system_config.get_signature_context()
            except Exception:
                ctx = None

        self.editor.set_signature_context(ctx)
        self.editor.set_hosted_in_mainwindow(True)
        self._load_editor_defaults()                # loads the BBS dropdown 
        self._apply_message_settings_defaults()     # ensures MID is set in the subject line

        if payload is not None:
            self.editor.set_message(payload, transport)

        self.editor.set_message_id(message_id)

        self._build_actions()
        self._build_menubar()
        self._build_toolbar()
        self._build_statusbar()
        self._apply_mode()

        # legacy/editor cancel signal still closes the host window if anything inside the editor emits canceled
        self.editor.canceled.connect(self.close)

        self.editor.cbBbs.currentTextChanged.connect(self._update_statusbar)
        self.editor.edFrom.textChanged.connect(self._update_statusbar)
        self.editor.edTo.textChanged.connect(self._update_statusbar)
        self.editor.edSubject.textChanged.connect(self._update_statusbar)

        self.editor.cbType.currentTextChanged.connect(self._update_statusbar)
        self.editor.chkUrgent.toggled.connect(self._update_statusbar)
        self.editor.chkReqDeliv.toggled.connect(self._update_statusbar)
        self.editor.chkReqRead.toggled.connect(self._update_statusbar)
        self.editor.chkBase64.toggled.connect(self._update_statusbar)

        self.editor.txtBody.textChanged.connect(self._update_statusbar)

        # restores saved geometry/window state.
        if self._config:
            self._config.restore_window_state(self, "MessageFormWindow")

        # initializes the status bar once after the window is constructed and any payload/defaults have been loaded.
        self._update_statusbar()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_actions(self) -> None:

        # Menu > File
        self.actSend = QtGui.QAction("&Send", self)
        self.actSend.setShortcut("Ctrl+Return")
        self.actSave = QtGui.QAction("&Save", self)
        self.actSave.setShortcut("Ctrl+S")

        self.actPrint = QtGui.QAction("&Print…", self)
        self.actPrint.setShortcut("Ctrl+P")
        self.actPrintPreview = QtGui.QAction("Print Pre&view…", self)
        self.actPrintNoHeaders = QtGui.QAction("Print, &No Headers…", self)

        self.actClose = QtGui.QAction("&Close", self)
        self.actClose.setShortcut("Esc")

        # Menu > Edit
        self.actCut = QtGui.QAction("Cu&t", self)
        self.actCut.setShortcut("Ctrl+X")
        self.actCopy = QtGui.QAction("&Copy", self)
        self.actCopy.setShortcut("Ctrl+C")
        self.actPaste = QtGui.QAction("&Paste", self)
        self.actPaste.setShortcut("Ctrl+V")
        self.actSelectAll = QtGui.QAction("Select &All", self)
        self.actSelectAll.setShortcut("Ctrl+A")

        # Menu > Action
        self.actReply = QtGui.QAction("&Reply", self)
        self.actReply.setShortcut("Ctrl+R")
        self.actReplyAll = QtGui.QAction("Reply &All", self)
        self.actReplyAll.setShortcut("Ctrl+Shift+R")
        self.actForward = QtGui.QAction("&Forward", self)
        self.actForward.setShortcut("Ctrl+F")
        self.actDelete = QtGui.QAction("&Delete", self)

        self.actTypePrivate = QtGui.QAction("Set as Private", self)
        self.actTypeBulletin = QtGui.QAction("Set as Bulletin", self)
        self.actTypeNts = QtGui.QAction("Set as NTS", self)

        self.actResendSameMid = QtGui.QAction("Same Message ID", self)
        self.actResendNewMid = QtGui.QAction("New Message ID", self)

        self.actUrgent = QtGui.QAction("Urgent", self)
        self.actUrgent.setCheckable(True)
        self.actReqDeliv = QtGui.QAction("Request Delivery Receipt", self)
        self.actReqDeliv.setCheckable(True)
        self.actBase64 = QtGui.QAction("Encode Base64", self)
        self.actBase64.setCheckable(True)

        self.actAddSignature = QtGui.QAction("Insert Signature", self)
        self.actAddSignature.setShortcut("Ctrl+J")

        self.actFontSmaller = QtGui.QAction("A-", self)
        self.actFontBigger = QtGui.QAction("A+", self)

        # wired connects
        self.actSend.triggered.connect(self._on_send)
        self.actSave.triggered.connect(self._on_save)
        self.actPrintPreview.triggered.connect(self._on_print_preview)
        self.actPrint.triggered.connect(lambda: self._on_print(include_headers=True))
        self.actPrintNoHeaders.triggered.connect(lambda: self._on_print(include_headers=False))
        self.actClose.triggered.connect(self._on_close)

        self.actCut.triggered.connect(self.editor.txtBody.cut)
        self.actCopy.triggered.connect(self.editor.txtBody.copy)
        self.actPaste.triggered.connect(self.editor.txtBody.paste)
        self.actSelectAll.triggered.connect(self.editor.txtBody.selectAll)

        self.actReply.triggered.connect(lambda: self._on_reply(reply_all=False))
        self.actReplyAll.triggered.connect(lambda: self._on_reply(reply_all=True))
        self.actForward.triggered.connect(self._on_forward)
        self.actDelete.triggered.connect(self._on_delete)

        self.actResendSameMid.triggered.connect(self._on_resend_same_mid)
        self.actResendNewMid.triggered.connect(self._on_resend_new_mid)

        self.actTypePrivate.triggered.connect(lambda: self.editor.cbType.setCurrentText("private"))
        self.actTypeBulletin.triggered.connect(lambda: self.editor.cbType.setCurrentText("bulletin"))
        self.actTypeNts.triggered.connect(lambda: self.editor.cbType.setCurrentText("nts"))

        self.actUrgent.triggered.connect(lambda checked: self.editor.chkUrgent.setChecked(checked))
        self.actReqDeliv.triggered.connect(lambda checked: self.editor.chkReqDeliv.setChecked(checked))
        self.actBase64.triggered.connect(lambda checked: self.editor.chkBase64.setChecked(checked))
        self.actAddSignature.triggered.connect(self.editor._on_add_signature)        

        self.actFontSmaller.triggered.connect(lambda: self.editor._nudge_font(-1))
        self.actFontBigger.triggered.connect(lambda: self.editor._nudge_font(+1))


    def _build_menubar(self) -> None:
        mb = self.menuBar()
        mb.setStyleSheet(MENU_BAR_STYLE)

        m_file = mb.addMenu("&File")
        m_file.addAction(self.actSend)
        m_file.addAction(self.actSave)
        m_file.addSeparator()
        m_file.addAction(self.actPrintPreview)
        m_file.addAction(self.actPrint)
        m_file.addAction(self.actPrintNoHeaders)        
        m_file.addSeparator()
        m_file.addAction(self.actClose)

        m_edit = mb.addMenu("&Edit")
        m_edit.addAction(self.actCut)
        m_edit.addAction(self.actCopy)
        m_edit.addAction(self.actPaste)
        m_edit.addSeparator()
        m_edit.addAction(self.actSelectAll)

        m_actions = mb.addMenu("&Actions")
        m_actions.addAction(self.actReply)
        m_actions.addAction(self.actReplyAll)
        m_actions.addAction(self.actForward)
        m_actions.addAction(self.actDelete)
        m_resend = m_actions.addMenu("Resend")
        m_resend.addAction(self.actResendSameMid)
        m_resend.addAction(self.actResendNewMid)
        m_actions.addSeparator()
        m_actions.addAction(self.actTypePrivate)
        m_actions.addAction(self.actTypeBulletin)
        m_actions.addAction(self.actTypeNts)
        m_actions.addSeparator()
        m_actions.addAction(self.actUrgent)
        m_actions.addAction(self.actReqDeliv)
        m_actions.addAction(self.actBase64)
        m_actions.addSeparator()
        m_actions.addAction(self.actAddSignature)

        m_help = mb.addMenu("&Help")
        m_help.addAction(QtGui.QAction("Message Form Help", self))

    def _build_toolbar(self) -> None:
        tb = self.addToolBar("Message")
        tb.setObjectName("MessageFormToolbar")
        tb.setStyleSheet(toolbar_style("MessageFormToolbar"))
        tb.setMovable(False)

        tb.addAction(self.actSend)
        tb.addAction(self.actSave)
        tb.addAction(self.actPrintPreview)
        tb.addAction(self.actPrint)

        tb.addSeparator()
        tb.addAction(self.actReply)
        tb.addAction(self.actReplyAll)
        tb.addAction(self.actForward)

        tb.addSeparator()
        tb.addAction(self.actDelete)
        tb.addAction(self.actClose)

        tb.addSeparator()
        tb.addAction(self.actFontSmaller)
        tb.addAction(self.actFontBigger)


    def _build_statusbar(self) -> None:
        self.lblStatus = QtWidgets.QLabel(self)
        self.lblCount = QtWidgets.QLabel(self)

        self.lblStatus.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)

        self.statusBar().addWidget(self.lblStatus, 1)
        self.statusBar().addPermanentWidget(self.lblCount)


    # ------------------------------------------------------------------
    # Mode/state
    # ------------------------------------------------------------------
    def _apply_mode(self) -> None:
        """mode rules"""
        is_new = self._mode == MessageFormMode.NEW
        is_open = self._mode == MessageFormMode.OPEN

        # File actions
        self.actSend.setEnabled(is_new)
        self.actSave.setEnabled(is_new)
        self.actPrintPreview.setEnabled(True)
        self.actPrint.setEnabled(True)
        self.actPrintNoHeaders.setEnabled(True)
        self.actClose.setEnabled(True)

        # Edit actions
        self.actCut.setEnabled(is_new)
        self.actCopy.setEnabled(True)
        self.actPaste.setEnabled(is_new)
        self.actSelectAll.setEnabled(True)

        # Message actions
        self.actReply.setEnabled(is_open)
        self.actReplyAll.setEnabled(is_open and self._has_reply_all_targets())
        self.actForward.setEnabled(is_open)
        self.actDelete.setEnabled(self._message_id is not None)
        self.actResendSameMid.setEnabled(is_open and self._message_id is not None)
        self.actResendNewMid.setEnabled(is_open and self._message_id is not None)

        # NEW-only controls
        for act in (
            self.actTypePrivate,
            self.actTypeBulletin,
            self.actTypeNts,
            self.actUrgent,
            self.actReqDeliv,
            self.actBase64,
            self.actAddSignature,
        ):
            act.setEnabled(is_new)


    def _update_statusbar(self) -> None:
        body_len = len(self.editor.txtBody.toPlainText())

        mode_label = "NEW" if self._mode == MessageFormMode.NEW else "OPEN"
        msg_type = self.editor.cbType.currentText().upper()

        flags = []
        if self.editor.chkUrgent.isChecked():
            flags.append("Urgent")
        if self.editor.chkReqDeliv.isChecked():
            flags.append("Request Delivery Receipt")
        if self.editor.chkReqRead.isChecked():
            flags.append("RR")
        if self.editor.chkBase64.isChecked():
            flags.append("Encode Base64")

        flag_text = ", ".join(flags) if flags else "no flags"
        dirty_text = "modified" if self.editor.is_dirty() else "saved"

        self.lblStatus.setText(
            f"{mode_label} Message  |  Type: {msg_type}  |  {flag_text}  |  {dirty_text}"
        )
        self.lblCount.setText(f"{body_len} chars")

        # Keep checkable menu actions visually synchronized
        self.actUrgent.setChecked(self.editor.chkUrgent.isChecked())
        self.actReqDeliv.setChecked(self.editor.chkReqDeliv.isChecked())
        self.actBase64.setChecked(self.editor.chkBase64.isChecked())

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _current_printable_message(self) -> PrintableMessage:
        if self._printable_message is not None:
            return self._printable_message

        payload = self.editor.collect_payload()

        title_call = payload.from_call or ""
        return PrintableMessage(
            title_call=title_call,
            from_call=payload.from_call,
            to_call=payload.to_call,
            sent_at="",
            subject=payload.subject,
            local_msg_id="",
            body=payload.body,
        )

    def _on_print(self, *, include_headers: bool) -> None:
        msg = self._current_printable_message()

        MessagePrintService(self).print_message(
            msg,
            include_headers=include_headers,
            printer_name=self._selected_printer_name(),
        )

    def _on_print_preview(self) -> None:
        msg = self._current_printable_message()

        MessagePrintService(self).preview_message(
            msg,
            include_headers=True,
            printer_name=self._selected_printer_name(),
        )

    def _show_body_context_menu(self, pos) -> None:
        menu = QtWidgets.QMenu(self)

        # -----------------------------------------
        # Edit actions
        # -----------------------------------------
        if self._mode == MessageFormMode.NEW:
            menu.addAction(self.actCut)

        menu.addAction(self.actCopy)

        if self._mode == MessageFormMode.NEW:
            menu.addAction(self.actPaste)

        menu.addSeparator()
        menu.addAction(self.actSelectAll)

        # -----------------------------------------
        # Message actions
        # -----------------------------------------
        menu.addSeparator()

        if self._mode == MessageFormMode.NEW:
            menu.addAction(self.actSend)
            menu.addAction(self.actSave)
        else:
            menu.addAction(self.actReply)
            menu.addAction(self.actReplyAll)
            menu.addAction(self.actForward)

        # -----------------------------------------
        # Print/Delete/Close
        # -----------------------------------------
        menu.addSeparator()

        menu.addAction(self.actPrint)
        menu.addAction(self.actDelete)
        menu.addAction(self.actClose)

        menu.exec(self.editor.txtBody.mapToGlobal(pos))


    # -----------------------------------------
    # Reply All Helpers
    # -----------------------------------------
    def _has_reply_all_targets(self) -> bool:
        to_text = self.editor.lblTo.text() if self._mode == MessageFormMode.OPEN else self.editor.edTo.text()
        parts = [p.strip() for p in to_text.replace(";", ",").split(",") if p.strip()]
        return len(parts) > 1


    # -----------------------------------------
    # 
    # -----------------------------------------
    def _on_save(self) -> None:
        payload = self.editor.collect_payload()
        msg_id = self._service.save_draft(payload, self._message_id)
        self._message_id = msg_id
        self.editor.set_message_id(msg_id)
        self.saved.emit(msg_id)
        self._apply_mode()
        self.statusBar().showMessage("Message saved.", 3000)
        self.editor.mark_clean()
        self._update_statusbar()

    def _on_send(self) -> None:
        ok, err = self.editor.validate()
        if not ok:
            QtWidgets.QMessageBox.warning(self, "Cannot Send", err)
            return
        self.editor.mark_clean()

        payload = self.editor.collect_payload()
        msg_id = self._service.queue_send(payload, self._message_id)
        self._message_id = msg_id
        self.editor.set_message_id(msg_id)
        self.sent.emit(msg_id)
        self.close()

    def _on_delete(self) -> None:
        if self._message_id is None:
            self.close()
            return

        resp = QtWidgets.QMessageBox.question(
            self,
            "Delete message?",
            "Move this message to Trash?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if resp != QtWidgets.QMessageBox.Yes:
            return

        self._service.delete_to_trash(self._message_id)
        self.deleted.emit(self._message_id)
        self.close()

    def _on_reply(self, *, reply_all: bool) -> None:
        if self._message_id is None:
            return

        new_id = self._service.make_reply(self._message_id, reply_all=reply_all)
        if reply_all:
            self.replied_all.emit(new_id)
        else:
            self.replied.emit(new_id)

    def _on_close(self) -> None:
        self.close()

    def _on_forward(self) -> None:
        if self._message_id is None:
            return

        make_forward = getattr(self._service, "make_forward", None)
        if callable(make_forward):
            new_id = make_forward(self._message_id)
        else:
            new_id = self._service.make_reply(self._message_id, reply_all=False)

        self.forwarded.emit(new_id)


    def _selected_printer_name(self) -> str:
        if self._config is None:
            return ""
        return (self._config.get("Printing/defaultPrinter", "") or "").strip()


    # ------------------------------------------------------------------
    # BBS editor dropdown helpers
    # ------------------------------------------------------------------
    def _load_editor_defaults(self) -> None:
        """
        Load editor defaults from MessageService.

        Applies mainly to NEW messages:
        - BBS dropdown list
        - default From callsign
        """
        try:
            bbs_calls, default_from = self._service.defaults()
        except Exception:
            bbs_calls, default_from = [], ""

        if bbs_calls:
            self.editor.cbBbs.clear()
            self.editor.cbBbs.addItems(bbs_calls)

        if default_from and not self.editor.edFrom.text().strip():
            self.editor.edFrom.setText(default_from)

    # ----------------------------------
    # message ID helpers
    # ----------------------------------
    def _apply_message_settings_defaults(self) -> None:
        """
        Apply global Message Settings defaults to a brand-new NEW message only.

        Existing drafts/replies/forwards pass a payload and must not receive
        a newly allocated Message ID.
        """
        if self._mode != MessageFormMode.NEW:
            return

        if self._message_id is not None:
            return

        if self._config is None:
            return

        settings = load_message_settings(self._config)

        default_to = ""
        if settings.use_default_destination:
            default_to = settings.default_destination or ""

        subject_prefix = ""
        if settings.add_mid_to_outbound:
            prefix = self._active_msg_id_prefix()
            if prefix:
                subject_prefix = allocate_next_mid(self._config, prefix)

        self.editor.apply_compose_defaults(
            default_to=default_to,
            request_delivery_receipt=settings.request_dr,
            subject_prefix=subject_prefix,
        )


    def _active_msg_id_prefix(self) -> str:
        """
        Return active Tactical msg_id_prefix if present, otherwise Station prefix.
        """
        if self._system_config is None:
            return ""

        try:
            tactical = self._system_config.get_active_tactical()
        except Exception:
            tactical = None

        try:
            station = self._system_config.get_active_station()
        except Exception:
            station = None

        tactical_prefix = (getattr(tactical, "msg_id_prefix", "") or "").strip().upper()
        station_prefix = (getattr(station, "msg_id_prefix", "") or "").strip().upper()

        return tactical_prefix or station_prefix

    # -------------------------
    # Resend Helpers
    # -------------------------
    def _on_resend_same_mid(self) -> None:
        if self._message_id is None:
            return

        make_resend = getattr(self._service, "make_resend", None)
        if not callable(make_resend):
            QtWidgets.QMessageBox.warning(
                self,
                "Resend",
                "This message service does not support Resend.",
            )
            return

        new_id = make_resend(self._message_id, new_message_id="")
        self.forwarded.emit(new_id)


    def _on_resend_new_mid(self) -> None:
        if self._message_id is None:
            return

        make_resend = getattr(self._service, "make_resend", None)
        if not callable(make_resend):
            QtWidgets.QMessageBox.warning(
                self,
                "Resend",
                "This message service does not support Resend.",
            )
            return

        new_mid = self._allocate_new_outbound_mid()
        if not new_mid:
            QtWidgets.QMessageBox.warning(
                self,
                "Resend",
                "Unable to allocate a new Message ID. Check Message Settings and active Station/Tactical MID prefix.",
            )
            return

        new_id = make_resend(self._message_id, new_message_id=new_mid)
        self.forwarded.emit(new_id)


    def _allocate_new_outbound_mid(self) -> str:
        if self._config is None:
            return ""

        prefix = self._active_msg_id_prefix()
        if not prefix:
            return ""

        return allocate_next_mid(self._config, prefix)


    # ------------------------------------------------------------------
    # Window lifecycle
    # ------------------------------------------------------------------
    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if self._mode == MessageFormMode.NEW and self.editor.is_dirty():
            resp = QtWidgets.QMessageBox.question(
                self,
                "Close without saving?",
                "You have unsaved changes. Close without saving?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No,
            )
            if resp != QtWidgets.QMessageBox.Yes:
                event.ignore()
                return

        if self._config:
            self._config.save_window_state(self, "MessageFormWindow")

        super().closeEvent(event)