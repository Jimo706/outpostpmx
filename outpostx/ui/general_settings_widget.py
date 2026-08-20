from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtWidgets


class GeneralSettingsWidget(QtWidgets.QWidget):
    """
    General OutpostX application preferences.

    These are global application preferences, not named profiles.
    """

    changed = QtCore.Signal()

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)

        self._building = False

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # --------------------------------------------------------------
        # Startup
        # --------------------------------------------------------------
        grp_startup = QtWidgets.QGroupBox("Startup")
        grp_startup.setStyleSheet(
            "QGroupBox { font-weight: bold; }"
        )

        layout = QtWidgets.QVBoxLayout(grp_startup)

        self.chk_start_in_inbox = QtWidgets.QCheckBox(
            "Start in Inbox"
        )

        layout.addWidget(self.chk_start_in_inbox)

        root.addWidget(grp_startup)
        root.addStretch(1)

        # Dirty tracking
        self.chk_start_in_inbox.toggled.connect(
            self._on_changed
        )

    def load_settings(self, settings) -> None:
        """
        Load General preferences from QSettings.
        """
        self._building = True
        try:
            value = settings.value(
                "General/start_in_inbox",
                False,
                type=bool,
            )
            self.chk_start_in_inbox.setChecked(value)
        finally:
            self._building = False

    def save_settings(self, settings) -> None:
        """
        Save General preferences to QSettings.
        """
        settings.setValue(
            "General/start_in_inbox",
            self.chk_start_in_inbox.isChecked(),
        )

    def _on_changed(self) -> None:
        if self._building:
            return

        self.changed.emit()