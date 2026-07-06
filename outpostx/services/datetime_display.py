# p139
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

"""
OutpostX date/time policy:

1. OutpostX-induced timestamps are stored as UTC ISO strings with Z.
   Example: 2026-05-19T02:34:25Z

2. BBS-reported timestamps are preserved as reported, but normalized to ISO shape.
   If the BBS reports UTC/Z, keep Z.
   If the BBS reports local/no timezone, store no-Z.

3. Display code must label the basis:
   - UTC   = explicit Z or timezone offset
   - Local = no timezone marker
"""

@dataclass(frozen=True)
class DisplayTimestamp:
    value: str
    basis: str       # "UTC", "Local", or ""
    display: str     # "2026-05-18 19:32:51 Local"


def classify_timestamp(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""

    upper = raw.upper()
    if upper.endswith("Z"):
        return "UTC"

    # Treat explicit offsets as UTC/absolute time for display labeling.
    # Examples: 2026-05-19T02:34:25+00:00
    if len(raw) >= 6 and (raw[-6] in ("+", "-")) and raw[-3] == ":":
        return "UTC"

    return "Local"


def format_timestamp(value: str, *, include_seconds: bool = False) -> DisplayTimestamp:
    raw = (value or "").strip()
    if not raw:
        return DisplayTimestamp(value="", basis="", display="")

    basis = classify_timestamp(raw)

    s = raw.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
        fmt = "%Y-%m-%d %H:%M:%S" if include_seconds else "%Y-%m-%d %H:%M"
        text = dt.strftime(fmt)
    except ValueError:
        text = raw

    display = f"{text} {basis}".strip()
    return DisplayTimestamp(value=text, basis=basis, display=display)