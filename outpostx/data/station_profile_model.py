# data/station_profile_model.py
"""
Station profile model.

This module defines StationProfile, the persistence model representing the
*legal FCC identity* used by OutpostX when sending messages.

Architectural role:
- Stored by StationProfileRepository.
- Combined with an optional TacticalProfile at runtime during
  Send/Receive sessions and message composition.
- Provides the authoritative legal callsign and signature information.

Conceptually, a StationProfile answers:
- Who am I legally transmitting as?
- What callsign prefix should message IDs use?
- What default signature should be applied?
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class StationProfile:
    """
    Legal station identity profile.

    A StationProfile represents a gov't-issued callsign and operator identity.
    Exactly one StationProfile may be marked active at a time.

    Fields
    ------
    id : Optional[int]
        Primary key in the station_profiles table (None for new/unsaved).
    legal_call_sign : str
        FCC (or training) callsign used for MYCALL and message FROM defaults.
    user_name : str
        Operator name or label ("Jim O").
    msg_id_prefix : str
        Up to 3 characters, [0-9A-Z], used in local Message ID generation.
    signature : str
        Optional multi-line text that can be appended to the end of messages.
        Case-insensitive semantics; stored as-is. Default is blank.
    is_active : bool
        Exactly one profile should be active at any time (enforced in code).

    Notes
    -----
    * This profile represents *legal identity*, not operational/tactical identity.
    * Tactical profiles are layered on top and never replace this profile.
    * Callsigns and message ID prefixes are normalized to uppercase by the repository.
    """
    id: Optional[int] = None
    legal_call_sign: str = ""
    user_name: str = ""
    msg_id_prefix: str = ""
    signature: str = ""
    is_active: bool = False
