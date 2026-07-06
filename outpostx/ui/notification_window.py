# ui/notification_window.py

"""
Notification Window

Purpose
-------
Display application notifications that should remain visible until the
user closes the window, clears the list, or exits the application.

The window is intentionally simple:

    <Date-Time>: <Severity>, <message>

Example:

    10-Jun 16:42:18: ERROR, Send/Receive failed: could not open COM3

Notifications are supplied by NotificationService. The window does not
own the notification list; it only displays it.
"""
# TODO: capture, save, qnd reset form geometries.

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtGui import QTextOption

from services.notification_service import NotificationService


class NotificationWindow(QtWidgets.QDialog):
    """
    Modeless notification window.

    Behavior:
    - Displays all existing notifications when opened.
    - Appends new notifications as they arrive.
    - Remains open until the user closes it.
    - Does not destroy the NotificationService.
    """

    def __init__(
        self,
        notification_service: NotificationService,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._service = notification_service

        self.setWindowTitle("Notifications")
        self.resize(650, 300)
        self.setMinimumSize(450, 200)

        self._build_ui()
        self._load_existing_notifications()

        # Subscribe after UI is ready.
        self._service.subscribe(self._on_notification_added)

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        self.text = QtWidgets.QPlainTextEdit(self)
        self.text.setReadOnly(True)
        ### self.text.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)

        # Wrap at window width
        self.text.setLineWrapMode(QtWidgets.QPlainTextEdit.WidgetWidth)
        self.text.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)

        font = QtGui.QFont()
        font.setFamily("Courier New")
        font.setStyleHint(QtGui.QFont.Monospace)
        font.setPointSize(9)
        self.text.setFont(font)

        layout.addWidget(self.text, 1)

        btn_row = QtWidgets.QHBoxLayout()

        self.btn_clear = QtWidgets.QPushButton("Clear", self)
        self.btn_close = QtWidgets.QPushButton("Close", self)

        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_clear)
        btn_row.addWidget(self.btn_close)

        layout.addLayout(btn_row)

        self.btn_clear.clicked.connect(self._on_clear)
        self.btn_close.clicked.connect(self.close)

    # ------------------------------------------------------------------
    # Notification Handling
    # ------------------------------------------------------------------
    def _load_existing_notifications(self) -> None:
        """
        Populate the window with notifications that already exist.
        """
        self.text.clear()

        for entry in self._service.messages():
            self.text.appendPlainText(entry)

        self._scroll_to_bottom()

    def _on_notification_added(self, entry: str) -> None:
        """
        Called by NotificationService when a new notification is added.
        """
        self.text.appendPlainText(entry)
        self._scroll_to_bottom()

        # Bring the window forward if it is already visible.
        if self.isVisible():
            self.raise_()
            self.activateWindow()

    def _on_clear(self) -> None:
        """
        Clear notifications from both the service and this window.
        """
        self._service.clear()
        self.text.clear()

    def _scroll_to_bottom(self) -> None:
        """
        Keep the newest notification visible.
        """
        sb = self.text.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ------------------------------------------------------------------
    # Qt Events
    # ------------------------------------------------------------------
    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """
        Unsubscribe from NotificationService when the window closes.

        This prevents callbacks from being sent to a closed/deleted window.
        """
        self._service.unsubscribe(self._on_notification_added)
        super().closeEvent(event)
