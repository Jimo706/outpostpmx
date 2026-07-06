# data/bbs_profile_dao.py
"""
BBS profile DAO (bbs_profiles table).

This module defines the SQLite Data Access Object responsible for storing and
retrieving BBSProfile records.

In OutpostX terms, a BBS Profile contains:
- The remote connect callsign and descriptive labels
- The command vocabulary used for send/list/read/kill/bye
- Retrieval policy flags (what to download and what to skip)
- Optional connect-time init commands
- Path selection (DIRECT/DIGI/NODE): DIGI fields live here; NODE hops are stored
  separately in NodePathRepo.

Use BBSProfileRepository for higher-level behavior (activate, duplicate, validation).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import List, Optional

from .bbs_profile_model import BBSProfile


class BBSProfileDAO:
    """Low-level SQLite DAO for BBS profiles.

    Architectural role:
      - Owns the SQLite schema for the `bbs_profiles` table.
      - Owns all SQL used to CRUD BBSProfile rows.
      - Performs row ↔ model mapping (BBSProfile dataclass).

    Boundaries:
      - No UI logic (that belongs in widgets/dialogs).
      - No workflow semantics (that belongs in BBSProfileRepository).
      - No credentials (that belongs in BBSLogonRepository).
      - No NODE path persistence (that belongs in NodePathRepo).

    Notes:
      - `friendly_name` is UNIQUE and is used as the human-facing identifier.
      - `is_active` is used to mark the single active profile. Enforced by
        repository/service logic; the DAO provides helper methods.
    """

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)

    # ------------------------------------------------------------------
    # Connection helper
    # ------------------------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        """Open a SQLite connection with Row mapping and foreign keys enabled."""
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    # ------------------------------------------------------------------
    # Schema management
    # ------------------------------------------------------------------
    def ensure_schema(self) -> None:
        """
        Ensure required table/indexes exist.

        This DAO self-initializes the `bbs_profiles` table and a UNIQUE index
        on friendly_name.
        """
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS bbs_profiles (
                    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                    friendly_name           TEXT NOT NULL,
                    connect_call            TEXT NOT NULL,
                    description             TEXT,
                    interface_name          TEXT,

                    cmd_send_private        TEXT NOT NULL DEFAULT 'SP',
                    cmd_send_bcast          TEXT NOT NULL DEFAULT 'SB',
                    cmd_send_nts            TEXT NOT NULL DEFAULT 'ST',
                    cmd_list_mine           TEXT NOT NULL DEFAULT 'LM',
                    cmd_list_bcast          TEXT NOT NULL DEFAULT 'LB',
                    cmd_list_nts            TEXT NOT NULL DEFAULT 'LT',
                    cmd_list_filtered       TEXT NOT NULL DEFAULT 'L>',
                    cmd_read_msg            TEXT NOT NULL DEFAULT 'R',
                    cmd_kill_msg            TEXT NOT NULL DEFAULT 'K',
                    cmd_bye                 TEXT NOT NULL DEFAULT 'B',

                    use_init_cmd            INTEGER NOT NULL DEFAULT 0,
                    cmd_before              TEXT,
                    cmd_after               TEXT,

                    retrieve_private        INTEGER NOT NULL DEFAULT 1,
                    retrieve_nts            INTEGER NOT NULL DEFAULT 0,
                    retrieve_bulletins      INTEGER NOT NULL DEFAULT 0,
                    delete_on_bbs           INTEGER NOT NULL DEFAULT 1,

                    skip_my_nts             INTEGER NOT NULL DEFAULT 0,
                    skip_my_bulletins       INTEGER NOT NULL DEFAULT 0,

                    retrieve_bulletins_mode TEXT NOT NULL DEFAULT 'ALL',
                    retrieve_selected       TEXT,
                    retrieve_custom         TEXT,

                    retrieve_my_bulletins   INTEGER NOT NULL DEFAULT 0,
                    retrieve_my_nts         INTEGER NOT NULL DEFAULT 0,

                    path_type               TEXT NOT NULL DEFAULT 'DIRECT',
                    path_via                TEXT,
                    digipeater_list         TEXT,
                    path_script             TEXT,
                    path_script_timeout     TEXT,

                    is_active               INTEGER NOT NULL DEFAULT 0
                );
                """
            )
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_bbs_profiles_name "
                "ON bbs_profiles(friendly_name);"
            )

    # ------------------------------------------------------------------
    # Mapping helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _row_to_model(row: sqlite3.Row) -> BBSProfile:
        """Convert a SQLite row into a BBSProfile instance."""
        return BBSProfile(
            id=row["id"],
            friendly_name=row["friendly_name"],
            connect_call=row["connect_call"],
            description=row["description"] or "",
            interface_name=row["interface_name"] or "",
            cmd_send_private=row["cmd_send_private"],
            cmd_send_bcast=row["cmd_send_bcast"],
            cmd_send_nts=row["cmd_send_nts"],
            cmd_list_mine=row["cmd_list_mine"],
            cmd_list_bcast=row["cmd_list_bcast"],
            cmd_list_nts=row["cmd_list_nts"],
            cmd_list_filtered=row["cmd_list_filtered"],
            cmd_read_msg=row["cmd_read_msg"],
            cmd_kill_msg=row["cmd_kill_msg"],
            cmd_bye=row["cmd_bye"],
            use_init_cmd=bool(row["use_init_cmd"]),
            cmd_before=row["cmd_before"] or "",
            cmd_after=row["cmd_after"] or "",
            retrieve_private=bool(row["retrieve_private"]),
            retrieve_nts=bool(row["retrieve_nts"]),
            retrieve_bulletins=bool(row["retrieve_bulletins"]),
            delete_on_bbs=bool(row["delete_on_bbs"]),
            skip_my_nts=bool(row["skip_my_nts"]),
            skip_my_bulletins=bool(row["skip_my_bulletins"]),
            retrieve_bulletins_mode=row["retrieve_bulletins_mode"],
            retrieve_selected=row["retrieve_selected"] or "",
            retrieve_custom=row["retrieve_custom"] or "",
            retrieve_my_bulletins=bool(row["retrieve_my_bulletins"]),
            retrieve_my_nts=bool(row["retrieve_my_nts"]),
            path_type=row["path_type"],
            path_via=row["path_via"] or "",
            digipeater_list=row["digipeater_list"] or "",
            path_script=row["path_script"] or "",
            path_script_timeout=row["path_script_timeout"] or "",
            is_active=bool(row["is_active"]),
        )

    @staticmethod
    def _model_to_params(profile: BBSProfile) -> dict:
        """Convert a BBSProfile (dict) into DB column → value parameters."""
        return {
            "friendly_name": profile.friendly_name,
            "connect_call": profile.connect_call,
            "description": profile.description,
            "interface_name": profile.interface_name,
            "cmd_send_private": profile.cmd_send_private,
            "cmd_send_bcast": profile.cmd_send_bcast,
            "cmd_send_nts": profile.cmd_send_nts,
            "cmd_list_mine": profile.cmd_list_mine,
            "cmd_list_bcast": profile.cmd_list_bcast,
            "cmd_list_nts": profile.cmd_list_nts,
            "cmd_list_filtered": profile.cmd_list_filtered,
            "cmd_read_msg": profile.cmd_read_msg,
            "cmd_kill_msg": profile.cmd_kill_msg,
            "cmd_bye": profile.cmd_bye,
            "use_init_cmd": int(profile.use_init_cmd),
            "cmd_before": profile.cmd_before,
            "cmd_after": profile.cmd_after,
            "retrieve_private": int(profile.retrieve_private),
            "retrieve_nts": int(profile.retrieve_nts),
            "retrieve_bulletins": int(profile.retrieve_bulletins),
            "delete_on_bbs": int(profile.delete_on_bbs),
            "skip_my_nts": int(profile.skip_my_nts),
            "skip_my_bulletins": int(profile.skip_my_bulletins),
            "retrieve_bulletins_mode": profile.retrieve_bulletins_mode,
            "retrieve_selected": profile.retrieve_selected,
            "retrieve_custom": profile.retrieve_custom,
            "retrieve_my_bulletins": int(profile.retrieve_my_bulletins),
            "retrieve_my_nts": int(profile.retrieve_my_nts),
            "path_type": profile.path_type,
            "path_via": profile.path_via,
            "path_script": profile.path_script, 
            "path_script_timeout": profile.path_script_timeout, 
            "digipeater_list": profile.digipeater_list,
            "is_active": int(profile.is_active),
        }

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    def list_profiles(self) -> List[BBSProfile]:
        """Return all BBS profiles ordered by friendly_name (case-insensitive)."""
        self.ensure_schema()
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT * FROM bbs_profiles ORDER BY friendly_name COLLATE NOCASE"
            )
            return [self._row_to_model(row) for row in cur.fetchall()]

    def get_profile(self, profile_id: int) -> Optional[BBSProfile]:
        """Return a profile by primary key id (or None if not found)."""
        self.ensure_schema()
        with self._connect() as conn:
            cur = conn.execute("SELECT * FROM bbs_profiles WHERE id=?", (profile_id,))
            row = cur.fetchone()
            return self._row_to_model(row) if row else None

    def get_by_name(self, friendly_name: str) -> Optional[BBSProfile]:
        """Return a profile by unique friendly_name (or None if not found)."""
        self.ensure_schema()
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT * FROM bbs_profiles WHERE friendly_name=?",
                (friendly_name,),
            )
            row = cur.fetchone()
            return self._row_to_model(row) if row else None

    def get_active(self) -> Optional[BBSProfile]:
        """Return the currently active BBS profile (or None)."""
        self.ensure_schema()
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT * FROM bbs_profiles WHERE is_active=1 LIMIT 1"
            )
            row = cur.fetchone()
            return self._row_to_model(row) if row else None

    def insert_profile(self, profile: BBSProfile) -> int:
        """Insert a new profile row and return the new id."""
        self.ensure_schema()
        params = self._model_to_params(profile)
        cols = ", ".join(params.keys())
        placeholders = ", ".join(["?"] * len(params))
        values = list(params.values())
        with self._connect() as conn:
            cur = conn.execute(
                f"INSERT INTO bbs_profiles ({cols}) VALUES ({placeholders})",
                values,
            )
            profile_id = cur.lastrowid
            conn.commit()
            return profile_id

    def update_profile(self, profile: BBSProfile) -> None:
        """Update an existing profile row (requires profile.id)."""
        if profile.id is None:
            raise ValueError("update_profile() requires profile.id to be set")

        self.ensure_schema()
        params = self._model_to_params(profile)
        assignments = ", ".join([f"{k}=?" for k in params.keys()])
        values = list(params.values()) + [profile.id]

        with self._connect() as conn:
            conn.execute(
                f"UPDATE bbs_profiles SET {assignments} WHERE id=?",
                values,
            )
            conn.commit()

    def delete_profile(self, profile_id: int) -> None:
        """Delete a profile row by id (no-op if id does not exist)."""
        self.ensure_schema()
        with self._connect() as conn:
            conn.execute("DELETE FROM bbs_profiles WHERE id=?", (profile_id,))
            conn.commit()

    def clear_active(self) -> None:
        """Clear the active flag on all profiles."""
        self.ensure_schema()
        with self._connect() as conn:
            conn.execute("UPDATE bbs_profiles SET is_active=0")
            conn.commit()

    def set_active(self, profile_id: int) -> None:
        """
        Mark exactly one profile as active.

        Implementation detail: clears is_active on all rows, then sets it on
        the given id.
        """
        self.ensure_schema()
        with self._connect() as conn:
            conn.execute("UPDATE bbs_profiles SET is_active=0")
            conn.execute(
                "UPDATE bbs_profiles SET is_active=1 WHERE id=?", (profile_id,)
            )
            conn.commit()
