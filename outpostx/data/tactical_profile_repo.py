# data/tactical_profile_repo.py
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import List, Optional

from .tactical_profile_model import TacticalProfile


class TacticalProfileRepository:
    """SQLite-backed repository for Tactical ID profiles.

    A Tactical profile represents a *situational operating identity* used
    in place of the legal Station callsign for specific incidents, nets,
    or deployments (e.g., EOC, Shelter, Field Team).

    Responsibilities:
      - Persist TacticalProfile records
      - Enforce normalization and validation rules
      - Maintain the single-active-profile invariant

    Relationship to Station profiles:
      - Tactical profiles are optional overlays.
      - When active, they supplement (not replace) the Station profile
        during Send/Receive and message composition.

    Schema
    ------
      CREATE TABLE IF NOT EXISTS tactical_profiles (
          id                INTEGER PRIMARY KEY AUTOINCREMENT,
          tactical_call_sign TEXT NOT NULL UNIQUE,
          tactical_location  TEXT NOT NULL,
          msg_id_prefix      TEXT NOT NULL,
          signature          TEXT NOT NULL DEFAULT '',
          is_active          INTEGER NOT NULL DEFAULT 0
      );

    Notes
    -----
    * tactical_call_sign and msg_id_prefix are normalized to uppercase.
    * signature is stored as-is.
    * At most one row has is_active=1; however, it is valid for all to be 0.
    """

    def __init__(self, db_path: Path | str) -> None:
        """Create a repository bound to a SQLite database file."""
        self._db = str(db_path)
        self._ensure_schema()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        """Open a SQLite connection with Row factory and foreign keys enabled."""
        conn = sqlite3.connect(self._db)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _ensure_schema(self) -> None:
        """Create the tactical_profiles table if it does not exist."""
        sql = """
        CREATE TABLE IF NOT EXISTS tactical_profiles (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            tactical_call_sign TEXT NOT NULL UNIQUE,
            tactical_location  TEXT NOT NULL,
            msg_id_prefix      TEXT NOT NULL,
            signature          TEXT NOT NULL DEFAULT '',
            is_active          INTEGER NOT NULL DEFAULT 0
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

    def _row_to_profile(self, row: sqlite3.Row) -> TacticalProfile:
        return TacticalProfile(
            id=row["id"],
            tactical_call_sign=row["tactical_call_sign"] or "",
            tactical_location=row["tactical_location"] or "",
            msg_id_prefix=row["msg_id_prefix"] or "",
            signature=row["signature"] or "",
            is_active=self._int_to_bool(row["is_active"]),
        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    def list_profiles(self) -> List[TacticalProfile]:
        """Return all Tactical profiles ordered by tactical_call_sign."""
        sql = """
        SELECT id, tactical_call_sign, tactical_location,
               msg_id_prefix, signature, is_active
        FROM tactical_profiles
        ORDER BY tactical_call_sign COLLATE NOCASE
        """
        with self._connect() as c:
            rows = c.execute(sql).fetchall()
        return [self._row_to_profile(r) for r in rows]

    def get(self, profile_id: int) -> Optional[TacticalProfile]:
        """Return a Tactical profile by id (or None if not found)."""
        sql = """
        SELECT id, tactical_call_sign, tactical_location,
               msg_id_prefix, signature, is_active
        FROM tactical_profiles
        WHERE id = ?
        """
        with self._connect() as c:
            row = c.execute(sql, (profile_id,)).fetchone()
        return self._row_to_profile(row) if row else None

    def get_by_call(self, tactical_call_sign: str) -> Optional[TacticalProfile]:
        """Return a Tactical profile by callsign (case-insensitive)."""
        call = (tactical_call_sign or "").upper().strip()
        sql = """
        SELECT id, tactical_call_sign, tactical_location,
               msg_id_prefix, signature, is_active
        FROM tactical_profiles
        WHERE tactical_call_sign = ?
        """
        with self._connect() as c:
            row = c.execute(sql, (call,)).fetchone()
        return self._row_to_profile(row) if row else None

    def get_active(self) -> Optional[TacticalProfile]:
        """Return the active Tactical profile, if any."""
        sql = """
        SELECT id, tactical_call_sign, tactical_location,
               msg_id_prefix, signature, is_active
        FROM tactical_profiles
        WHERE is_active = 1
        ORDER BY id
        LIMIT 1
        """
        with self._connect() as c:
            row = c.execute(sql).fetchone()
        return self._row_to_profile(row) if row else None

    # ------------------------------------------------------------------
    # Factory / persistence
    # ------------------------------------------------------------------
    def new_profile(self) -> TacticalProfile:
        """Return a new, unsaved TacticalProfile with empty fields."""
        return TacticalProfile()

    def save(self, profile: TacticalProfile) -> TacticalProfile:
        """
        Insert or update a TacticalProfile.

        Enforces:
        * non-empty tactical_call_sign, tactical_location, msg_id_prefix
        * msg_id_prefix length ≤ 3
        * uniqueness of tactical_call_sign
        """
        call = (profile.tactical_call_sign or "").upper().strip()
        loc = (profile.tactical_location or "").strip()
        prefix = (profile.msg_id_prefix or "").upper().strip()
        signature = profile.signature or ""

        if not call:
            raise ValueError("Tactical Call Sign is required.")
        if not loc:
            raise ValueError("Tactical Location is required.")
        if not prefix:
            raise ValueError("Message ID Prefix is required.")
        if len(prefix) > 3:
            raise ValueError("Message ID Prefix must be at most 3 characters.")

        with self._connect() as c:
            try:
                if profile.id is None:
                    sql = """
                    INSERT INTO tactical_profiles
                        (tactical_call_sign, tactical_location,
                         msg_id_prefix, signature, is_active)
                    VALUES (?, ?, ?, ?, ?)
                    """
                    cur = c.execute(
                        sql,
                        (
                            call,
                            loc,
                            prefix,
                            signature,
                            self._bool_to_int(profile.is_active),
                        ),
                    )
                    profile.id = cur.lastrowid
                else:
                    sql = """
                    UPDATE tactical_profiles
                    SET tactical_call_sign = ?,
                        tactical_location  = ?,
                        msg_id_prefix      = ?,
                        signature          = ?,
                        is_active          = ?
                    WHERE id = ?
                    """
                    c.execute(
                        sql,
                        (
                            call,
                            loc,
                            prefix,
                            signature,
                            self._bool_to_int(profile.is_active),
                            profile.id,
                        ),
                    )
            except sqlite3.IntegrityError as e:
                msg = str(e).lower()
                if "unique" in msg and "tactical_call_sign" in msg:
                    raise ValueError(
                        f"A Tactical profile with call '{call}' already exists."
                    ) from e
                raise

        profile.tactical_call_sign = call
        profile.tactical_location = loc
        profile.msg_id_prefix = prefix
        profile.signature = signature
        return profile

    def delete(self, profile_id: int) -> None:
        """Delete a Tactical profile by id (no-op if id does not exist)."""
        sql = "DELETE FROM tactical_profiles WHERE id = ?"
        with self._connect() as c:
            c.execute(sql, (profile_id,))

    def set_active(self, profile_id: Optional[int]) -> None:
        """Set the active Tactical profile.

        If profile_id is None → all profiles become inactive.
        If an id is provided → that row becomes the *only* active one.
        """
        with self._connect() as c:
            c.execute("UPDATE tactical_profiles SET is_active = 0")
            if profile_id is not None:
                c.execute(
                    "UPDATE tactical_profiles SET is_active = 1 WHERE id = ?",
                    (profile_id,),
                )
