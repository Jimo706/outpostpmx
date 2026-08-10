# data/bbs_profile_repo.py
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from .bbs_profile_model import BBSProfile
from .bbs_profile_dao import BBSProfileDAO


class BBSProfileRepository:
    """
    Business-logic layer for BBS profiles.

    Responsibilities:
      - Provide a higher-level API over BBSProfileDAO
      - Enforce uniqueness of friendly_name
      - Implement Activate / New / Copy / Delete / Save behaviors
        described in the OutpostX IRS for Setup → BBS

    Scope notes:
      - This repository manages *what* a BBS profile is and its lifecycle.
      - It does not manage credentials (see BBSLogonRepository).
      - It does not manage NODE paths (see NodePathRepo).
    """

    def __init__(self, db_path: Path | str) -> None:
        """Create a repository bound to a SQLite database file."""
        self.dao = BBSProfileDAO(db_path)

    # ------------------------------------------------------------------
    # Basic queries
    # ------------------------------------------------------------------
    def list_profiles(self) -> List[BBSProfile]:
        """Return all profiles, sorted by friendly name (case-insensitive)."""
        return self.dao.list_profiles()

    def get(self, profile_id: int) -> Optional[BBSProfile]:
        """Return a BBS profile by id (or None if not found)."""
        return self.dao.get_profile(profile_id)

    def get_active(self) -> Optional[BBSProfile]:
        """Return the currently active BBS profile (or None)."""
        return self.dao.get_active()

    # ------------------------------------------------------------------
    # Creation / persistence
    # ------------------------------------------------------------------
    def new_profile(self) -> BBSProfile:
        """Return a new profile instance with all defaults."""
        return BBSProfile()

    def save(self, profile: BBSProfile) -> BBSProfile:
        """Insert or update a profile as appropriate.

        Enforces uniqueness of ``friendly_name`` at the repo layer so that UI
        code can present a friendlier error than a raw UNIQUE constraint.
        """
        existing = self.dao.get_by_name(profile.friendly_name)
        if existing and existing.id != profile.id:
            raise ValueError(
                f"A BBS profile named '{profile.friendly_name}' already exists."
            )

        if profile.id is None:
            profile.id = self.dao.insert_profile(profile)
        else:
            self.dao.update_profile(profile)
        return profile

    def delete(self, profile_id: int) -> None:
        """Delete a BBS profile by id (no-op if id does not exist)."""
        self.dao.delete_profile(profile_id)

    # ------------------------------------------------------------------
    # Copy / activate
    # ------------------------------------------------------------------
    def duplicate(self, profile_id: int) -> BBSProfile:
        """
        #147.  Resolved inconsistent behavior across configuration areas.
        Duplicate and persist an existing BBS profile.

        The copied profile:
        - receives a new database ID
        - is not active
        - receives a unique "(COPY)" name
        """
        original = self.get(profile_id)
        if original is None:
            raise ValueError(f"BBS profile {profile_id} does not exist")

        copy = BBSProfile(**vars(original))
        copy.id = None
        copy.is_active = False

        base_name = (original.friendly_name or "").strip()
        if not base_name:
            base_name = "Unnamed BBS"

        new_name = f"{base_name} (COPY)"
        suffix = 1

        while self.dao.get_by_name(new_name) is not None:
            new_name = f"{base_name} (COPY {suffix})"
            suffix += 1

        copy.friendly_name = new_name

        return self.save(copy)


    def set_active(self, profile_id: int) -> None:
        """
        Mark the specified profile as active and clear the active flag
        on all others.
        """
        self.dao.set_active(profile_id)
