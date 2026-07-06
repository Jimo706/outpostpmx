# ui/bbs_logon_settings_widget.py
from __future__ import annotations

from typing import Optional

from PySide6 import QtWidgets, QtCore

from data.bbs_logon_model import BBSLogonProfile


class BBSLogonSettingsWidget(QtWidgets.QWidget):
    """Detail editor for a single BBSLogonProfile.

    Fields
    ------
    BBS Name       → bbs_connect_call (uppercased on focus-out)
    Logon Name     → login_username (uppercased on focus-out)
    Account Passwd → account_password (masked; required)
    Access Passwd  → access_password (masked; optional; Winlink)

    Controls
    --------
    * Show/Hide button: toggles visibility of both password fields.
    * changed signal: emitted on any data change (for SetupDialog dirty tracking).
    """

    changed = QtCore.Signal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)

        self._building = False
        self._current: Optional[BBSLogonProfile] = None
        self._passwords_visible = False

        # ------------------------------------------------------------------
        # Layout
        # ------------------------------------------------------------------
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # --- NEW GROUP BOX FOR TOP THREE FIELDS ---------------------------
        grp_main = QtWidgets.QGroupBox("Logon Credentials")
        grp_main.setStyleSheet("QGroupBox { font-weight: bold; }")     # makes label BOLD

        main_layout = QtWidgets.QFormLayout(grp_main)
        main_layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        root.addWidget(grp_main)

        # Replace the old "form" with the new "main_layout"
        form = main_layout

        self.edBBSName = QtWidgets.QLineEdit()
        self.edLogonName = QtWidgets.QLineEdit()

        self.edAccountPass = QtWidgets.QLineEdit()
        self.edAccountPass.setEchoMode(QtWidgets.QLineEdit.Password)

        self.edAccessPass = QtWidgets.QLineEdit()
        self.edAccessPass.setEchoMode(QtWidgets.QLineEdit.Password)

        form.addRow("BBS Connect Name:", self.edBBSName)
        form.addRow("Logon Name:", self.edLogonName)
        form.addRow("Account Passwd:", self.edAccountPass)
        form.addRow("Access Passwd:", self.edAccessPass)

        # Show/Hide button row INSIDE the group box
        self.btnShowHide = QtWidgets.QPushButton("Show")

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(self.btnShowHide)

        btn_container = QtWidgets.QWidget()
        btn_container.setLayout(btn_row)

        form.addRow("", btn_container)   # <-- add to the group box's form layout

        root.addStretch(1)

        # Signals → dirty tracking
        self.edBBSName.textChanged.connect(self._on_any_changed)
        self.edLogonName.textChanged.connect(self._on_any_changed)
        self.edAccountPass.textChanged.connect(self._on_any_changed)
        self.edAccessPass.textChanged.connect(self._on_any_changed)

        self.edBBSName.editingFinished.connect(self._normalize_bbs_name)
        self.edLogonName.editingFinished.connect(self._normalize_logon_name)

        self.btnShowHide.clicked.connect(self._on_toggle_show_hide)

    # ------------------------------------------------------------------
    # Load / Save
    # ------------------------------------------------------------------
    def load_profile(self, profile: Optional[BBSLogonProfile]) -> None:
        """Populate fields from the given profile (or clear for None)."""
        self._building = True
        try:
            self._current = profile
            if profile is None:
                self.edBBSName.clear()
                self.edLogonName.clear()
                self.edAccountPass.clear()
                self.edAccessPass.clear()
            else:
                self.edBBSName.setText(profile.bbs_connect_call or "")
                self.edLogonName.setText(profile.login_username or "")
                self.edAccountPass.setText(profile.account_password or "")
                self.edAccessPass.setText(profile.access_password or "")
        finally:
            self._building = False
        # Show/Hide state does not affect stored data; no changed signal here.

    def apply_to_profile(self, profile: Optional[BBSLogonProfile]) -> BBSLogonProfile:
        """Apply current UI values to the given profile (or a new one)."""
        if profile is None:
            profile = BBSLogonProfile()

        bbs = (self.edBBSName.text() or "").upper().strip()
        logon = (self.edLogonName.text() or "").upper().strip()
        account = self.edAccountPass.text() or ""
        access = self.edAccessPass.text() or ""

        profile.bbs_connect_call = bbs
        profile.login_username = logon
        profile.account_password = account
        profile.access_password = access

        return profile

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _on_any_changed(self) -> None:
        if self._building:
            return
        self.changed.emit()

    def _normalize_bbs_name(self) -> None:
        if self._building:
            return
        txt = (self.edBBSName.text() or "").upper().strip()
        self._building = True
        try:
            self.edBBSName.setText(txt)
        finally:
            self._building = False

    def _normalize_logon_name(self) -> None:
        if self._building:
            return
        txt = (self.edLogonName.text() or "").upper().strip()
        self._building = True
        try:
            self.edLogonName.setText(txt)
        finally:
            self._building = False

    def _on_toggle_show_hide(self) -> None:
        self._passwords_visible = not self._passwords_visible
        mode = (
            QtWidgets.QLineEdit.Normal
            if self._passwords_visible
            else QtWidgets.QLineEdit.Password
        )
        self.edAccountPass.setEchoMode(mode)
        self.edAccessPass.setEchoMode(mode)
        self.btnShowHide.setText("Hide" if self._passwords_visible else "Show")
