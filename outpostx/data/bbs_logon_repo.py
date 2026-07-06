# data/bbs_logon_repo.py
"""BBS Logon profile persistence.

This module stores per-BBS user credentials used during BBS login.
It intentionally separates logon credentials from the BBS profile so
multiple logons can be maintained for the same BBS.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import List, Optional

from .bbs_logon_model import BBSLogonProfile, BBSLogon


class BBSLogonRepository:
    """SQLite-backed repository for BBS Logon profiles.

    A BBS Logon profile represents the credential set needed to authenticate
    to a specific BBS (often a PBBS, JNOS BBS, etc.). The effective identity is
    the pair (bbs_connect_call, login_username), which is unique.

    Normalization rules:
      - bbs_connect_call and login_username are normalized to UPPERCASE for matching.
      - passwords are stored exactly as entered (no normalization).

    Security note:
      - Passwords are currently stored in plaintext in SQLite.
        For a future enhancement, consider OS keychain integration or encryption.

    Schema
    ------
      CREATE TABLE IF NOT EXISTS bbs_logons (
          id               INTEGER PRIMARY KEY AUTOINCREMENT,
          bbs_connect_call TEXT NOT NULL,
          login_username    TEXT NOT NULL,
          account_password  TEXT NOT NULL,
          access_password   TEXT,
          UNIQUE(bbs_connect_call, login_username)
      );

    Notes
    -----
    * bbs_connect_call and login_username are normalized to uppercase.
    * account_password and access_password are stored as entered.
    * (bbs_connect_call, login_username) is unique, matching the "<bbs>-<logon>"
      identity in the IRS.
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
        """Create the bbs_logons table if it does not exist."""
        sql = """
        CREATE TABLE IF NOT EXISTS bbs_logons (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            bbs_connect_call TEXT NOT NULL,
            login_username    TEXT NOT NULL,
            account_password  TEXT NOT NULL,
            access_password   TEXT,
            UNIQUE (bbs_connect_call, login_username)
        );
        """
        with self._connect() as c:
            c.execute(sql)

    def _row_to_profile(self, row: sqlite3.Row) -> BBSLogonProfile:
        """Convert a SQLite Row to a BBSLogonProfile dataclass."""
        return BBSLogonProfile(
            id=row["id"],
            bbs_connect_call=row["bbs_connect_call"] or "",
            login_username=row["login_username"] or "",
            account_password=row["account_password"] or "",
            access_password=row["access_password"] or "",
        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    def list_profiles(self) -> List[BBSLogonProfile]:
        """Return all BBS Logon profiles ordered by BBS name and user logon."""
        sql = """
        SELECT id, bbs_connect_call, login_username,
               account_password, access_password
        FROM bbs_logons
        ORDER BY bbs_connect_call COLLATE NOCASE,
                 login_username COLLATE NOCASE
        """
        with self._connect() as c:
            rows = c.execute(sql).fetchall()
        return [self._row_to_profile(r) for r in rows]

    def get(self, profile_id: int) -> Optional[BBSLogonProfile]:
        """Return a logon profile by primary key id (or None if not found)."""
        sql = """
        SELECT id, bbs_connect_call, login_username,
               account_password, access_password
        FROM bbs_logons
        WHERE id = ?
        """
        with self._connect() as c:
            row = c.execute(sql, (profile_id,)).fetchone()
        return self._row_to_profile(row) if row else None

    def find(self, bbs_name: str, user_logon: str) -> Optional[BBSLogonProfile]:
        """
        Lookup by (BBS name, user logon) pair.

        Inputs are normalized to uppercase for matching.
        """
        bbs = (bbs_name or "").upper().strip()
        user = (user_logon or "").upper().strip()
        sql = """
        SELECT id, bbs_connect_call, login_username,
               account_password, access_password
        FROM bbs_logons
        WHERE bbs_connect_call = ? AND login_username = ?
        """
        with self._connect() as c:
            row = c.execute(sql, (bbs, user)).fetchone()
        return self._row_to_profile(row) if row else None

    # ------------------------------------------------------------------
    # Factory / persistence
    # ------------------------------------------------------------------
    def new_profile(self) -> BBSLogonProfile:
        """Return a new, unsaved BBSLogonProfile with empty fields."""
        return BBSLogonProfile()

    def save(self, profile: BBSLogonProfile) -> BBSLogonProfile:
        """Insert or update a BBS Logon profile.

        Enforces:
        * non-empty bbs_connect_call, login_username, account_password
        * uniqueness of (bbs_connect_call, login_username)

        Returns:
            The saved profile with normalized fields and id populated.
        """
        bbs = (profile.bbs_connect_call or "").upper().strip()
        user = (profile.login_username or "").upper().strip()
        account = (profile.account_password or "")
        access = (profile.access_password or "")

        if not bbs:
            raise ValueError("BBS Name is required.")
        if not user:
            raise ValueError("Logon Name is required.")
        if not account:
            raise ValueError("Account Password is required.")

        with self._connect() as c:
            try:
                if profile.id is None:
                    sql = """
                    INSERT INTO bbs_logons
                        (bbs_connect_call, login_username,
                         account_password, access_password)
                    VALUES (?, ?, ?, ?)
                    """
                    cur = c.execute(sql, (bbs, user, account, access))
                    profile.id = cur.lastrowid
                else:
                    sql = """
                    UPDATE bbs_logons
                    SET bbs_connect_call = ?,
                        login_username    = ?,
                        account_password  = ?,
                        access_password   = ?
                    WHERE id = ?
                    """
                    c.execute(sql, (bbs, user, account, access, profile.id))
            except sqlite3.IntegrityError as e:
                msg = str(e).lower()
                if "unique" in msg:
                    raise ValueError(
                        f"A BBS Logon for '{bbs}-{user}' already exists."
                    ) from e
                raise

        profile.bbs_connect_call = bbs
        profile.login_username = user
        profile.account_password = account
        profile.access_password = access
        return profile

    def delete(self, profile_id: int) -> None:
        """Delete a logon profile by id (no-op if id does not exist)."""
        sql = "DELETE FROM bbs_logons WHERE id = ?"
        with self._connect() as c:
            c.execute(sql, (profile_id,))

    def duplicate(self, profile_id: int) -> BBSLogonProfile:
        """
        Duplicate a profile.

        Creates a new profile with the same BBS name and passwords, and a
        modified Logon Name (adds " (COPY)" / " (COPY N)") to keep the
        (bbs_connect_call, login_username) pair unique.
        """
        original = self.get(profile_id)
        if original is None:
            raise ValueError("BBS Logon profile to copy does not exist.")

        base_user = original.login_username
        new_user = f"{base_user} (COPY)"

        # Ensure uniqueness
        suffix = 1
        while self.find(original.bbs_connect_call, new_user) is not None:
            new_user = f"{base_user} (COPY {suffix})"
            suffix += 1

        new_profile = BBSLogonProfile(
            bbs_connect_call=original.bbs_connect_call,
            login_username=new_user,
            account_password=original.account_password,
            access_password=original.access_password,
        )
        return self.save(new_profile)


    def get_by_connect_call_and_operator(self, connect_call: str, operator_id: str) -> BBSLogon | None:
        """
        Retrieve BBS logon credentials for a given
        BBS connect call and operator identity.

        called by: services.system_config_service.py
        rev: 260310: added for bbs_logon support
        rev: 260311: corrected sql column names, pass.
        """
        sql = """
            SELECT *
            FROM bbs_logons
            WHERE bbs_connect_call = ?
            AND login_username = ?
            LIMIT 1
        """
        # row = self._dao.fetchone(sql, (connect_call, operator_id))

        with self._connect() as c:
            row = c.execute(sql, (connect_call, operator_id)).fetchone()
            ## CONFIRMED:  print(dict(row))

        if not row:
            return None
        ## CONFIRMED:  print(f">>>>> row={row} <<<<<")

        return BBSLogon.from_row(row)