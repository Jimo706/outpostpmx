# dialogs/compose_message_dialog.py
# 251207: Compose dialog wiring for MessageEditorWidget.

from __future__ import annotations
from typing import Optional

from PySide6 import QtWidgets, QtCore, QtGui

from widgets.message_editor import MessageEditorWidget, MessageMode
"""from widgets.message_editor import (
    MessageEditorWidget,
    MessageMode,
    MessagePayload,
    TransportMeta,
    AppConfigContract,
)
"""
from services.message_service import MessageService, MessagePayload, TransportMeta
from services.system_config_service import SystemConfigService

# P132
from services.message_settings import (
    load_message_settings,
    allocate_next_mid,
)


class ComposeMessageDialog(QtWidgets.QDialog):
    """
    Dialog hosting the MessageEditorWidget for composing/editing outbound messages.

    Contract freeze:
    This dialog is wiring only. It forwards editor actions (Save/Send/Delete)
    to MessageService and updates the editor with the returned message_id.
    It must not transform MessagePayload fields or implement lifecycle rules;
    those responsibilities belong to MessageService.
    """

    saved = QtCore.Signal(int)    # message_id
    sent = QtCore.Signal(int)     # message_id
    deleted = QtCore.Signal(int)  # message_id

    def __init__(
        self,
        service: MessageService,
        system_config: Optional[SystemConfigService] = None,
        config: Optional[AppConfigContract] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._system_config = system_config
        self._config = config
        self._message_id: Optional[int] = None

        self.setWindowTitle("New Message")
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)

        # --- main editor widget ---
        self.editor = MessageEditorWidget(
            mode=MessageMode.COMPOSE,
            config=self._config,
            parent=self,
        )

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.editor)

        # --- bottom-row controls (Delete) ---
        self.btnDelete = QtWidgets.QPushButton("Delete")
        bottom = QtWidgets.QHBoxLayout()
        bottom.addStretch(1)
        bottom.addWidget(self.btnDelete)
        layout.addLayout(bottom)

        # ------------------------------------------------------------------
        # Preload defaults from MessageService
        # ------------------------------------------------------------------
        # Current contract: defaults() -> (bbs_calls, default_from_call)
        # retrieve the list of all BBS entries (comment: 260109)
        try:
            bbs_calls, default_from = self._service.defaults()
        except NotImplementedError:
            bbs_calls, default_from = [], ""

        # BBS list
        # Load the cbBbs combo box with these items (comment: 260109)
        if bbs_calls:
            self.editor.cbBbs.addItems(bbs_calls)
            # Let index 0 stand:
            # - If there is an active BBS, it was moved to index 0 by EditorProfilesAdapter.
            # - If there is no active BBS, index 0 is a blank entry, so the field is blank.
            # So: no explicit setCurrentIndex here.
            
        # FROM field: only populate when we have a default call
        if default_from:
            self.editor.edFrom.setText(default_from)

        # ------------------------------------------------------------------
        # Signature context (Station/Tactical signatures)
        # ------------------------------------------------------------------
        ctx = None
        if self._system_config is not None:
            try:
                ctx = self._system_config.get_signature_context()
            except Exception:
                ctx = None

        if hasattr(self.editor, "set_signature_context"):
            self.editor.set_signature_context(ctx)


        # ------------------------------------------------------------------
        # Supports adding message setting defaults
        # ------------------------------------------------------------------
        self._apply_message_settings_defaults()

        # ------------------------------------------------------------------
        # Wiring editor actions back into the dialog
        # ------------------------------------------------------------------
        self.editor.setProperty("on_save", self._on_save)
        self.editor.setProperty("on_send", self._on_send)
        self.editor.canceled.connect(self.close)

        # bottom-row Delete
        self.btnDelete.clicked.connect(self._on_delete_clicked)

        # Restore geometry
        if self._config:
            self._config.restore_window_state(self, "ComposeMessageDialog")

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    def _apply_message_settings_defaults(self) -> None:
        """
        Apply global Message Settings defaults to a brand-new compose window.

        Draft edits call load_draft() after construction, so draft contents overwrite
        these defaults. This keeps existing drafts safe.
        """
        if self._config is None:
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




    # 260104, fix for opening a reply message
    # NOTE: Preferred path today is passing payload+transport from MainWindow.
    # Dialog-based loading requires MessageService.load_payload() to be implemented.
    def load_draft(
        self,
        message_id: int,
        payload: Optional[MessagePayload] = None,
        transport: Optional[TransportMeta] = None,
    ) -> None:
        """Load an existing draft by ID into the editor."""
        self._message_id = message_id
    
        # If caller provided the content, use it (avoids calling unimplemented MessageService.load_payload)
        if payload is None or transport is None:
            payload, transport = self._service.load_payload(message_id)

        self.editor.set_message(payload, transport)
        self.editor.set_message_id(message_id)
        self.setWindowTitle("Edit Message")
        self.show()

    # ------------------------------------------------------------------
    # Internals: actions from MessageEditorWidget
    # ------------------------------------------------------------------
    def _on_save(self, payload: MessagePayload, message_id: Optional[int]) -> None:
        """Handle Save from the editor (create or update draft)."""        
        msg_id = self._service.save_draft(payload, self._message_id)
        self._message_id = msg_id
        self.editor.set_message_id(msg_id)
        self.saved.emit(msg_id)

    def _on_send(self, payload: MessagePayload, message_id: Optional[int]) -> None:
        """Handle Send from the editor (queue for send)."""
        msg_id = self._service.queue_send(payload, self._message_id)
        self._message_id = msg_id
        self.editor.set_message_id(msg_id)
        self.sent.emit(msg_id)
        self.accept()  # close after queueing

    def _on_delete_clicked(self) -> None:
        if self._message_id is None:
            # Just close; nothing persisted yet
            self.reject()
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

        try:
            self._service.delete_to_trash(self._message_id)
        finally:
            self.deleted.emit(self._message_id)
            self.accept()

    # ------------------------------------------------------------------
    # Window state
    # ------------------------------------------------------------------
    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if self._config:
            self._config.save_window_state(self, "ComposeMessageDialog")
        super().closeEvent(event)
