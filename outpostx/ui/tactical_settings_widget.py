# ui/tactical_settings_widget.py
from __future__ import annotations

from typing import Optional

from PySide6 import QtWidgets, QtCore, QtGui

from data.tactical_profile_model import TacticalProfile


class TacticalSettingsWidget(QtWidgets.QWidget):
    """Detail editor for a single TacticalProfile.

    Fields
    ------
    Tactical Call Sign  → tactical_call_sign (required, uppercase, pattern)
    Tactical Location   → tactical_location (required, free text)
    Message ID Prefix   → msg_id_prefix (required, uppercase, ≤ 3 chars)
    Signature           → signature (optional multi-line text)

    Signals
    -------
    changed : emitted whenever a field changes (for SetupDialog dirty tracking).
    """

    changed = QtCore.Signal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)

        self._building = False
        self._current: Optional[TacticalProfile] = None

        # ------------------------------------------------------------------
        # Layout
        # ------------------------------------------------------------------
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # --- NEW GROUP BOX FOR TOP THREE FIELDS ---------------------------
        grp_main = QtWidgets.QGroupBox("Tactical ID")
        grp_main.setStyleSheet("QGroupBox { font-weight: bold; }")     # makes label BOLD

        main_layout = QtWidgets.QFormLayout(grp_main)
        main_layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        root.addWidget(grp_main)

        # Replace the old "form" with the new "main_layout"
        form = main_layout

        self.edCall = QtWidgets.QLineEdit()
        self.edLocation = QtWidgets.QLineEdit()
        self.edPrefix = QtWidgets.QLineEdit()

        form.addRow("Tactical Call Sign *:", self.edCall)
        form.addRow("Tactical Location *:", self.edLocation)
        form.addRow("Message ID Prefix *:", self.edPrefix)

        # Signature group
        grp_sig = QtWidgets.QGroupBox("Signature")
        sig_layout = QtWidgets.QVBoxLayout(grp_sig)
        self.txtSignature = QtWidgets.QPlainTextEdit()
        self.txtSignature.setMinimumHeight(80)
        self.txtSignature.setMaximumHeight(120)
        sig_layout.addWidget(self.txtSignature)

        # #176, 260901
        required_note = QtWidgets.QLabel("* Required field")
        required_note.setStyleSheet("font-style: italic;")
        root.addWidget(required_note)

        # Prevent group box from greedily stretching vertically
        policy = grp_sig.sizePolicy()
        policy.setVerticalPolicy(QtWidgets.QSizePolicy.Fixed)
        grp_sig.setSizePolicy(policy)

        root.addWidget(grp_sig)
        root.addStretch(1)

        # Validators – allow upper/lower while typing; normalize on focus-out
        call_re = QtCore.QRegularExpression(r"^[A-Za-z0-9/]+$")
        self._call_validator = QtGui.QRegularExpressionValidator(call_re, self)
        self.edCall.setValidator(self._call_validator)

        prefix_re = QtCore.QRegularExpression(r"^[A-Za-z0-9]{0,3}$")
        self._prefix_validator = QtGui.QRegularExpressionValidator(prefix_re, self)
        self.edPrefix.setValidator(self._prefix_validator)

        # Signals → change tracking
        self.edCall.textChanged.connect(self._on_any_changed)
        self.edLocation.textChanged.connect(self._on_any_changed)
        self.edPrefix.textChanged.connect(self._on_any_changed)
        self.txtSignature.textChanged.connect(self._on_any_changed)

        # Normalize to uppercase on editingFinished (for call + prefix)
        self.edCall.editingFinished.connect(self._normalize_call)
        self.edPrefix.editingFinished.connect(self._normalize_prefix)

    # ------------------------------------------------------------------
    # Load / Save
    # ------------------------------------------------------------------
    def load_profile(self, profile: Optional[TacticalProfile]) -> None:
        """Populate fields from the given profile (or clear for None)."""
        self._building = True
        try:
            self._current = profile
            if profile is None:
                self.edCall.clear()
                self.edLocation.clear()
                self.edPrefix.clear()
                self.txtSignature.clear()
            else:
                self.edCall.setText((profile.tactical_call_sign or "").upper())
                self.edLocation.setText(profile.tactical_location or "")
                self.edPrefix.setText((profile.msg_id_prefix or "").upper())
                self.txtSignature.setPlainText(profile.signature or "")
        finally:
            self._building = False

    def apply_to_profile(self, profile: Optional[TacticalProfile]) -> TacticalProfile:
        """Apply current UI values to the given profile (or a new one)."""
        if profile is None:
            profile = TacticalProfile()

        call = (self.edCall.text() or "").upper().strip()
        loc = (self.edLocation.text() or "").strip()
        prefix = (self.edPrefix.text() or "").upper().strip()
        sig = self.txtSignature.toPlainText() or ""

        if len(prefix) > 3:
            prefix = prefix[:3]

        profile.tactical_call_sign = call
        profile.tactical_location = loc
        profile.msg_id_prefix = prefix
        profile.signature = sig

        return profile

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def validate_required_fields(self) -> list[str]:
        """Return the names of required Tactical ID fields that are blank."""
        missing: list[str] = []

        if not self.edCall.text().strip():
            missing.append("Tactical Call Sign")

        if not self.edLocation.text().strip():
            missing.append("Tactical Location")

        if not self.edPrefix.text().strip():
            missing.append("Message ID Prefix")

        return missing
    

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _on_any_changed(self) -> None:
        if self._building:
            return
        self.changed.emit()

    def _normalize_call(self) -> None:
        if self._building:
            return
        txt = (self.edCall.text() or "").upper().strip()
        self._building = True
        try:
            self.edCall.setText(txt)
        finally:
            self._building = False

    def _normalize_prefix(self) -> None:
        if self._building:
            return
        txt = (self.edPrefix.text() or "").upper().strip()
        if len(txt) > 3:
            txt = txt[:3]
        self._building = True
        try:
            self.edPrefix.setText(txt)
        finally:
            self._building = False
