# widgets.command_entry_edit.py
"""
Command-entry widget for OpTermX.

A small QPlainTextEdit subclass that behaves like a terminal send box:
- Enter sends the current text
- Shift+Enter inserts a newline
- Ctrl-A through Ctrl-Z can be passed through as raw control bytes
- F1-F8 request insertion of active Hot Key text  # 260701: added
- Multi-line paste is preserved
"""

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QPlainTextEdit


class CommandEntryEdit(QPlainTextEdit):
    sendRequested = Signal(str)
    controlCharRequested = Signal(bytes)
    functionKeyRequested = Signal(str)      # NEW: emits "F1" through "F8"

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setPlaceholderText("Command / text to send")
        self.setTabChangesFocus(True)

        # Keep it visually compact like the old QLineEdit.
        fm = self.fontMetrics()
        self.setFixedHeight(int(fm.lineSpacing() * 2.4))

    def keyPressEvent(self, event):
        """
        This gives us:
        Ctrl+C        sends raw Ctrl-C / 0x03
        Shift+Ctrl+C  copies selected text
        Ctrl+V        pastes
        F1-F8         requests active hot key text
        Enter         sends
        Shift+Enter   inserts newline
        """
        modifiers = event.modifiers()
        key = event.key()

        ctrl = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
        shift = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)

        # F1-F8 -> request active Hot Key text.
        # We only intercept plain function keys, not Ctrl/Shift/Alt variants.
        if modifiers == Qt.KeyboardModifier.NoModifier:
            f1 = int(Qt.Key.Key_F1)
            f8 = int(Qt.Key.Key_F8)

            if f1 <= key <= f8:
                key_name = f"F{key - f1 + 1}"
                self.functionKeyRequested.emit(key_name)
                event.accept()
                return

        # Shift+Ctrl+C = normal copy
        if ctrl and shift and key == int(Qt.Key.Key_C):
            self.copy()
            event.accept()
            return

        # Ctrl-V = normal paste
        if ctrl and not shift and key == int(Qt.Key.Key_V):
            super().keyPressEvent(event)
            return

        # Ctrl-A through Ctrl-Z -> raw control byte
        if ctrl and not shift:
            key_a = int(Qt.Key.Key_A)
            key_z = int(Qt.Key.Key_Z)

            if key_a <= key <= key_z:
                value = key - key_a + 1
                self.controlCharRequested.emit(bytes([value]))
                event.accept()
                return

        # Enter sends immediately like a terminal emulator.
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):

            text = self.toPlainText()

            # Empty field -> send bare CR.
            if text.strip() == "":
                self.sendRequested.emit("\r")
            else:
                self.sendRequested.emit(text)

            self.clear()
            event.accept()
            return

        super().keyPressEvent(event)