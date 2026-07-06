# services/notification_service.py

"""
Notification Service

Purpose
-------
Provide a central location for application notifications that should
remain visible to the user until dismissed.

Notifications are maintained in memory only. They persist for the
lifetime of the OutpostX process and are discarded when the application
exits.

Typical uses:

    - Send/Receive failures
    - COM port errors
    - Connection failures
    - Missing configuration warnings
    - Informational status messages

Design Goals
------------
- Extremely lightweight
- No database storage
- No log-file dependency
- No threading requirements
- No UI dependencies

The service simply stores notifications and notifies any subscribed
listeners when new notifications arrive.

The NotificationWindow (or future UI components) can subscribe to the
service and update automatically.
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable


class NotificationService:
    """
    In-memory notification repository.

    Notifications are stored as formatted strings:

        10-Jun 16:42:18: ERROR, Could not open COM3

    A simple callback mechanism allows UI components to be notified
    whenever a new notification is added.
    """

    def __init__(self) -> None:
        """
        Initialize an empty notification store.
        """
        self._messages: list[str] = []
        self._listeners: list[Callable[[str], None]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, severity: str, message: str) -> None:
        """
        Add a notification.

        Args:
            severity:
                INFO, WARN, ERROR

            message:
                Human-readable notification text.
        """
        timestamp = datetime.now().strftime("%d-%b %H:%M:%S")

        entry = f"{timestamp}: {severity}, {message}"

        self._messages.append(entry)

        self._notify(entry)

    def info(self, message: str) -> None:
        """
        Add an informational notification.
        """
        self.add("INFO", message)

    def warn(self, message: str) -> None:
        """
        Add a warning notification.
        """
        self.add("WARN", message)

    def error(self, message: str) -> None:
        """
        Add an error notification.
        """
        self.add("ERROR", message)

    def messages(self) -> list[str]:
        """
        Return a copy of all notifications.

        Returns:
            List of formatted notification strings.
        """
        return list(self._messages)

    def clear(self) -> None:
        """
        Remove all stored notifications.

        Existing windows may choose to refresh themselves after
        calling this method.
        """
        self._messages.clear()

    def count(self) -> int:
        """
        Return the number of stored notifications.
        """
        return len(self._messages)

    # ------------------------------------------------------------------
    # Listener Support
    # ------------------------------------------------------------------

    def subscribe(self, callback: Callable[[str], None]) -> None:
        """
        Register a listener callback.

        The callback will be invoked whenever a new notification is
        added.

        Example:

            notification_service.subscribe(
                my_window.on_notification_added
            )
        """
        if callback not in self._listeners:
            self._listeners.append(callback)

    def unsubscribe(self, callback: Callable[[str], None]) -> None:
        """
        Remove a previously registered listener.
        """
        if callback in self._listeners:
            self._listeners.remove(callback)

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    def _notify(self, entry: str) -> None:
        """
        Notify all registered listeners of a new notification.

        Listener exceptions are ignored so that one misbehaving UI
        component cannot prevent other listeners from receiving the
        notification.
        """
        for callback in self._listeners:
            try:
                callback(entry)
            except Exception:
                pass
            