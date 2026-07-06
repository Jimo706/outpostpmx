# app_config.py
""" 260118
Application Configuration Management (AppConfig)

This module provides a centralized, persistent configuration service for OutpostX.
It is the single source of truth for application-wide settings that must survive
across runs, reboots, and user sessions.

Design goals:
- Provide a simple, stable API for reading and writing global settings.
- Abstract away platform-specific storage details (QSettings).
- Support non-admin users and strict IT environments.
- Establish clear ownership boundaries between configuration, UI, and services.

What belongs here:
- Application-scoped settings (data directory, session counters, preferences)
- Persistent UI state (window geometry, last-used selections)
- Global counters (e.g., Send/Receive session number)
- Defaults that may be overridden by user choice

What does NOT belong here:
- Runtime-only state
- Business logic
- Per-message or per-session transient data
- UI widgets or dialogs

Key concepts:
- QSettings-backed storage ensures cross-platform persistence.
- All paths written by OutpostX (DB, logs, exports) must derive from get_data_dir().
- Settings keys are namespaced (e.g., "App/...", "SendReceive/...") to avoid collision.
- Values are stored in a human-readable, inspectable form when possible.

Data directory policy:
- The application data directory is user-writable and platform-appropriate.
- It is created automatically if missing.
- The chosen directory is persisted and reused on subsequent runs.
- Future UI may allow the user to change this location explicitly.

This module intentionally has no dependencies on Send/Receive, BBS logic, or UI
components, allowing it to be safely imported anywhere in the application.

Stability note:
- Changes to AppConfig APIs should be rare and deliberate.
- Any change here affects the entire application.
"""
# 251112: Migrate from QtPy5 to PySide6; added 'set' and 'get'

from PySide6.QtCore import QSettings, QByteArray
from PySide6 import QtCore   # <-- needed for QByteArray.fromHex, types, etc.
from pathlib import Path

from services.app_info import AppInfo

class AppConfig:
    def __init__(self, org=AppInfo.ORG_NAME, app=AppInfo.APP_NAME):
        self.settings = QSettings(org, app)

    def get_value(self, key: str, default=None):
        return self.settings.value(key, default)

    def set_value(self, key: str, value):
        self.settings.setValue(key, value)

    # Dict-style aliases (used in UI code for simplicity)
    def get(self, key: str, default=None):
        """Return a stored setting value (dict-like alias for QSettings.value)."""
        return self.settings.value(key, default)

    def set(self, key: str, value):
        """Save a setting value (dict-like alias for QSettings.setValue)."""
        self.settings.setValue(key, value)        

    # optional helpers for UI windows
    def save_window_state(self, widget, name):
        geom = bytes(widget.saveGeometry().toHex()).decode()
        self.set_value(f"{name}/geometry", geom)

        # 260101, Some widgets’ saveState() can return empty early in life. This is an optional guard 
        if hasattr(widget, "saveState"):
            ba = widget.saveState()
            if not ba.isEmpty():
                state = bytes(ba.toHex()).decode()
                self.set_value(f"{name}/state", state)

        # 260101, replace with above
        # # if hasattr(widget, "saveState"):
        #     state = bytes(widget.saveState().toHex()).decode()
        #     self.set_value(f"{name}/state", state)

    def restore_window_state(self, widget, name):
        geom = self.get_value(f"{name}/geometry")
        if geom:
            widget.restoreGeometry(QtCore.QByteArray.fromHex(geom.encode()))
        state = self.get_value(f"{name}/state")
        if state and hasattr(widget, "restoreState"):
            widget.restoreState(QtCore.QByteArray.fromHex(state.encode()))


    # ---------------------------------
    # Define a canonical data directory
    # ---------------------------------
    def get_data_dir(self) -> Path: 
        """
        Return the writable OutpostX data directory.

          * Windows:  C:\\Users\\<user>\\AppData\\Local\\OutpostX
          * Linux:    ~/.local/share/OutpostX
          * macOS:    ~/Library/Application Support/OutpostX

        Resolution order:
        1. User override stored in settings
        2. Platform default from Qt AppDataLocation

        This directory is used for user-writable application data such as:
          - outpostx.db
          - logs
          - exports
          - backups
        """
        # 1) User override (stored)
        # stored in the registry    'Computer\HKEY_CURRENT_USER\Software\OutpostX\App'
        v = self.settings.value("App/data_dir")     
        if v:
            p = Path(str(v)).expanduser().resolve()
            ## print(f"DEBUG: data_dir override -> {p}")

            p.mkdir(parents=True, exist_ok=True)
            return p

        # 2) Cross-platform default via Qt
        base = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.AppDataLocation)
        p = Path(base).expanduser().resolve()
        ## print(f"DEBUG: data_dir default -> {p}")

        p.mkdir(parents=True, exist_ok=True)

        # Persist it
        self.settings.setValue("App/data_dir", str(p))
        return p