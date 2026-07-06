# dialogs/view_message_dialog.py
"""Read-only View dialog with Reply/Reply All/Forward/Delete toolbar.

Closes after action (per requirements) and emits the relevant signal with ID.
"""
from __future__ import annotations
from typing import Optional
from PySide6 import QtWidgets, QtCore, QtGui

from widgets.message_editor import (
    MessageEditorWidget, MessageMode, MessagePayload, TransportMeta, AppConfigContract
)
from services.message_service import MessageService
from services.message_print_service import MessagePrintService, PrintableMessage



class ViewMessageDialog(QtWidgets.QDialog):
    deleted = QtCore.Signal(int)
    replied = QtCore.Signal(int)
    replied_all = QtCore.Signal(int)
    forwarded = QtCore.Signal(int)

    def __init__(self,
                 message_id: int,
                 payload: MessagePayload,
                 transport: Optional[TransportMeta],
                 service: MessageService,
                 config: Optional[AppConfigContract] = None,
                 printable_message: PrintableMessage | None = None,
                 parent=None) -> None:
        super().__init__(parent)
        self._message_id = message_id
        self._service = service
        self._config = config
        self._printable_message = printable_message
        self.setWindowTitle("Message")
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)

        self.editor = MessageEditorWidget(mode=MessageMode.VIEW, config=self._config, parent=self)
        self.editor.set_message(payload, transport)
        self.editor.set_message_id(message_id)

        # Extra toolbar for VIEW actions
        bar = QtWidgets.QHBoxLayout(); bar.setContentsMargins(0, 0, 0, 0)
        self.btnReply = QtWidgets.QPushButton("Reply")
        self.btnReplyAll = QtWidgets.QPushButton("Reply All")
        self.btnForward = QtWidgets.QPushButton("Forward")

        self.btnPrintPreview = QtWidgets.QPushButton("Print Preview")
        self.btnPrint = QtWidgets.QPushButton("Print")
        self.btnPrintNoHeaders = QtWidgets.QPushButton("Print No Headers")

        self.btnDelete = QtWidgets.QPushButton("Delete")

        bar.addWidget(self.btnReply)
        bar.addWidget(self.btnReplyAll)
        bar.addWidget(self.btnForward)

        bar.addSpacing(1)
        bar.addWidget(self.btnPrintPreview)
        bar.addWidget(self.btnPrint)
        bar.addWidget(self.btnPrintNoHeaders)

        bar.addStretch(1)
        bar.addWidget(self.btnDelete)

        host = QtWidgets.QVBoxLayout(self)
        host.addLayout(bar)
        host.addWidget(self.editor)

        # wiring
        self.editor.canceled.connect(self.close)
        self.btnReply.clicked.connect(self._on_reply)
        self.btnReplyAll.clicked.connect(self._on_reply_all)
        self.btnForward.clicked.connect(self._on_forward)
        self.btnDelete.clicked.connect(self._on_delete)

        self.btnPrintPreview.clicked.connect(self._on_print_preview)
        self.btnPrint.clicked.connect(self._on_print)
        self.btnPrintNoHeaders.clicked.connect(self._on_print_no_headers)


    # --- window state ---
    def showEvent(self, event):
        super().showEvent(event)
        if self._config:
            self._config.restore_window_state(self, "ViewMessageDialog")

    def closeEvent(self, event):
        if self._config:
            self._config.save_window_state(self, "ViewMessageDialog")
        super().closeEvent(event)

    # --- actions ---
    def _on_reply(self) -> None:
        new_id = self._service.make_reply(self._message_id, reply_all=False)
        self.replied.emit(new_id)
        self.accept()

    def _on_reply_all(self) -> None:
        new_id = self._service.make_reply(self._message_id, reply_all=True)
        self.replied_all.emit(new_id)
        self.accept()

    def _on_forward(self) -> None:
        """
        Forward uses MessageService.make_forward() when available, and falls back
        to make_reply() for older/alternate implementations.
        """
        make_forward = getattr(self._service, "make_forward", None)
        if callable(make_forward):
            new_id = make_forward(self._message_id)
        else:
            # Fallback: behave like a simple reply
            new_id = self._service.make_reply(self._message_id, reply_all=False)

        self.forwarded.emit(new_id)
        self.accept()

    def _on_delete(self) -> None:
        self._service.delete_to_trash(self._message_id)
        self.deleted.emit(self._message_id)
        self.accept()

    def _on_print_preview(self) -> None:
        if not self._printable_message:
            QtWidgets.QMessageBox.warning(
                self,
                "Print Preview",
                "No printable message is available.",
            )
            return

        MessagePrintService(self).preview_message(
            self._printable_message,
            include_headers=True,
            printer_name=self._selected_printer_name(),
        )


    def _on_print(self) -> None:
        if not self._printable_message:
            QtWidgets.QMessageBox.warning(
                self,
                "Print Message",
                "No printable message is available.",
            )
            return

        MessagePrintService(self).print_message(
            self._printable_message,
            include_headers=True,
            printer_name=self._selected_printer_name(),
        )

    def _on_print_no_headers(self) -> None:
        if not self._printable_message:
            QtWidgets.QMessageBox.warning(
                self,
                "Print Message",
                "No printable message is available.",
            )
            return

        MessagePrintService(self).print_message(
            self._printable_message,
            include_headers=False,
            printer_name=self._selected_printer_name(),
        )

    def _selected_printer_name(self) -> str:
        if self._config is None:
            return ""
        return (self._config.get("Printing/defaultPrinter", "") or "").strip()

