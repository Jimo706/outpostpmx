# main.py
# 251207: Production bootstrap with SystemConfigService + SqliteMessageService
"""
OutpostX GUI bootstrap (composition root).

This module is the application entry point for the OutpostX desktop GUI. It is intentionally
"wiring-only": it connects configuration, persistence, repositories/services, and the Qt UI,
then starts the Qt event loop.

Wires together:
- Qt application identity + platform style
- Persistent settings (AppConfig / QSettings)
- SQLite database location and initialization
- Data layer (MessageDAO/MessageRepository + profile repositories)
- SystemConfigService (active Station/Tactical/BBS/Interface selection coordination)
- Adapters used by the editor/message service
- MainWindow construction and launch

Primary side effects:
- Creates ~/.OutpostX/ (or equivalent home folder path)
- Opens/creates outpostx.db
- Ensures folders table and root folder rows exist

Keep this module light: business logic belongs in services/repositories, not here.
"""
from __future__ import annotations

import sys
import platform
from pathlib import Path

from PySide6 import QtWidgets, QtCore
from PySide6.QtGui import QIcon

from app_config import AppConfig
from ui.main_window import MainWindow, ensure_folders_table_and_roots

from data.message_dao import MessageDAO
from data.message_repo import MessageRepository, RepoConfig

from data.station_profile_repo import StationProfileRepository
from data.tactical_profile_repo import TacticalProfileRepository
from data.bbs_profile_repo import BBSProfileRepository
from data.interface_profile_repo import InterfaceProfileRepository
from data.bbs_logon_repo import BBSLogonRepository

from services.app_info import AppInfo
from services.app_paths import AppPaths
from services.seed_data import seed_runtime_data
from services.notification_service import NotificationService
from services.sqlite_message_service import SqliteMessageService
from services.system_config_service import SystemConfigService
from services.recent_config_service import RecentConfigService


def apply_native_style() -> None:
    """
    Apply a platform-appropriate Qt widget style.

    Notes:
    - Windows: prefer "windowsvista" for a more native look.
    - macOS: do not override; Qt's native macOS style is typically best.
    - Linux: use "fusion" for consistency across distros/themes.
    """
    osname = platform.system()

    if osname == "Windows":
        QtWidgets.QApplication.setStyle("windowsvista")
    elif osname == "Darwin":
        # macOS: let Qt use the built-in macOS style
        pass
    elif osname == "Linux":
        QtWidgets.QApplication.setStyle("fusion")


def app_db_path(app_paths: AppPaths) -> Path:
    """ 260605
    Return the SQLite database path under the resolved OutpostX
    writable data directory.
    """
    return app_paths.data_dir / "outpostx.db"

# ----------------------------------------------------------------------
# Adapters for SqliteMessageService
# ----------------------------------------------------------------------
class EditorProfilesAdapter:
    """
    260609: !!!NOTACCESSED: does not look like it is called by anyone any more.
    Adapter for SqliteMessageService: provides a list of BBS "names" for UI dropdowns.

    Behavior (matches Outpost Classic):
      - Use friendly_name when present; else bbs_call; else "(Unassigned)".
      - If an active BBS exists (SystemConfigService), it should appear first.
      - If no BBS profiles at all: show "(Unassigned)".

    Contract:
        Must provide list_bbs_names() -> list[str] for SqliteMessageService.
    """

    def __init__(self, bbs_repo: BBSProfileRepository, system_config: SystemConfigService) -> None:
        self._bbs_repo = bbs_repo
        self._system_config = system_config

    def list_bbs_names(self) -> list[str]:
        """
        260609: !!!NOTACCESSED: does not look like it is called by anyone any more.
        """
        profiles = self._bbs_repo.list_profiles()
        raw_names: list[str] = []

        for p in profiles:
            # Prefer friendly_name; fall back to bbs_call; else "(Unassigned)"
            name = (getattr(p, "friendly_name", "") or "").strip()
            if not name:
                name = (getattr(p, "bbs_call", "") or "").strip()
            if not name:
                name = "(Unassigned)"
            raw_names.append(name)

        # No BBS profiles at all → single placeholder
        if not raw_names:
            return ["(Unassigned)"]

        # Determine active BBS name from SystemConfigService snapshot, if any
        sel = self._system_config.get_active_selection()
        active_name = (sel.bbs_name or "").strip() if sel.bbs_name else ""

        if active_name and active_name in raw_names:
            # Active BBS goes first
            names = [active_name] + [n for n in raw_names if n != active_name]
        else:
            # No active BBS → insert a blank item so combo starts blank
            names = [""] + raw_names

        return names

    def list_bbs_calls(self) -> list[str]:
        """
        260609: !!!NOTACCESSED: does not look like it is called by anyone any more.
        Retrieve the list of BBS call signs for BBS connections
        """
        profiles = self._bbs_repo.list_profiles()
        # print(f">>>DEBUG EditorProfilesAdaptor.list_bbs_calls.profiles = {profiles}")
        raw_calls: list[str] = []

        for p in profiles:
            # Prefer bbs_call; fall back to "(Unassigned)"
            call = (getattr(p, "connect_call", "") or "").strip()
            if not call:
                call = (getattr(p, "bbs_call", "") or "").strip()
            if not call:
                call = "(Unassigned)"
            raw_calls.append(call)

        # No BBS profiles at all → single placeholder
        if not raw_calls:
            return ["(Unassigned)"]

        # Determine active BBS call from SystemConfigService snapshot, if any
        sel = self._system_config.get_active_selection()
        active_call = (sel.bbs_call or "").strip() if sel.bbs_call else ""

        if active_call and active_call in raw_calls:
            # Build the list of BBS calls with the Active BBS goes first
            calls = [active_call] + [c for c in raw_calls if c != active_call]
        else:
            # No active BBS → insert a blank item so combo starts blank
            calls = [""] + raw_calls

        return calls


class EditorAppSettings:
    """
    Adapter for SqliteMessageService: provides editor-specific "defaults".

    Implements the Outpost Classic default "From" logic:
        - If no active Station: blank
        - If Tactical enabled and a Tactical call is present: use Tactical call
        - Otherwise: use Station legal call

    Contract:
        Must provide get_default_from_call() -> str for SqliteMessageService.
    """

    def __init__(self, config: AppConfig, system_config: SystemConfigService) -> None:
        self._config = config
        self._system_config = system_config


    def get_default_from_call(self) -> str:
        """ 260426
        Return the default From: call for new outbound messages.

        Delegate to SystemConfigService so Tactical Call rules are centralized.
        Kept so SqliteMessageService does not need to know about SystemConfigService directly.
        """
        return self._system_config.get_default_from_call()

# ----------------------------------------------------------------------
# Application bootstrap
# ----------------------------------------------------------------------
def main() -> None:
    """
    Application entry point.

    Responsibilities:
    - Configure QSettings application identity (org/app names)
    - Create QApplication and apply platform-appropriate Qt style
    - Initialize AppConfig (QSettings wrapper)
    - Resolve database path and ensure required schema/seed rows exist
    - Construct repositories and services
    - Create and show the MainWindow
    - Start the Qt event loop

    Common startup failure points:
    - DB file path not writable (home directory permissions)
    - SQLite schema missing/out-of-date (ensure_folders_table_and_roots)
    - QSettings migration issues (AppConfig)
    """
    # Set names BEFORE anything that might create QSettings
    QtCore.QCoreApplication.setOrganizationName(AppInfo.ORG_NAME)
    QtCore.QCoreApplication.setApplicationName(AppInfo.APP_NAME)

    app = QtWidgets.QApplication(sys.argv)
    # make this the default icon for every window
    # app.setWindowIcon(QIcon(AppPaths.resource_path("polar3232.ico")))
    app.setWindowIcon(QIcon(AppPaths.app_icon()))
    apply_native_style()

    # App configuration wrapper (uses QSettings internally)
    config = AppConfig(AppInfo.ORG_NAME, AppInfo.APP_NAME)
    app_paths = AppPaths(app_name=AppInfo.APP_NAME)
    recent_config_service = RecentConfigService(app_paths.data_dir)
    seed_runtime_data(app_paths)

    # Core DB path
    db_path = app_db_path(app_paths)

    # Data layer for messages
    dao = MessageDAO(db_path)
    ensure_folders_table_and_roots(dao)

    repo_cfg = RepoConfig()
    msg_repo = MessageRepository(dao, repo_cfg)

    # Profile repositories
    station_repo = StationProfileRepository(db_path)
    tactical_repo = TacticalProfileRepository(db_path)
    bbs_repo = BBSProfileRepository(db_path)
    iface_repo = InterfaceProfileRepository(db_path)
    bbs_logons_repo = BBSLogonRepository(db_path)

    # System-wide active configuration coordinator
    system_config = SystemConfigService(
        config=config,
        station_repo=station_repo,
        tactical_repo=tactical_repo,
        bbs_repo=bbs_repo,
        iface_repo=iface_repo,
        bbs_logons_repo=bbs_logons_repo,
    )
    
    notification_service = NotificationService()

    # Adapters for the editor / message service
    profiles_adapter = EditorProfilesAdapter(bbs_repo, system_config)
    app_settings = EditorAppSettings(config, system_config)

    # SQLite-backed message service used by the editor/compose/view dialogs
    message_service = SqliteMessageService(
        msg_repo=msg_repo,
        profiles_repo=profiles_adapter,
        app_settings=app_settings,
    )

    # Main window (builds its own DAO/Repos for UI; gets message_service + system_config)
    win = MainWindow(
        db_path=db_path,
        config=config,
        message_service=message_service,
        system_config=system_config,
        app_paths=app_paths,
        notification_service=notification_service,
        recent_config_service=recent_config_service,
    )
    win.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
