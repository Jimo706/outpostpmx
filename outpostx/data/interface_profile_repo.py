from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import List, Optional

from .interface_profile_model import InterfaceProfile


class InterfaceProfileRepository:
    """
    SQLite-backed repository for Interface profiles.

    Design:
      - Stores the interface configuration as a JSON payload to allow
        UI evolution without schema churn.
      - Maintains a small set of indexed columns for identity and activation.

    Responsibilities:
      - Persist InterfaceProfile objects
      - Enforce unique interface_name (case-insensitive)
      - Manage the single-active-profile invariant

    Scope notes:
      - This repository does not interpret the payload contents.
      - Validation of payload fields is owned by the UI/widgets.
    """

    def __init__(self, db_path: Path | str) -> None:
        self._db = str(db_path)
        self._ensure_schema()

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _connect(self) -> sqlite3.Connection:
        """Open a SQLite connection with Row factory and foreign keys enabled."""
        conn = sqlite3.connect(self._db)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _ensure_schema(self) -> None:
        """Create the interface_profiles table if it does not exist."""
        sql = """
        CREATE TABLE IF NOT EXISTS interface_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            interface_name TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 0,
            payload TEXT NOT NULL,
            CONSTRAINT uq_interface_name UNIQUE(interface_name COLLATE NOCASE)
        );
        """
        with self._connect() as c:
            c.execute(sql)

    @staticmethod
    def _bool_to_int(value: bool) -> int:
        return 1 if value else 0

    @staticmethod
    def _int_to_bool(value: int | None) -> bool:
        return bool(value) if value is not None else False

    def _row_to_profile(self, row: sqlite3.Row) -> InterfaceProfile:
        """Convert a SQLite row into an InterfaceProfile instance."""
        data = {}
        payload = row["payload"]
        if payload:
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                data = {}
        return InterfaceProfile(
            id=row["id"],
            interface_name=row["interface_name"] or "",
            is_active=self._int_to_bool(row["is_active"]),
            data=data,
        )

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def list_profiles(self) -> List[InterfaceProfile]:
        """Return all interface profiles sorted by interface name."""
        sql = "SELECT * FROM interface_profiles ORDER BY interface_name COLLATE NOCASE"
        with self._connect() as c:
            rows = c.execute(sql).fetchall()
        return [self._row_to_profile(r) for r in rows]

    def get(self, profile_id: int) -> Optional[InterfaceProfile]:
        """Return an interface profile by id (or None if not found)."""
        sql = "SELECT * FROM interface_profiles WHERE id = ?"
        with self._connect() as c:
            row = c.execute(sql, (profile_id,)).fetchone()
        return self._row_to_profile(row) if row else None

    def get_active(self) -> Optional[InterfaceProfile]:
        """Return the currently active interface profile (or None)."""
        sql = "SELECT * FROM interface_profiles WHERE is_active = 1 ORDER BY id LIMIT 1"
        with self._connect() as c:
            row = c.execute(sql).fetchone()
        return self._row_to_profile(row) if row else None

    def new_profile(self) -> InterfaceProfile:
        """Return a new, unsaved interface profile with empty data dict."""
        return InterfaceProfile()

    def duplicate(self, profile_id: int) -> InterfaceProfile:
        """
        Create an unsaved copy of an existing interface profile.

        The copy has id=None and is_active=False, and its interface_name
        is suffixed with " (COPY)" to preserve uniqueness.
        """
        """
        Create an in-memory copy of an existing profile.

        The returned profile has id=None and is_active=False. The caller must
        call save() to persist it.

        For Interface:
            - The Interface Name is appended with " (COPY)".
        """
        original = self.get(profile_id)
        if original is None:
            raise ValueError(f"Interface profile {profile_id} does not exist")

        # Start with a shallow copy of the payload
        data = dict(original.data or {})

        # Determine base name from either the top-level or the payload
        base_name = (original.interface_name or "").strip()
        if not base_name:
            base_name = (data.get("interface_name") or "").strip()

        if base_name:
            new_name = f"{base_name} (COPY)"
        else:
            new_name = "Unnamed Interface (COPY)"

        # Keep payload and top-level name in sync
        data["interface_name"] = new_name

        copy = InterfaceProfile(
            id=None,
            interface_name=new_name,
            is_active=False,
            data=data,
        )
        return copy


    def delete(self, profile_id: int) -> None:
        """Delete an interface profile by id (no-op if id does not exist)."""
        sql = "DELETE FROM interface_profiles WHERE id = ?"
        with self._connect() as c:
            c.execute(sql, (profile_id,))

    def set_active(self, profile_id: int) -> None:
        """Mark the specified interface profile as active and clear others."""
        with self._connect() as c:
            c.execute("UPDATE interface_profiles SET is_active = 0")
            c.execute(
                "UPDATE interface_profiles SET is_active = 1 WHERE id = ?",
                (profile_id,),
            )

    def save(self, profile: InterfaceProfile) -> InterfaceProfile:
        """
        Insert or update an interface profile.

        Enforces:
          - non-empty interface_name
          - uniqueness of interface_name (case-insensitive)
        """
        name = (profile.interface_name or "").strip()
        if not name and isinstance(profile.data, dict):
            name = (profile.data.get("interface_name") or "").strip()
        if not name:
            raise ValueError("Interface Name is required.")

        payload = json.dumps(profile.data or {})

        with self._connect() as c:
            try:
                if profile.id is None:
                    sql = (
                        "INSERT INTO interface_profiles "
                        "(interface_name, is_active, payload) VALUES (?, ?, ?)"
                    )
                    cur = c.execute(
                        sql,
                        (name, self._bool_to_int(profile.is_active), payload),
                    )
                    profile.id = cur.lastrowid
                else:
                    sql = (
                        "UPDATE interface_profiles SET "
                        "interface_name = ?, is_active = ?, payload = ? "
                        "WHERE id = ?"
                    )
                    c.execute(
                        sql,
                        (name, self._bool_to_int(profile.is_active), payload, profile.id),
                    )
            except sqlite3.IntegrityError as e:
                msg = str(e).lower()
                if "unique" in msg and "interface_name" in msg:
                    raise ValueError(
                        f"An interface named '{name}' already exists."
                    ) from e
                raise

        profile.interface_name = name
        return profile
