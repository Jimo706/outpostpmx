"""
Interface profile model.

This module defines InterfaceProfile, the persistence model for interface
configuration in OutpostX.

Architectural role:
- Stored by InterfaceProfileRepository as an (id, interface_name, is_active, data) row.
- The `data` field is an opaque dict that holds the interface-specific payload
  (Serial/Telnet/SSH/AGWPE/etc.).
- The UI (InterfaceSetupWidget) owns the meaning and validation of `data` via
  to_dict() / from_dict() helpers.

Design notes:
- `interface_name` is the human-friendly identifier and is enforced as unique
  (case-insensitive) by the repository.
- `is_active` marks the currently selected profile. The "single active profile"
  invariant is enforced at the repository layer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class InterfaceProfile:
    """
    Row model for an Interface profile.

    We keep the actual Interface configuration as an opaque dict ``data``.
    The UI widget (InterfaceSetupWidget) already knows how to read
    and write this dict via to_dict() / from_dict().

    Top-level fields
    ----------------
    id
        Surrogate primary key in the database.
    interface_name
        Human-friendly name for this interface configuration. Also used as
        a unique key (case-insensitive) in the table.
    is_active
        Exactly one row may be marked active (enforced by repository logic).
    data
        Arbitrary key/value mapping representing the actual interface setup.
    """

    id: Optional[int] = None
    interface_name: str = ""
    is_active: bool = False
    data: Dict[str, Any] = field(default_factory=dict)

    @property
    def friendly_name(self) -> str:
        """
        Return a label suitable for list displays.

        Prefers the explicit top-level interface_name, and falls back to a
        "interface_name" value in the data payload (if present), otherwise a
        placeholder string.
        """
        base = self.interface_name.strip()
        if not base and isinstance(self.data, dict):
            base = str(self.data.get("interface_name", "")) or "<unnamed interface>"
        if not base:
            base = "<unnamed interface>"
        return base
