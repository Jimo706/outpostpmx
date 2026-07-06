# data/tactical_profile_model.py
"""
Tactical profile model.

This module defines TacticalProfile, the persistence model representing an
*operational/tactical identity overlay* used during specific incidents, nets,
or deployments (EOC, Shelter, Field Team, etc.).

Architectural role:
- Stored by TacticalProfileRepository.
- Optionally combined with the active StationProfile at runtime during
  Send/Receive sessions and message composition.
- Provides the tactical callsign/location context and optional signature used
  to tag messages for the current operational role.

Conceptually, a TacticalProfile answers:
- What tactical callsign should I operate as right now?
- What location/function label should be associated with my traffic?
- What message ID prefix should be used for tactical message IDs?
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class TacticalProfile:
    """Represents a Tactical ID profile.

    A TacticalProfile is an optional overlay identity that may be enabled for a
    particular operation. It never replaces the legal StationProfile; it augments
    the sender identity and message metadata where appropriate.

    Fields
    ------
    id : Optional[int]
        Primary key in the tactical_profiles table (None for new/unsaved).
    tactical_call_sign : str
        Non-legal tactical call sign for a location/function (e.g. "CUPEOC").
        Typically normalized to uppercase by the repository.
    tactical_location : str
        Short description of where the tactical station is located.
    msg_id_prefix : str
        Up to 3 characters, [0-9A-Z], part of message ID generation.
        Required and user-specified (no auto-fill).
    signature : str
        Optional multi-line text that can be appended to the end of messages.
        Stored as-is.
    is_active : bool
        Whether this tactical profile is the currently active one.
        At most one can be active, but it is valid for NONE to be active.
    """
    id: Optional[int] = None
    tactical_call_sign: str = ""
    tactical_location: str = ""
    msg_id_prefix: str = ""
    signature: str = ""
    is_active: bool = False
