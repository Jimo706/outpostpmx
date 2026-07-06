# data/bbs_logon_model.py
"""
BBS logon model.

This module defines the dataclass used to represent stored BBS login credentials.

Architectural role:
- Persistence model for the `bbs_logons` table (see BBSLogonRepository).
- Used by setup/UI to create, edit, select, and pass credential sets into a
  Send/Receive session.

Normalization / matching:
- `bbs_connect_call` and `login_username` are typically normalized to UPPERCASE
  by the repository on save to support case-insensitive matching.

Security note:
- Password fields are stored in plaintext in SQLite in the current design.
  Treat your OutpostX database file as sensitive; future enhancement could use
  OS keychain integration or encryption-at-rest.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class BBSLogon:
    """
    Credential mapping for a session/operator logging into a remote BBS.

    Identity:
      - bbs_connect_call: the remote BBS callsign used for connection/login lookup
      - operator_id: the active operator identity for this session
                     (typically tactical call if active, otherwise legal call)
      - logon_name: user-facing label for this credential entry

    Notes:
      - login_username/account_password may be blank for BBSs that do not require them.
      - This model is intentionally small and transport-agnostic.
    """
    logon_id: Optional[int] = None
    bbs_connect_call: str = ""
    operator_id: str = ""
    logon_name: str = ""
    login_username: str = ""
    account_password: str = ""
    access_password: str = ""

    @classmethod
    def from_row(cls, row) -> "BBSLogon":
        def _get(name: str, default=None):
            try:
                return row[name]
            except Exception:
                try:
                    return row.get(name, default)
                except Exception:
                    return default

        return cls(
            logon_id=_get("logon_id"),
            bbs_connect_call=(str(_get("bbs_connect_call", "")) or "").strip(),
            operator_id=(str(_get("operator_id", "")) or "").strip(),
            logon_name=(str(_get("logon_name", "")) or "").strip(),
            login_username=(str(_get("login_username", "")) or "").strip(),
            account_password=(str(_get("account_password", "")) or "").strip(),
            access_password=(str(_get("access_password", "")) or "").strip(),
        )


@dataclass
class BBSLogonProfile:
    """Represents a BBS Logon record.

    Fields
    ------
    id : Optional[int]
        Primary key in the bbs_logons table (None for new/unsaved).
    bbs_connect_call : str
        Friendly name of the BBS that requires a login (e.g., "W1XSC-1", "WINLINK").
    login_username : str
        User login name (FCC callsign, tactical, etc.). Uppercased on save.
    account_password : str
        Required account password. Stored as entered (case-insensitive semantics).
    access_password : str
        Optional access password (e.g., Winlink). Stored as entered.
    """
    id: Optional[int] = None
    bbs_connect_call: str = ""
    login_username: str = ""
    account_password: str = ""
    access_password: str = ""
