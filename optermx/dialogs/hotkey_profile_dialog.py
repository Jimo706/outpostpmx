# dialogs/hotkey_profile_dialog.py

"""
Hot Key Profile dialog for OpTermX.

Allows the user to create, open, save, and delete named F1-F8 hot key profiles.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from services.app_paths import AppPaths
from services.app_info import AppInfo
from services.hotkey_profile_service import HOTKEY_NAMES, HotkeyProfileService


class HotkeyProfileDialog(QDialog):
    def __init__(self, service: HotkeyProfileService, parent=None):
        super().__init__(parent)

        self.service = service
        self._loading = False
        self._dirty = False

        self.setWindowTitle(f"{AppInfo.TITLE} Hot Key Profiles")
        self.setWindowIcon(QIcon(AppPaths.app_icon()))
        self.setMinimumWidth(640)
        self.setModal(True)

        self._build_ui()
        self._wire_events()
        self._load_profile_list()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        title = QLabel("Hot Key Profiles")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        open_row = QHBoxLayout()
        open_row.addWidget(QLabel("Open:"))

        self.cbo_profiles = QComboBox(self)
        open_row.addWidget(self.cbo_profiles, stretch=1)

        root.addLayout(open_row)

        form = QFormLayout()

        self.line_profile_name = QLineEdit(self)
        form.addRow("Profile Name:", self.line_profile_name)

        self.key_edits: dict[str, QLineEdit] = {}

        for key_name in HOTKEY_NAMES:
            edit = QLineEdit(self)
            edit.setPlaceholderText(f"{key_name} text")
            self.key_edits[key_name] = edit
            form.addRow(f"{key_name}:", edit)

        root.addLayout(form)

        button_row = QHBoxLayout()

        self.btn_new = QPushButton("New", self)
        self.btn_delete = QPushButton("Delete", self)
        self.btn_save = QPushButton("Save", self)
        self.btn_close = QPushButton("Close", self)

        button_row.addWidget(self.btn_new)
        button_row.addWidget(self.btn_delete)
        button_row.addStretch()
        button_row.addWidget(self.btn_save)
        button_row.addWidget(self.btn_close)

        root.addLayout(button_row)

    def _wire_events(self) -> None:
        self.cbo_profiles.currentTextChanged.connect(self._on_profile_selected)

        self.line_profile_name.textChanged.connect(self._mark_dirty)

        for edit in self.key_edits.values():
            edit.textChanged.connect(self._mark_dirty)

        self.btn_new.clicked.connect(self._new_profile)
        self.btn_delete.clicked.connect(self._delete_profile)
        self.btn_save.clicked.connect(self._save_profile)
        self.btn_close.clicked.connect(self.close)

    def _load_profile_list(self) -> None:
        self._loading = True

        self.cbo_profiles.clear()
        self.cbo_profiles.addItems(self.service.profile_names())

        active = self.service.active_profile
        if active:
            idx = self.cbo_profiles.findText(active)
            if idx >= 0:
                self.cbo_profiles.setCurrentIndex(idx)

        self._loading = False

        current = self.cbo_profiles.currentText()
        if current:
            self._load_profile(current)
        else:
            self._clear_fields()

        self._dirty = False

    def _load_profile(self, name: str) -> None:
        profile = self.service.get_profile(name)

        if profile is None:
            self._clear_fields()
            return

        self._loading = True

        self.line_profile_name.setText(profile.name)

        for key_name in HOTKEY_NAMES:
            self.key_edits[key_name].setText(profile.keys.get(key_name, ""))

        self._loading = False
        self._dirty = False

    def _clear_fields(self) -> None:
        self._loading = True

        self.line_profile_name.clear()

        for edit in self.key_edits.values():
            edit.clear()

        self._loading = False
        self._dirty = False

    def _mark_dirty(self) -> None:
        if not self._loading:
            self._dirty = True

    def _confirm_discard_changes(self) -> bool:
        if not self._dirty:
            return True

        result = QMessageBox.question(
            self,
            "Unsaved Changes",
            "This profile has unsaved changes. Discard them?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        return result == QMessageBox.StandardButton.Yes

    def _on_profile_selected(self, name: str) -> None:
        if self._loading:
            return

        if not name:
            return

        if not self._confirm_discard_changes():
            return

        try:
            self.service.set_active_profile(name)
        except ValueError:
            pass

        self._load_profile(name)

    def _new_profile(self) -> None:
        if not self._confirm_discard_changes():
            return

        self.cbo_profiles.setCurrentIndex(-1)
        self._clear_fields()
        self.line_profile_name.setFocus()
        self._dirty = True

    def _delete_profile(self) -> None:
        name = self.line_profile_name.text().strip()

        if not name:
            return

        result = QMessageBox.question(
            self,
            "Delete Hot Key Profile",
            f"Delete hot key profile '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if result != QMessageBox.StandardButton.Yes:
            return

        self.service.delete_profile(name)
        self._load_profile_list()

    def _save_profile(self) -> None:
        name = self.line_profile_name.text().strip()

        if not name:
            QMessageBox.warning(
                self,
                "Hot Key Profile",
                "Profile name cannot be blank.",
            )
            return

        keys = {
            key_name: self.key_edits[key_name].text()
            for key_name in HOTKEY_NAMES
        }

        try:
            self.service.save_profile(name, keys)
        except Exception as e:
            QMessageBox.warning(
                self,
                "Hot Key Profile",
                f"Could not save profile:\n{e}",
            )
            return

        self._load_profile_list()

        idx = self.cbo_profiles.findText(name)
        if idx >= 0:
            self.cbo_profiles.setCurrentIndex(idx)

        self._dirty = False

    def closeEvent(self, event) -> None:
        if self._confirm_discard_changes():
            event.accept()
        else:
            event.ignore()