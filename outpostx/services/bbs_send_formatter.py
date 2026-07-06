# services/bbs_send_formatter.py
"""
BBS outbound send formatter.

Builds BBS-specific outbound send blocks from a stored OutpostX message.

This keeps SendReceiveSession focused on transport/session orchestration while
isolating protocol-specific send formatting here.

Initial multi-destination policy:
- KPC3/PBBS: fan out into one SP send block per destination
- JNOS: single destination uses SP; multiple destination uses SC + continuation line
- Winlink/BPQ: use SP with semicolon-separated destinations
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SendBlock:
    """
    One complete outbound BBS send transaction prefix.

    SendReceiveSession will append:
      - subject line
      - body lines
      - end-of-message marker
    """
    command_line: str
    extra_address_lines: list[str]


def parse_destinations(to_field: str) -> list[str]:
    """
    Normalize simple packet-style multi-destination addressing.

    Accepts:
      CALL1
      CALL1 CALL2
      CALL1,CALL2
      CALL1;CALL2

    Returns:
      ["CALL1", "CALL2"]

    Phase 1 intentionally supports simple packet/Winlink style addresses only.
    It does not attempt full RFC822 parsing.
    """
    text = (to_field or "").strip()
    if not text:
        return []

    normalized = (
        text.replace(",", ";")
            .replace(" ", ";")
    )

    destinations: list[str] = []
    seen: set[str] = set()

    for part in normalized.split(";"):
        dest = part.strip()
        if not dest:
            continue

        key = dest.upper()
        if key in seen:
            continue

        seen.add(key)
        destinations.append(dest)

    return destinations


def get_spec_id(adapter: Any) -> str:
    """
    Return the bound BBS spec id, if available.

    Examples:
      kpc3
      jnos
      wl2k
      bpq
    """
    spec = getattr(adapter, "spec", None)
    if spec is not None:
        sid = getattr(spec, "id", "") or ""
        if sid:
            return str(sid).strip().lower()

        raw = getattr(spec, "raw", None) or {}
        sid = raw.get("id", "")
        if sid:
            return str(sid).strip().lower()

    raw = getattr(getattr(adapter, "_spec", None), "raw", None) or {}
    sid = raw.get("id", "")
    return str(sid).strip().lower()


def _base_send_token(msg: Any, adapter: Any) -> str:
    """
    Determine the base BBS send command token.

    Uses adapter.build_send_command(msg) to preserve existing private/bulletin/NTS
    behavior, but keeps only the command token.

    Examples:
      SP
      SB
      ST
    """
    try:
        full_cmd = adapter.build_send_command(msg)
        if full_cmd:
            token = str(full_cmd).split()[0].strip()
            if token:
                return token
    except Exception:
        pass

    return "SP"


def build_send_blocks(adapter: Any, msg: Any) -> list[SendBlock]:
    """
    Build one or more BBS-specific send blocks for this outbound message.

    The message body and end marker are not included here; SendReceiveSession
    appends those consistently after each block.
    """
    to_field = (
        getattr(msg, "to_call", None)
        or getattr(msg, "to", None)
        or ""
    )

    destinations = parse_destinations(str(to_field))
    if not destinations:
        raise ValueError("Outbound message has no destination address")

    spec_id = get_spec_id(adapter)
    token = _base_send_token(msg, adapter)

    # KPC3/PBBS: no native multi-destination send; fan out one message per dest.
    if spec_id == "kpc3":
        return [
            SendBlock(command_line=f"{token} {dest}".strip(), extra_address_lines=[])
            for dest in destinations
        ]

    # JNOS: single destination = SP; multiple destinations = SC + continuation line.
    if spec_id == "jnos":
        if len(destinations) == 1:
            return [
                SendBlock(command_line=f"{token} {destinations[0]}".strip(), extra_address_lines=[])
            ]

        first = destinations[0]
        rest = ";".join(destinations[1:])
        return [
            SendBlock(
                command_line=f"SC {first}".strip(),
                extra_address_lines=[rest] if rest else [],
            )
        ]

    # Winlink and BPQ: SP with semicolon-separated destination list.
    if spec_id in ("wl2k", "bpq"):
        joined = ";".join(destinations)
        return [
            SendBlock(command_line=f"{token} {joined}".strip(), extra_address_lines=[])
        ]

    # Conservative fallback: preserve existing single-command behavior.
    joined = ";".join(destinations)
    return [
        SendBlock(command_line=f"{token} {joined}".strip(), extra_address_lines=[])
    ]