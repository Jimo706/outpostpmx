from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtGui import QShortcut, QKeySequence

from data.bbs_profile_model import BBSProfile
from data.bbs_profile_repo import BBSProfileRepository
from data.interface_profile_model import InterfaceProfile
from data.interface_profile_repo import InterfaceProfileRepository
from data.station_profile_model import StationProfile
from data.station_profile_repo import StationProfileRepository
from data.tactical_profile_model import TacticalProfile
from data.tactical_profile_repo import TacticalProfileRepository
from data.bbs_logon_model import BBSLogonProfile
from data.bbs_logon_repo import BBSLogonRepository

from ui.bbs_settings_widget import BBSSettingsWidget
from data.node_path_repo import NodePathRepo
from data.node_path_model import NodePath
from services.node_path_executor import NodePathExecutor
from ui.interface_setup_widget import InterfaceSetupWidget
from ui.station_settings_widget import StationSettingsWidget
from ui.tactical_settings_widget import TacticalSettingsWidget
from ui.bbs_logon_settings_widget import BBSLogonSettingsWidget
from ui.send_receive_settings_widget import SendReceiveSettingsWidget

from services.system_config_service import SystemConfigService, ActiveSelection
from services.send_receive_settings import (
    load_send_receive_settings,
    save_send_receive_settings,
    AutomationMode,
)

from app_config import AppConfig

from ui.message_settings_widget import MessageSettingsWidget
from services.message_settings import (
    load_message_settings,
    save_message_settings,
)



class SetupDialog(QtWidgets.QDialog):
    """OutpostX Setup / Preferences dialog."""

    def __init__(
        self,
        db_path: Path | str,
        config: Optional[AppConfig] = None,
        system_config: Optional[SystemConfigService] = None,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("OutpostX Setup")
        self.resize(1100, 650)
        self.setMinimumSize(745, 500)

        # repositories
        self._bbs_repo = BBSProfileRepository(db_path)
        self._node_path_repo = NodePathRepo(db_path)
        self._node_path_executor = NodePathExecutor(self)
        self._iface_repo = InterfaceProfileRepository(db_path)
        self._station_repo = StationProfileRepository(db_path)
        self._tactical_repo = TacticalProfileRepository(db_path)
        self._bbs_logon_repo = BBSLogonRepository(db_path)

        self._config = config
        self._system_config = system_config
        self._dirty = False
        # 260730, Issue x133:
        # Track the last successfully displayed area and configuration row.
        # These are used to restore the list selection when the user chooses
        # not to discard unsaved changes.
        self._previous_area_row = -1
        self._previous_config_row = -1

        self._current_bbs: Optional[BBSProfile] = None
        self._current_interface: Optional[InterfaceProfile] = None
        self._current_station: Optional[StationProfile] = None
        self._current_tactical: Optional[TacticalProfile] = None
        self._current_bbs_logon: Optional[BBSLogonProfile] = None

        main = QtWidgets.QVBoxLayout(self)

        # ESC behaves like Cancel
        esc = QShortcut(QKeySequence(QtCore.Qt.Key_Escape), self)
        esc.activated.connect(self._on_cancel)

        # ------------------------------------------------------------------
        # Toolbar
        # ------------------------------------------------------------------
        toolbar = QtWidgets.QHBoxLayout()
        self.btn_new = QtWidgets.QPushButton("New")
        self.btn_copy = QtWidgets.QPushButton("Copy")
        self.btn_delete = QtWidgets.QPushButton("Delete")
        self.btn_activate = QtWidgets.QPushButton("Activate")
        self.btn_save = QtWidgets.QPushButton("Save")
        self.btn_cancel = QtWidgets.QPushButton("Close")

        for btn in (
            self.btn_new,
            self.btn_copy,
            self.btn_delete,
            self.btn_activate,
            self.btn_save,
            self.btn_cancel,
        ):
            toolbar.addWidget(btn)
        toolbar.addStretch(1)
        main.addLayout(toolbar)

        # ------------------------------------------------------------------
        # Three columns
        # ------------------------------------------------------------------
        cols = QtWidgets.QHBoxLayout()
        main.addLayout(cols, 1)

        # Column 1: Setup Areas
        self.lst_areas = QtWidgets.QListWidget()
        self.lst_areas.addItems(
            [
                "General",
                "Station ID",
                "Tactical ID",
                "Interface",
                "BBS",
                "BBS Logon",
                "Send/Receive",
                "Message Settings",
            ]
        )
        self.lst_areas.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.lst_areas.setFixedWidth(140)
        self.lst_areas.setSizePolicy(
            QtWidgets.QSizePolicy.Fixed,
            QtWidgets.QSizePolicy.Expanding,
        )
        cols.addWidget(self.lst_areas, 0)

        # Column 2: Configurations
        mid = QtWidgets.QVBoxLayout()
        cols.addLayout(mid, 1)

        self.lbl_configs = QtWidgets.QLabel("Configurations")
        mid.addWidget(self.lbl_configs)

        self.lst_configs = QtWidgets.QListWidget()
        self.lst_configs.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        mid.addWidget(self.lst_configs, 1)

        # Column 3: Stacked detail pages
        self.stack = QtWidgets.QStackedWidget()
        cols.addWidget(self.stack, 2)

        # Page indices:
        #   0 -> BBS
        #   1 -> General
        #   2 -> Station ID
        #   3 -> Tactical ID
        #   4 -> Interface
        #   5 -> BBS Logon
        #   6 -> Send/Receive
        #   7 -> Message Settings

        # Page 0: BBS
        self.bbs_widget = BBSSettingsWidget()
        bbs_scroll = QtWidgets.QScrollArea()
        bbs_scroll.setWidgetResizable(True)
        bbs_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        bbs_scroll.setWidget(self.bbs_widget)
        self.stack.addWidget(bbs_scroll)  # index 0

        # Page 1: General (placeholder)
        self.page_general = QtWidgets.QWidget()
        general_layout = QtWidgets.QVBoxLayout(self.page_general)
        lbl_general = QtWidgets.QLabel("General settings not implemented yet.")
        lbl_general.setAlignment(QtCore.Qt.AlignCenter)
        general_layout.addWidget(lbl_general)
        general_layout.addStretch(1)
        self.stack.addWidget(self.page_general)  # index 1

        # Page 2: Station ID
        self.station_widget = StationSettingsWidget()
        station_scroll = QtWidgets.QScrollArea()
        station_scroll.setWidgetResizable(True)
        station_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        station_scroll.setWidget(self.station_widget)
        self.stack.addWidget(station_scroll)  # index 2

        # Page 3: Tactical ID
        self.tactical_widget = TacticalSettingsWidget()
        tactical_scroll = QtWidgets.QScrollArea()
        tactical_scroll.setWidgetResizable(True)
        tactical_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        tactical_scroll.setWidget(self.tactical_widget)
        self.stack.addWidget(tactical_scroll)  # index 3

        # Page 4: Interface
        self.interface_widget = InterfaceSetupWidget()
        iface_scroll = QtWidgets.QScrollArea()
        iface_scroll.setWidgetResizable(True)
        iface_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        iface_scroll.setWidget(self.interface_widget)
        self.stack.addWidget(iface_scroll)  # index 4

        # Page 5: BBS Logon
        self.bbs_logon_widget = BBSLogonSettingsWidget()
        logon_scroll = QtWidgets.QScrollArea()
        logon_scroll.setWidgetResizable(True)
        logon_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        logon_scroll.setWidget(self.bbs_logon_widget)
        self.stack.addWidget(logon_scroll)  # index 5

        # Page 6: Send/Receive
        self.sendrecv_widget = SendReceiveSettingsWidget()
        sendrecv_scroll = QtWidgets.QScrollArea()
        sendrecv_scroll.setWidgetResizable(True)
        sendrecv_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        sendrecv_scroll.setWidget(self.sendrecv_widget)
        self.stack.addWidget(sendrecv_scroll)  # index 6

        # Page 7: Message Settings
        self.message_settings_widget = MessageSettingsWidget()
        msg_settings_scroll = QtWidgets.QScrollArea()
        msg_settings_scroll.setWidgetResizable(True)
        msg_settings_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        msg_settings_scroll.setWidget(self.message_settings_widget)
        self.stack.addWidget(msg_settings_scroll)  # index 7

        # ------------------------------------------------------------------
        # Wire signals
        # ------------------------------------------------------------------
        self.lst_areas.currentRowChanged.connect(self._on_area_changed)
        self.lst_configs.currentRowChanged.connect(self._on_config_selected)

        self.btn_new.clicked.connect(self._on_new)
        self.btn_copy.clicked.connect(self._on_copy)
        self.btn_delete.clicked.connect(self._on_delete)
        self.btn_activate.clicked.connect(self._on_activate)
        self.btn_save.clicked.connect(self._on_save)
        self.btn_cancel.clicked.connect(self._on_cancel)

        self.bbs_widget.changed.connect(self._on_bbs_changed)
        self.interface_widget.changed.connect(self._on_interface_changed)
        self.station_widget.changed.connect(self._on_station_changed)
        self.tactical_widget.changed.connect(self._on_tactical_changed)
        self.bbs_logon_widget.changed.connect(self._on_bbs_logon_changed)
        self.sendrecv_widget.changed.connect(self._on_sendrecv_changed)
        self.message_settings_widget.changed.connect(self._on_message_settings_changed)

        # Initial: load BBS profiles and select area BBS
        self._refresh_bbs_list(select_active=True)
        if self._config:
            self._config.restore_window_state(self, "SetupDialog")

        self.lst_areas.setCurrentRow(4)  # Interface as initial view

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _current_area(self) -> str:
        item = self.lst_areas.currentItem()
        return item.text() if item else "BBS"

    def _current_config_id(self) -> Optional[int]:
        item = self.lst_configs.currentItem()
        if not item:
            return None
        return item.data(QtCore.Qt.UserRole)

    def _select_config_id(self, config_id: int | None) -> None:
        """Select the lst_configs row whose UserRole == config_id."""
        if config_id is None:
            return
        for i in range(self.lst_configs.count()):
            item = self.lst_configs.item(i)
            if item and item.data(QtCore.Qt.UserRole) == config_id:
                self.lst_configs.setCurrentRow(i)
                return

    # ------------------------------------------------------------------
    # Area switching
    # ------------------------------------------------------------------
    def _on_area_changed(self, row: int) -> None:
        """
        Change Setup areas.

        If the current form contains unsaved changes, ask before leaving it.
        Choosing No restores the previous area selection and leaves the
        current form unchanged.
        """
        if row < 0:
            return

        # Issue x133: protect unsaved form contents.
        if self._dirty:
            if not self._confirm_discard():
                # Restore only the visual selection. Do not reload the form.
                if self._previous_area_row >= 0:
                    # QSignalBlocker is an RAII object (a C++ pattern exposed through Qt).
                    # Temporarily block currentRowChanged() while restoring the previous
                    # selection. Without this, setCurrentRow() would emit the signal and
                    # recursively call _on_area_changed() (or _on_config_selected()).
                    #
                    # When the blocker object is destroyed (del blocker), its destructor
                    # automatically restores the widget's previous signal state so the
                    # remainder of this function executes with normal signal handling.
                    blocker = QtCore.QSignalBlocker(self.lst_areas)
                    self.lst_areas.setCurrentRow(self._previous_area_row)  
                    del blocker 
                return

            # The user explicitly chose to discard the edits.
            # Clear this before the refresh methods select another profile.
            self._dirty = False

        item = self.lst_areas.item(row)
        if not item:
            return

        area = item.text()

        if area == "BBS":
            self.lbl_configs.setText("BBS configurations")
            self._refresh_bbs_list(select_active=True)
            self.stack.setCurrentIndex(0)

        elif area == "Interface":
            self.lbl_configs.setText("Interface configurations")
            self._refresh_interface_list(select_active=True)
            self.stack.setCurrentIndex(4)

        elif area == "Station ID":
            self.lbl_configs.setText("Station ID configurations")
            self._refresh_station_list(select_active=True)
            self.stack.setCurrentIndex(2)

        elif area == "Tactical ID":
            self.lbl_configs.setText("Tactical ID configurations")
            self._refresh_tactical_list(select_active=True)
            self.stack.setCurrentIndex(3)

        elif area == "BBS Logon":
            self.lbl_configs.setText("BBS Logon configurations")
            self._refresh_bbs_logon_list(select_any=True)
            self.stack.setCurrentIndex(5)

        elif area == "Send/Receive":
            self.lbl_configs.setText("Send/Receive settings")
            self._refresh_send_receive()
            self.stack.setCurrentIndex(6)

        elif area == "Message Settings":
            self.lbl_configs.setText("Message Settings")
            self._refresh_message_settings()
            self.stack.setCurrentIndex(7)

        else:  # General
            self.lbl_configs.setText("General configurations")

            blocker = QtCore.QSignalBlocker(self.lst_configs)
            self.lst_configs.clear()
            del blocker

            self.stack.setCurrentIndex(1)
            self._dirty = False

        self._update_toolbar_for_area(area)

        # This area is now the successfully displayed area.
        self._previous_area_row = row


    def _update_toolbar_for_area(self, area: str) -> None:
        """Enable/disable toolbar buttons based on active area."""
        # defaults: all off, Cancel on
        self.btn_new.setEnabled(False)
        self.btn_copy.setEnabled(False)
        self.btn_delete.setEnabled(False)
        self.btn_activate.setEnabled(False)
        self.btn_save.setEnabled(False)
        self.btn_cancel.setEnabled(True)

        full_toolbar_areas = {"BBS", "Interface", "Station ID", "Tactical ID", "BBS Logon"}
        if area in full_toolbar_areas:
            self.btn_new.setEnabled(True)
            self.btn_delete.setEnabled(True)
            self.btn_save.setEnabled(True)

            # Copy: BBS, Interface, BBS Logon, Tactical (allowed)
            self.btn_copy.setEnabled(area in {"BBS", "Interface", "BBS Logon", "Tactical ID"})

            # Activate: BBS, Interface, Station ID, Tactical ID
            self.btn_activate.setEnabled(area in {"BBS", "Interface", "Station ID", "Tactical ID"})
        elif area in {"Send/Receive", "Message Settings"}:
            # Send/Receive is a single global configuration: only Save/Cancel apply
            self.btn_save.setEnabled(True)

    # ------------------------------------------------------------------
    # BBS helpers
    # ------------------------------------------------------------------
    def _refresh_bbs_list(self, select_active: bool = False) -> None:
        self.lst_configs.blockSignals(True)
        self.lst_configs.clear()

        profiles = self._bbs_repo.list_profiles()
        active = self._bbs_repo.get_active()
        active_id = active.id if active else None

        for p in profiles:
            label = p.friendly_name
            if p.is_active:
                label += "  <-ACTIVE"
            item = QtWidgets.QListWidgetItem(label)
            item.setData(QtCore.Qt.UserRole, p.id)
            self.lst_configs.addItem(item)

        self.lst_configs.blockSignals(False)

        if self.lst_configs.count() > 0:
            if select_active and active_id is not None:
                row_to_select = 0
                for i in range(self.lst_configs.count()):
                    if self.lst_configs.item(i).data(QtCore.Qt.UserRole) == active_id:
                        row_to_select = i
                        break
                self.lst_configs.setCurrentRow(row_to_select)
            else:
                self.lst_configs.setCurrentRow(0)
        else:
            self._current_bbs = self._bbs_repo.new_profile()
            self.bbs_widget.load_profile(self._current_bbs, interfaces=[])
            self._update_node_path_summary(getattr(self._current_bbs,'id',None))

        self._dirty = False

    # ------------------------------------------------------------------
    # Node Path (KA-NODE / NET/ROM) actions
    # ------------------------------------------------------------------

    def _update_node_path_summary(self, bbs_profile_id: Optional[int]) -> None:
        """
        Populate the small 'summary' label on the BBS page, if present.
        """
        # If the widget doesn't have the label, just exit quietly.
        lbl = getattr(self.bbs_widget, "lbl_node_path_summary", None)
        if lbl is None:
            return

        if not bbs_profile_id:
            lbl.setText("No node path configured.")
            return

        path = self._node_path_repo.get_for_bbs(int(bbs_profile_id))
        if path is None or path.is_empty():
            lbl.setText("No node path configured.")
            return

        # Compact summary: "3 hop(s): A -> B -> C"
        names = [h.node_name for h in path.hops if (h.node_name or "").strip()]
        if not names:
            lbl.setText("No node path configured.")
            return

        hop_count = len(names)
        preview = " \u2192 ".join(names[:4])
        if hop_count > 4:
            preview += " \u2192 …"

        lbl.setText(f"{hop_count} hop(s): {preview}")


    # ------------------------------------------------------------------
    # Interface helpers
    # ------------------------------------------------------------------
    def _refresh_interface_list(self, select_active: bool = False) -> None:
        self.lst_configs.blockSignals(True)
        self.lst_configs.clear()

        profiles = self._iface_repo.list_profiles()
        active = self._iface_repo.get_active()
        active_id = active.id if active else None

        for p in profiles:
            label = p.interface_name
            if p.is_active:
                label += "  <-ACTIVE"
            item = QtWidgets.QListWidgetItem(label)
            item.setData(QtCore.Qt.UserRole, p.id)
            self.lst_configs.addItem(item)

        self.lst_configs.blockSignals(False)

        if self.lst_configs.count() > 0:
            row_to_select = 0
            if select_active and active_id is not None:
                for i in range(self.lst_configs.count()):
                    if self.lst_configs.item(i).data(QtCore.Qt.UserRole) == active_id:
                        row_to_select = i
                        break
            self.lst_configs.setCurrentRow(row_to_select)

            profile_id = self._current_config_id()
            if profile_id is not None:
                profile = self._iface_repo.get(profile_id)
                if profile:
                    self._current_interface = profile
                    self.interface_widget.from_dict(profile.data or {})
        else:
            self._current_interface = self._iface_repo.new_profile()
            self.interface_widget.load_default_tnc_profile()

        self._dirty = False

    # ------------------------------------------------------------------
    # Station helpers
    # ------------------------------------------------------------------
    def _refresh_station_list(self, select_active: bool = True) -> None:
        self.lst_configs.blockSignals(True)
        self.lst_configs.clear()

        profiles = self._station_repo.list_profiles()
        active = self._station_repo.get_active()
        active_id = active.id if active else None

        for p in profiles:
            label = p.legal_call_sign
            if p.is_active:
                label += "  <-ACTIVE"
            item = QtWidgets.QListWidgetItem(label)
            item.setData(QtCore.Qt.UserRole, p.id)
            self.lst_configs.addItem(item)

        self.lst_configs.blockSignals(False)

        if self.lst_configs.count() > 0:
            row_to_select = 0
            if select_active and active_id is not None:
                for i in range(self.lst_configs.count()):
                    if self.lst_configs.item(i).data(QtCore.Qt.UserRole) == active_id:
                        row_to_select = i
                        break
            self.lst_configs.setCurrentRow(row_to_select)

            profile_id = self._current_config_id()
            if profile_id is not None:
                profile = self._station_repo.get(profile_id)
                if profile:
                    self._current_station = profile
                    self.station_widget.load_profile(profile)
        else:
            self._current_station = self._station_repo.new_profile()
            self.station_widget.load_profile(self._current_station)

        self._dirty = False

    # ------------------------------------------------------------------
    # Tactical helpers
    # ------------------------------------------------------------------
    def _refresh_tactical_list(self, select_active: bool = True) -> None:
        self.lst_configs.blockSignals(True)
        self.lst_configs.clear()

        profiles = self._tactical_repo.list_profiles()
        active = self._tactical_repo.get_active()
        active_id = active.id if active else None

        for p in profiles:
            label = p.tactical_call_sign
            if p.is_active:
                label += "  <-ACTIVE"
            item = QtWidgets.QListWidgetItem(label)
            item.setData(QtCore.Qt.UserRole, p.id)
            self.lst_configs.addItem(item)

        self.lst_configs.blockSignals(False)

        if self.lst_configs.count() > 0:
            row_to_select = 0
            if select_active and active_id is not None:
                for i in range(self.lst_configs.count()):
                    if self.lst_configs.item(i).data(QtCore.Qt.UserRole) == active_id:
                        row_to_select = i
                        break
            self.lst_configs.setCurrentRow(row_to_select)

            profile_id = self._current_config_id()
            if profile_id is not None:
                profile = self._tactical_repo.get(profile_id)
                if profile:
                    self._current_tactical = profile
                    self.tactical_widget.load_profile(profile)
        else:
            self._current_tactical = self._tactical_repo.new_profile()
            self.tactical_widget.load_profile(self._current_tactical)

        self._dirty = False

    # ------------------------------------------------------------------
    # BBS Logon helpers
    # ------------------------------------------------------------------
    def _refresh_bbs_logon_list(self, select_any: bool = True) -> None:
        self.lst_configs.blockSignals(True)
        self.lst_configs.clear()

        profiles = self._bbs_logon_repo.list_profiles()

        for p in profiles:
            label = f"{p.bbs_connect_call}-{p.login_username}"
            item = QtWidgets.QListWidgetItem(label)
            item.setData(QtCore.Qt.UserRole, p.id)
            self.lst_configs.addItem(item)

        self.lst_configs.blockSignals(False)

        if self.lst_configs.count() > 0 and select_any:
            self.lst_configs.setCurrentRow(0)
            profile_id = self._current_config_id()
            if profile_id is not None:
                profile = self._bbs_logon_repo.get(profile_id)
                if profile:
                    self._current_bbs_logon = profile
                    self.bbs_logon_widget.load_profile(profile)
        else:
            self._current_bbs_logon = self._bbs_logon_repo.new_profile()
            self.bbs_logon_widget.load_profile(self._current_bbs_logon)

        self._dirty = False

    # ------------------------------------------------------------------
    # Send/Receive helpers
    # ------------------------------------------------------------------
    def _refresh_send_receive(self) -> None:
        """
        Refresh the Send/Receive settings page.

        - lst_configs shows a single 'Global Send/Receive Settings' entry
        - sendrecv_widget is populated from QSettings
        """
        self.lst_configs.blockSignals(True)
        self.lst_configs.clear()

        item = QtWidgets.QListWidgetItem("Global Send/Receive Settings")
        item.setData(QtCore.Qt.UserRole, 0)
        self.lst_configs.addItem(item)
        self.lst_configs.setCurrentRow(0)

        self.lst_configs.blockSignals(False)

        if self._config is None:
            return

        settings = load_send_receive_settings(self._config)
        self.sendrecv_widget.load_from_models(settings)

        self._dirty = False

    # ------------------------------------------------------------------
    # Message Settings helpers
    # ------------------------------------------------------------------
    def _refresh_message_settings(self) -> None:
        """
        Refresh the Message Settings page.

        - lst_configs shows a single global settings entry
        - message_settings_widget is populated from QSettings
        """
        self.lst_configs.blockSignals(True)
        self.lst_configs.clear()

        item = QtWidgets.QListWidgetItem("Global Message Settings")
        item.setData(QtCore.Qt.UserRole, 0)
        self.lst_configs.addItem(item)
        self.lst_configs.setCurrentRow(0)

        self.lst_configs.blockSignals(False)

        if self._config is None:
            return

        settings = load_message_settings(self._config)
        self.message_settings_widget.load_from_models(settings)

        self._dirty = False

    # ------------------------------------------------------------------
    # Config selection
    # ------------------------------------------------------------------
    def _on_config_selected(self, row: int) -> None:
        """
        Load the selected configuration profile.

        If the current form contains unsaved changes, ask before replacing it.
        Choosing No restores the previous list selection and preserves the
        current form exactly as entered.
        """
        if row < 0:
            return

        # Issue x133: protect unsaved form contents.
        if self._dirty:
            if not self._confirm_discard():
                # See _on_area_changed() for the detailed explanation.
                # Restore the previous selection without emitting currentRowChanged().
                # See the comments in _on_area_changed() for details.
                if self._previous_config_row >= 0:
                    blocker = QtCore.QSignalBlocker(self.lst_configs)
                    self.lst_configs.setCurrentRow(self._previous_config_row)
                    del blocker
                return

            # User chose to discard the unsaved edits.
            self._dirty = False

        profile_id = self._current_config_id()
        if profile_id is None:
            return

        area = self._current_area()

        if area == "BBS":
            profile = self._bbs_repo.get(profile_id)
            if profile is None:
                return
            self._current_bbs = profile
            self.bbs_widget.load_profile(profile, interfaces=[])
            self._update_node_path_summary(profile.id)

        elif area == "Interface":
            profile = self._iface_repo.get(profile_id)
            if profile is None:
                return
            self._current_interface = profile
            self.interface_widget.from_dict(profile.data or {})

        elif area == "Station ID":
            profile = self._station_repo.get(profile_id)
            if profile is None:
                return
            self._current_station = profile
            self.station_widget.load_profile(profile)

        elif area == "Tactical ID":
            profile = self._tactical_repo.get(profile_id)
            if profile is None:
                return
            self._current_tactical = profile
            self.tactical_widget.load_profile(profile)

        elif area == "BBS Logon":
            profile = self._bbs_logon_repo.get(profile_id)
            if profile is None:
                return
            self._current_bbs_logon = profile
            self.bbs_logon_widget.load_profile(profile)

        self._dirty = False

        # This row is now the successfully loaded configuration.
        self._previous_config_row = row


    # ------------------------------------------------------------------
    # Toolbar actions
    # ------------------------------------------------------------------
    def _on_new(self) -> None:
        area = self._current_area()
        if area == "BBS":
            self._current_bbs = self._bbs_repo.new_profile()
            self.bbs_widget.load_profile(self._current_bbs, interfaces=[])
            self._update_node_path_summary(getattr(self._current_bbs, "id", None))
        elif area == "Interface":
            self._current_interface = self._iface_repo.new_profile()
            self.interface_widget.load_default_tnc_profile()
        elif area == "Station ID":
            self._current_station = self._station_repo.new_profile()
            self.station_widget.load_profile(self._current_station)
        elif area == "Tactical ID":
            self._current_tactical = self._tactical_repo.new_profile()
            self.tactical_widget.load_profile(self._current_tactical)
        elif area == "BBS Logon":
            self._current_bbs_logon = self._bbs_logon_repo.new_profile()
            self.bbs_logon_widget.load_profile(self._current_bbs_logon)

        self._dirty = False

    def _on_copy(self) -> None:
        area = self._current_area()

        if area not in ("BBS", "Interface", "BBS Logon", "Tactical ID"):
            return

        profile_id = self._current_config_id()
        if profile_id is None:
            QtWidgets.QMessageBox.information(
                self,
                f"Copy {area}",
                f"There is no {area} configuration selected to copy.",
            )
            return

        if self._dirty:
            resp = QtWidgets.QMessageBox.question(
                self,
                "Unsaved changes",
                (
                    f"You have unsaved changes to the current {area} configuration.\n\n"
                    "Copy will be based on the last saved version and your unsaved changes "
                    "will be lost.\n\n"
                    "Continue without saving?"
                ),
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No,
            )
            if resp != QtWidgets.QMessageBox.Yes:
                return

        if area == "BBS":
            try:
                copy = self._bbs_repo.duplicate(profile_id)
            except ValueError as exc:
                QtWidgets.QMessageBox.warning(self, "Copy BBS", str(exc))
                return
            self._current_bbs = copy
            self.bbs_widget.load_profile(copy, interfaces=[])
            self._refresh_bbs_list(select_active=False)

        elif area == "Interface":
            try:
                copy = self._iface_repo.duplicate(profile_id)
            except ValueError as exc:
                QtWidgets.QMessageBox.warning(self, "Copy Interface", str(exc))
                return
            self._current_interface = copy
            self.interface_widget.from_dict(copy.data or {})
            self._refresh_interface_list(select_active=False)

        elif area == "BBS Logon":
            try:
                copy = self._bbs_logon_repo.duplicate(profile_id)
            except ValueError as exc:
                QtWidgets.QMessageBox.warning(self, "Copy BBS Logon", str(exc))
                return
            self._current_bbs_logon = copy
            self.bbs_logon_widget.load_profile(copy)
            self._refresh_bbs_logon_list(select_any=False)

        elif area == "Tactical ID":
            # Simple copy: duplicate via repo? (no helper yet, so copy in memory)
            original = self._tactical_repo.get(profile_id)
            if original is None:
                return
            new_profile = TacticalProfile(
                tactical_call_sign=f"{original.tactical_call_sign}-COPY",
                tactical_location=original.tactical_location,
                msg_id_prefix=original.msg_id_prefix,
                signature=original.signature,
                is_active=False,
            )
            try:
                new_profile = self._tactical_repo.save(new_profile)
            except ValueError as exc:
                QtWidgets.QMessageBox.warning(self, "Copy Tactical ID", str(exc))
                return
            self._current_tactical = new_profile
            self.tactical_widget.load_profile(new_profile)
            self._refresh_tactical_list(select_active=False)

        self._dirty = False

    def _on_delete(self) -> None:
        area = self._current_area()
        profile_id = self._current_config_id()
        if profile_id is None:
            return

        if area == "BBS":
            title = "Delete BBS profile"
            msg = "Do you really want to delete this BBS profile?"
        elif area == "Interface":
            title = "Delete Interface profile"
            msg = "Do you really want to delete this Interface profile?"
        elif area == "Station ID":
            title = "Delete Station ID profile"
            msg = "Do you really want to delete this Station ID profile?"
        elif area == "Tactical ID":
            title = "Delete Tactical ID profile"
            msg = "Do you really want to delete this Tactical ID profile?"
        elif area == "BBS Logon":
            title = "Delete BBS Logon profile"
            msg = "Do you really want to delete this BBS Logon profile?"
        else:
            return

        resp = QtWidgets.QMessageBox.question(
            self,
            title,
            msg,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if resp != QtWidgets.QMessageBox.Yes:
            return

        if area == "BBS":
            self._bbs_repo.delete(profile_id)
            self._current_bbs = None
            self._refresh_bbs_list(select_active=True)
        elif area == "Interface":
            self._iface_repo.delete(profile_id)
            self._current_interface = None
            self._refresh_interface_list(select_active=True)
        elif area == "Station ID":
            self._station_repo.delete(profile_id)
            self._current_station = None
            self._refresh_station_list(select_active=True)
        elif area == "Tactical ID":
            self._tactical_repo.delete(profile_id)
            self._current_tactical = None
            self._refresh_tactical_list(select_active=True)
        elif area == "BBS Logon":
            self._bbs_logon_repo.delete(profile_id)
            self._current_bbs_logon = None
            self._refresh_bbs_logon_list(select_any=True)

    def _on_activate(self) -> None:
        area = self._current_area()
        profile_id = self._current_config_id()
        if profile_id is None:
            return

        # If we don't have a SystemConfigService yet, fall back to repo-only behavior.
        use_service = self._system_config is not None

        if area == "BBS":
            if use_service:
                self._system_config.set_active_bbs(profile_id)
            else:
                self._bbs_repo.set_active(profile_id)
            self._refresh_bbs_list(select_active=True)

        elif area == "Interface":
            if use_service:
                self._system_config.set_active_interface(profile_id)
            else:
                self._iface_repo.set_active(profile_id)
            self._refresh_interface_list(select_active=True)

        elif area == "Station ID":
            if use_service:
                self._system_config.set_active_station(profile_id)
            else:
                self._station_repo.set_active(profile_id)
            self._refresh_station_list(select_active=True)

        elif area == "Tactical ID":
            # Toggle semantics kept, but push through the service when available
            current = self._tactical_repo.get(profile_id)
            if current and current.is_active:
                # Deactivate all
                if use_service:
                    self._system_config.set_active_tactical(None)
                else:
                    self._tactical_repo.set_active(None)
            else:
                if use_service:
                    self._system_config.set_active_tactical(profile_id)
                else:
                    self._tactical_repo.set_active(profile_id)
            self._refresh_tactical_list(select_active=True)

        # BBS Logon has no 'active' concept at the moment, so nothing here.

    def _on_save(self) -> None:
        area = self._current_area()
        if area == "BBS":
            profile = self.bbs_widget.apply_to_profile(self._current_bbs)
            try:
                profile = self._bbs_repo.save(profile)
            except ValueError as exc:
                QtWidgets.QMessageBox.warning(self, "Save error", str(exc))
                return

            self._current_bbs = profile
            saved_id = profile.id                         # <<< ADD THIS
            self._dirty = False                             # x133

            self._refresh_bbs_list(select_active=False)
            self._select_config_id(saved_id)              # <<< ADD THIS
            self._update_node_path_summary(saved_id)      # <<< ADD THIS

        elif area == "Interface":
            data = self.interface_widget.to_dict()
            if self._current_interface is None:
                self._current_interface = self._iface_repo.new_profile()
            self._current_interface.data = data
            name = (data.get("interface_name") or "").strip()
            self._current_interface.interface_name = name
            try:
                profile = self._iface_repo.save(self._current_interface)
            except ValueError as exc:
                QtWidgets.QMessageBox.warning(self, "Save error", str(exc))
                return

            self._current_interface = profile
            saved_id = profile.id                         # <<< ADD THIS
            self._dirty = False                             # x133
            self._refresh_interface_list(select_active=False)
            self._select_config_id(saved_id)              # <<< ADD THIS

        elif area == "Station ID":
            if self._current_station is None:
                self._current_station = self._station_repo.new_profile()
            profile = self.station_widget.apply_to_profile(self._current_station)
            try:
                profile = self._station_repo.save(profile)
            except ValueError as exc:
                QtWidgets.QMessageBox.warning(self, "Save error", str(exc))
                return
            self._current_station = profile
            saved_id = profile.id                         # <<< ADD THIS
            self._dirty = False                             # x133
            self._refresh_station_list(select_active=False)
            self._select_config_id(saved_id)              # <<< ADD THIS

        elif area == "Tactical ID":
            if self._current_tactical is None:
                self._current_tactical = self._tactical_repo.new_profile()
            profile = self.tactical_widget.apply_to_profile(self._current_tactical)
            try:
                profile = self._tactical_repo.save(profile)
            except ValueError as exc:
                QtWidgets.QMessageBox.warning(self, "Save error", str(exc))
                return
            self._current_tactical = profile
            saved_id = profile.id                         # <<< ADD THIS
            self._dirty = False                             # x133
            self._refresh_tactical_list(select_active=False)
            self._select_config_id(saved_id)              # <<< ADD THIS

        elif area == "BBS Logon":
            if self._current_bbs_logon is None:
                self._current_bbs_logon = self._bbs_logon_repo.new_profile()
            profile = self.bbs_logon_widget.apply_to_profile(self._current_bbs_logon)
            try:
                profile = self._bbs_logon_repo.save(profile)
            except ValueError as exc:
                QtWidgets.QMessageBox.warning(self, "Save error", str(exc))
                return
            self._current_bbs_logon = profile
            saved_id = profile.id                         # <<< ADD THIS
            self._dirty = False                             # x133
            self._refresh_bbs_logon_list(select_any=False)
            self._select_config_id(saved_id)              # <<< ADD THIS

        # 260531: replaced
        elif area == "Send/Receive":
            if self._config is None:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Save error",
                    "Cannot save Send/Receive settings: no AppConfig is available.",
                )
                return

            settings = self.sendrecv_widget.to_settings()

            # Slot Time Scheduling: must have at least one valid minute
            if (
                settings.mode == AutomationMode.SLOT_TIMES
                and not settings.slot_minutes
            ):
                QtWidgets.QMessageBox.warning(
                    self,
                    "Invalid Slot Times",
                    (
                        "You selected Slot Time Scheduling but did not enter any valid "
                        "minutes past the hour.\n\n"
                        "Please enter one or more values between 0 and 59, separated "
                        "by commas (for example: 5, 45, 59)."
                    ),
                )
                return

            # Play sound on receive: must have a non-empty file path
            if settings.play_sound_on_receive and not settings.sound_file_path.strip():
                QtWidgets.QMessageBox.warning(
                    self,
                    "Missing Sound File",
                    (
                        "You enabled 'Play this sound on message arrival' but did not "
                        "specify a sound file.\n\n"
                        "Either choose a sound file or uncheck the option."
                    ),
                )
                return

            save_send_receive_settings(self._config, settings)
            self._dirty = False
            self._show_saved_toast(self.btn_save, "Saved!")
            return


        elif area == "Message Settings":
            settings = self.message_settings_widget.to_settings()
            save_message_settings(self._config, settings)
            self._dirty = False
            self._show_saved_toast(self.btn_save, "Saved!")
            return

            settings = self.sendrecv_widget.to_settings()

            # --- Lightweight validation ---

            # 1) Slot Time Scheduling: must have at least one valid minute
            if (
                settings.mode == AutomationMode.SLOT_TIMES
                and not settings.slot_minutes
            ):
                QtWidgets.QMessageBox.warning(
                    self,
                    "Invalid Slot Times",
                    (
                        "You selected Slot Time Scheduling but did not enter any valid "
                        "minutes past the hour.\n\n"
                        "Please enter one or more values between 0 and 59, separated "
                        "by commas (for example: 5, 45, 59)."
                    ),
                )
                return

            # 2) Play sound on receive: must have a non-empty file path
            if settings.play_sound_on_receive and not settings.sound_file_path.strip():
                QtWidgets.QMessageBox.warning(
                    self,
                    "Missing Sound File",
                    (
                        "You enabled 'Play this sound on message arrival' but did not "
                        "specify a sound file.\n\n"
                        "Either choose a sound file or uncheck the option."
                    ),
                )
                return

            # If we get here, settings look reasonable
            save_send_receive_settings(self._config, settings)
            self._dirty = False
            return

        elif area == "Message Settings":
            if self._config is None:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Message Settings",
                    "Application configuration is not available.",
                )
                return

            ok, err = self.message_settings_widget.validate()
            if not ok:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Message Settings",
                    err,
                )
                return

            settings = self.message_settings_widget.to_settings()
            save_message_settings(self._config, settings)
            self._dirty = False
            self._show_saved_toast(self.btn_save, "Saved!")
            return

        self._show_saved_toast(self.btn_save, "Saved!")

    def _on_cancel(self) -> None:
        if self._dirty and not self._confirm_discard():
            return
        self.reject()


    # ------------------------------------------------------------------
    # Helper function
    # ------------------------------------------------------------------
    def _show_saved_toast(self, anchor: QtWidgets.QWidget, text: str = "Saved!") -> None:
        # Show tooltip just below the anchor widget (e.g., Save button)
        pos = anchor.mapToGlobal(QtCore.QPoint(0, anchor.height() + 6))
        QtWidgets.QToolTip.showText(pos, text, anchor)

        # Force-hide after ~1.5s (tooltip may auto-hide sooner depending on platform)
        QtCore.QTimer.singleShot(1500, QtWidgets.QToolTip.hideText)


    # ------------------------------------------------------------------
    # Dirty tracking
    # ------------------------------------------------------------------
    def _on_bbs_changed(self) -> None:
        self._dirty = True

    def _on_interface_changed(self) -> None:
        self._dirty = True

    def _on_station_changed(self) -> None:
        self._dirty = True

    def _on_tactical_changed(self) -> None:
        self._dirty = True

    def _on_bbs_logon_changed(self) -> None:
        self._dirty = True

    def _on_sendrecv_changed(self) -> None:
        self._dirty = True

    def _on_message_settings_changed(self) -> None:
        self._dirty = True        

    def _confirm_discard(self) -> bool:
        resp = QtWidgets.QMessageBox.question(
            self,
            "Discard changes?",
            "You have unsaved changes.\nDo you really want to discard them?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        return resp == QtWidgets.QMessageBox.Yes

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if self._dirty and not self._confirm_discard():
            event.ignore()
            return
        if self._config:
            self._config.save_window_state(self, "SetupDialog")
        super().closeEvent(event)


if __name__ == "__main__":
    import sys

    app = QtWidgets.QApplication(sys.argv)
    db_path = Path("outpostx.db")
    dlg = SetupDialog(db_path)
    dlg.exec()
