# data/station_profile_repo.py
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import List, Optional

from .station_profile_model import StationProfile


class StationProfileRepository:
    """
    SQLite-backed repository for Station (legal callsign) profiles.

    A Station profile represents the *legal identity* used when sending
    messages (FCC callsign, operator name, message ID prefix, signature).

    Responsibilities:
      - Persist StationProfile records
      - Enforce normalization and validation rules
      - Maintain the single-active-profile invariant

    Schema
    ------
      CREATE TABLE IF NOT EXISTS station_profiles (
          id              INTEGER PRIMARY KEY AUTOINCREMENT,
          legal_call_sign TEXT NOT NULL UNIQUE,
          user_name       TEXT NOT NULL,
          msg_id_prefix   TEXT NOT NULL,
          signature       TEXT NOT NULL DEFAULT '',
          is_active       INTEGER NOT NULL DEFAULT 0
      );

    Notes
    -----
    * legal_call_sign and msg_id_prefix are normalized to uppercase.
    * signature is stored as-is (case-insensitive semantics).
    * is_active is maintained so that at most one row has is_active=1.
    * If the table already exists without `signature`, it is added automatically.
    """

    def __init__(self, db_path: Path | str) -> None:
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
        """Create or migrate the station_profiles table as needed."""
        # Create table if needed
        create_sql = """
        CREATE TABLE IF NOT EXISTS station_profiles (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            legal_call_sign TEXT NOT NULL UNIQUE,
            user_name       TEXT NOT NULL,
            msg_id_prefix   TEXT NOT NULL,
            signature       TEXT NOT NULL DEFAULT '',
            is_active       INTEGER NOT NULL DEFAULT 0
        );
        """
        with self._connect() as c:
            c.execute(create_sql)

            # Migration: ensure 'signature' column exists
            info = c.execute("PRAGMA table_info(station_profiles)").fetchall()
            cols = {row["name"] for row in info}
            if "signature" not in cols:
                c.execute(
                    "ALTER TABLE station_profiles "
                    "ADD COLUMN signature TEXT NOT NULL DEFAULT ''"
                )

    @staticmethod
    def _bool_to_int(value: bool) -> int:
        return 1 if value else 0

    @staticmethod
    def _int_to_bool(value: int | None) -> bool:
        return bool(value) if value is not None else False

    def _row_to_profile(self, row: sqlite3.Row) -> StationProfile:
        """Convert a SQLite row into a StationProfile instance."""
        return StationProfile(
            id=row["id"],
            legal_call_sign=row["legal_call_sign"] or "",
            user_name=row["user_name"] or "",
            msg_id_prefix=row["msg_id_prefix"] or "",
            signature=row["signature"] or "",
            is_active=self._int_to_bool(row["is_active"]),
        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    def list_profiles(self) -> List[StationProfile]:
        """Return all Station profiles ordered by callsign (case-insensitive)."""
        sql = """
        SELECT id, legal_call_sign, user_name, msg_id_prefix, signature, is_active
        FROM station_profiles
        ORDER BY legal_call_sign COLLATE NOCASE
        """
        with self._connect() as c:
            rows = c.execute(sql).fetchall()
        return [self._row_to_profile(r) for r in rows]

    def get(self, profile_id: int) -> Optional[StationProfile]:
        """Return a Station profile by id (or None if not found)."""
        sql = """
        SELECT id, legal_call_sign, user_name, msg_id_prefix, signature, is_active
        FROM station_profiles
        WHERE id = ?
        """
        with self._connect() as c:
            row = c.execute(sql, (profile_id,)).fetchone()
        return self._row_to_profile(row) if row else None

    def get_by_call(self, legal_call_sign: str) -> Optional[StationProfile]:
        """Return a Station profile by legal callsign (case-insensitive)."""
        call = (legal_call_sign or "").upper().strip()
        sql = """
        SELECT id, legal_call_sign, user_name, msg_id_prefix, signature, is_active
        FROM station_profiles
        WHERE legal_call_sign = ?
        """
        with self._connect() as c:
            row = c.execute(sql, (call,)).fetchone()
        return self._row_to_profile(row) if row else None

    def get_active(self) -> Optional[StationProfile]:
        """Return the currently active Station profile (or None)."""
        sql = """
        SELECT id, legal_call_sign, user_name, msg_id_prefix, signature, is_active
        FROM station_profiles
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
    def new_profile(self) -> StationProfile:
        """Return a new, unsaved StationProfile with empty fields."""
        return StationProfile()

    def save(self, profile: StationProfile) -> StationProfile:
        """
        Insert or update a StationProfile.

        Enforces:
        * non-empty legal_call_sign, user_name, msg_id_prefix
        * Message ID prefix length ≤ 3
        * uniqueness of legal_call_sign (case-insensitive via UNIQUE constraint)
        """
        call = (profile.legal_call_sign or "").upper().strip()
        name = (profile.user_name or "").strip()
        prefix = (profile.msg_id_prefix or "").upper().strip()
        signature = (profile.signature or "")

        if not call:
            raise ValueError("User Call Sign is required.")
        if not name:
            raise ValueError("User Name is required.")
        if not prefix:
            raise ValueError("Message ID Prefix is required.")
        if len(prefix) > 3:
            raise ValueError("Message ID Prefix must be at most 3 characters.")

        with self._connect() as c:
            try:
                if profile.id is None:
                    # Insert
                    sql = """
                    INSERT INTO station_profiles
                        (legal_call_sign, user_name, msg_id_prefix, signature, is_active)
                    VALUES (?, ?, ?, ?, ?)
                    """
                    cur = c.execute(
                        sql,
                        (
                            call,
                            name,
                            prefix,
                            signature,
                            self._bool_to_int(profile.is_active),
                        ),
                    )
                    profile.id = cur.lastrowid
                else:
                    # Update
                    sql = """
                    UPDATE station_profiles
                    SET legal_call_sign = ?,
                        user_name       = ?,
                        msg_id_prefix   = ?,
                        signature       = ?,
                        is_active       = ?
                    WHERE id = ?
                    """
                    c.execute(
                        sql,
                        (
                            call,
                            name,
                            prefix,
                            signature,
                            self._bool_to_int(profile.is_active),
                            profile.id,
                        ),
                    )
            except sqlite3.IntegrityError as e:
                msg = str(e).lower()
                if "unique" in msg and "legal_call_sign" in msg:
                    raise ValueError(
                        f"A Station profile with call '{call}' already exists."
                    ) from e
                raise

        profile.legal_call_sign = call
        profile.user_name = name
        profile.msg_id_prefix = prefix
        profile.signature = signature
        return profile

    def delete(self, profile_id: int) -> None:
        """Delete a Station profile by id (no-op if id does not exist)."""
        sql = "DELETE FROM station_profiles WHERE id = ?"
        with self._connect() as c:
            c.execute(sql, (profile_id,))

    def set_active(self, profile_id: Optional[int]) -> None:
        """Mark the given profile as active; all others become inactive.

        If profile_id is None, all profiles become inactive.
        """
        with self._connect() as c:
            c.execute("UPDATE station_profiles SET is_active = 0")
            if profile_id is not None:
                c.execute(
                    "UPDATE station_profiles SET is_active = 1 WHERE id = ?",
                    (profile_id,),
                )
