from __future__ import annotations

from typing import Optional

from PySide6 import QtWidgets, QtCore

from services.message_settings import MessageSettings


class MessageSettingsWidget(QtWidgets.QWidget):
    """
    Global Message Settings UI.

    Phase 1:
      - New Messages
      - Message Numbering
      - Message Receipts

    This widget only edits settings. It does not apply message defaults itself.
    """

    changed = QtCore.Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._current_settings: Optional[MessageSettings] = None

        self._build_ui()
        self._wire_signals()
        self._update_controls()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        # --------------------------------------------------------------
        # Group: New Messages
        # --------------------------------------------------------------
        grp_new = QtWidgets.QGroupBox("New Messages", self)
        vn = QtWidgets.QVBoxLayout(grp_new)

        self.chkSendNtsAsPrivate = QtWidgets.QCheckBox(
            "Send NTS messages as Private messages",
            self,
        )

        self.chkUseDefaultDestination = QtWidgets.QCheckBox(
            "Use default destination for new messages",
            self,
        )

        row_dest = QtWidgets.QHBoxLayout()
        row_dest.setContentsMargins(24, 0, 0, 0)
        self.edDefaultDestination = QtWidgets.QLineEdit(self)
        self.edDefaultDestination.setPlaceholderText(
            "e.g. KN6PE, CUPEOC, user@example.org"
        )
        row_dest.addWidget(QtWidgets.QLabel("Default To:", self))
        row_dest.addWidget(self.edDefaultDestination, 1)

        self.lblDestinationHint = QtWidgets.QLabel(
            "Hint: Multiple destinations may be separated with commas or semicolons. "
            "OutpostX stores them as comma-separated addresses.",
            self,
        )
        self.lblDestinationHint.setWordWrap(True)
        self.lblDestinationHint.setContentsMargins(24, 0, 0, 0)

        vn.addWidget(self.chkSendNtsAsPrivate)
        vn.addWidget(self.chkUseDefaultDestination)
        vn.addLayout(row_dest)
        vn.addWidget(self.lblDestinationHint)

        layout.addWidget(grp_new)

        # --------------------------------------------------------------
        # Group: Message Numbering
        # --------------------------------------------------------------
        grp_mid = QtWidgets.QGroupBox("Message Numbering", self)
        vm = QtWidgets.QVBoxLayout(grp_mid)

        self.chkAddMidToOutbound = QtWidgets.QCheckBox(
            "Add Message ID to outbound message subject",
            self,
        )

        self.chkAddMidToInbound = QtWidgets.QCheckBox(
            "Add Message ID to received messages",
            self,
        )

        form_mid = QtWidgets.QFormLayout()
        form_mid.setContentsMargins(24, 0, 0, 0)

        self.spinNextMsgNumber = QtWidgets.QSpinBox(self)
        self.spinNextMsgNumber.setRange(0, 999999)
        self.spinNextMsgNumber.setValue(100)

        self.edMidSeparator = QtWidgets.QLineEdit(self)
        self.edMidSeparator.setMaxLength(4)
        self.edMidSeparator.setPlaceholderText("e.g. -")

        self.edMidSuffix = QtWidgets.QLineEdit(self)
        self.edMidSuffix.setMaxLength(12)
        self.edMidSuffix.setPlaceholderText("e.g. P")

        form_mid.addRow("Next Message Number:", self.spinNextMsgNumber)
        form_mid.addRow("MID Separator:", self.edMidSeparator)
        form_mid.addRow("MID Suffix:", self.edMidSuffix)

        self.lblMidHint = QtWidgets.QLabel(
            "MID format: active station/tactical prefix + separator + number + suffix. "
            "Example: CMV-304P",
            self,
        )
        self.lblMidHint.setWordWrap(True)
        self.lblMidHint.setContentsMargins(24, 0, 0, 0)

        vm.addWidget(self.chkAddMidToOutbound)
        vm.addWidget(self.chkAddMidToInbound)
        vm.addLayout(form_mid)
        vm.addWidget(self.lblMidHint)

        layout.addWidget(grp_mid)

        # --------------------------------------------------------------
        # Group: Message Receipts
        # --------------------------------------------------------------
        grp_receipts = QtWidgets.QGroupBox("Message Receipts", self)
        vr = QtWidgets.QVBoxLayout(grp_receipts)

        self.chkRequestDr = QtWidgets.QCheckBox(
            "Always request a delivery receipt",
            self,
        )

        self.chkSendDr = QtWidgets.QCheckBox(
            "Automatically send delivery receipts for received messages",
            self,
        )

        self.lblReceiptHint = QtWidgets.QLabel(
            "Delivery receipt request tags are applied at Send/Receive time, "
            "not when the message is created.",
            self,
        )
        self.lblReceiptHint.setWordWrap(True)

        vr.addWidget(self.chkRequestDr)
        vr.addWidget(self.chkSendDr)
        vr.addWidget(self.lblReceiptHint)

        layout.addWidget(grp_receipts)
        layout.addStretch(1)

    def _wire_signals(self) -> None:
        self.chkSendNtsAsPrivate.toggled.connect(self._on_changed)
        self.chkUseDefaultDestination.toggled.connect(self._on_default_destination_toggled)
        self.edDefaultDestination.textChanged.connect(self._on_changed)

        self.chkAddMidToOutbound.toggled.connect(self._on_mid_toggled)
        self.chkAddMidToInbound.toggled.connect(self._on_mid_toggled)
        self.spinNextMsgNumber.valueChanged.connect(self._on_changed)
        self.edMidSeparator.textChanged.connect(self._on_changed)
        self.edMidSuffix.textChanged.connect(self._on_changed)

        self.chkRequestDr.toggled.connect(self._on_changed)
        self.chkSendDr.toggled.connect(self._on_changed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def load_from_models(self, settings: MessageSettings) -> None:
        """
        Populate the widget from a MessageSettings instance.
        """
        self._current_settings = settings

        self.chkSendNtsAsPrivate.setChecked(settings.send_nts_as_private)
        self.chkUseDefaultDestination.setChecked(settings.use_default_destination)
        self.edDefaultDestination.setText(settings.default_destination or "")

        self.chkAddMidToOutbound.setChecked(settings.add_mid_to_outbound)
        self.chkAddMidToInbound.setChecked(settings.add_mid_to_inbound)
        self.spinNextMsgNumber.setValue(max(0, int(settings.next_msg_number)))
        self.edMidSeparator.setText(settings.mid_separator or "")
        self.edMidSuffix.setText(settings.mid_suffix or "")

        self.chkRequestDr.setChecked(settings.request_dr)
        self.chkSendDr.setChecked(settings.send_dr)

        self._update_controls()

    def to_settings(self) -> MessageSettings:
        """
        Collect current UI contents into a MessageSettings instance.
        """
        return MessageSettings(
            send_nts_as_private=self.chkSendNtsAsPrivate.isChecked(),
            use_default_destination=self.chkUseDefaultDestination.isChecked(),
            default_destination=self._normalize_destination_display(
                self.edDefaultDestination.text()
            ),

            add_mid_to_outbound=self.chkAddMidToOutbound.isChecked(),
            add_mid_to_inbound=self.chkAddMidToInbound.isChecked(),
            next_msg_number=int(self.spinNextMsgNumber.value()),
            mid_separator=self.edMidSeparator.text(),
            mid_suffix=self.edMidSuffix.text(),

            request_dr=self.chkRequestDr.isChecked(),
            send_dr=self.chkSendDr.isChecked(),
        )

    def validate(self) -> tuple[bool, str]:
        """
        Validate settings before saving.
        """
        if self.chkUseDefaultDestination.isChecked():
            if not self.edDefaultDestination.text().strip():
                return False, "Default Destination is checked, but no destination was entered."

        return True, ""

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _on_changed(self, *args) -> None:
        self.changed.emit()

    def _on_default_destination_toggled(self, _checked: bool) -> None:
        self._update_controls()
        self._on_changed()

    def _on_mid_toggled(self, _checked: bool) -> None:
        self._update_controls()
        self._on_changed()

    def _update_controls(self) -> None:
        use_dest = self.chkUseDefaultDestination.isChecked()
        self.edDefaultDestination.setEnabled(use_dest)

        use_mid = (
            self.chkAddMidToOutbound.isChecked()
            or self.chkAddMidToInbound.isChecked()
        )
        self.spinNextMsgNumber.setEnabled(use_mid)
        self.edMidSeparator.setEnabled(use_mid)
        self.edMidSuffix.setEnabled(use_mid)

    @staticmethod
    def _normalize_destination_display(value: str) -> str:
        """
        Normalize destination separators for display/storage handoff.

        Accept commas or semicolons, return comma+space.
        """
        raw = (value or "").strip()
        if not raw:
            return ""

        parts = []
        for part in raw.replace(";", ",").split(","):
            p = part.strip()
            if p:
                parts.append(p)

        return ", ".join(parts)