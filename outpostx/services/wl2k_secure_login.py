# services/wl2k_secure_login.py
"""
Winlink secure-login helpers.

Responsibilities:
- Detect a WL2K secure-login challenge in banner text (";PQ: nnnnnnnn")
- Compute the WL2K ";PR:" response from challenge + account password
- Build the client SID string sent by OutpostX during secure login

Background
----------
A typical Winlink login exchange is:

    [WL2K-...]
    ;PQ: 96511784
    CMS>
    [OUTPOST-3.8.10]
    ;PR: 83290120

The response algorithm is based on the Winlink reference implementation:

    MD5( ASCII(challenge + password) + salt )

Then form a positive 31-bit integer from the first 4 digest bytes:
    value = ((digest[3] & 0x3F) << 24) |
            ( digest[2]        << 16) |
            ( digest[1]        <<  8) |
              digest[0]

Format as 10 decimal digits and use the last 8 digits as the PR response.

Notes
-----
- This module is intentionally transport-agnostic.
- It does NOT send anything by itself; it only prepares values for the caller.
"""

from __future__ import annotations

import hashlib
import re
from typing import Optional


# ----------------------------------------------------------------------
# Regex helpers
# ----------------------------------------------------------------------

# Example matches:
#   ";PQ: 96511784"
#   ";PQ:12345678"
#   "  ;PQ: 89ABCDEF"
#
# We accept 1..32 hex-ish chars to be tolerant, but in practice Winlink
# challenges are typically 8 characters.
_WL2K_CHALLENGE_RE = re.compile(r";PQ:\s*([0-9A-Fa-f]{1,32})", re.IGNORECASE)

# Typical banner:
#   [WL2K-5.0-B2FWIHJM$]
_WL2K_SID_RE = re.compile(r"\[WL2K-[^\]]+\]", re.IGNORECASE)


# ----------------------------------------------------------------------
# Winlink salt from WinlinkAuth.vb
# ----------------------------------------------------------------------
_WL2K_SALT = bytes([
    77, 197, 101, 206, 190, 249, 93, 200,
    51, 243, 93, 237, 71, 94, 239, 138,
    68, 108, 70, 185, 225, 137, 217, 16,
    51, 122, 193, 48, 194, 195, 198, 175,
    172, 169, 70, 84, 61, 62, 104, 186,
    114, 52, 61, 168, 66, 129, 192, 208,
    187, 249, 232, 193, 41, 113, 41, 45,
    240, 16, 29, 228, 208, 228, 61, 20,
])


# ----------------------------------------------------------------------
# Detection helpers
# ----------------------------------------------------------------------
def is_wl2k_banner(text: str) -> bool:
    """
    Return True if the supplied text looks like Winlink banner/login text.

    This is intentionally broad:
    - WL2K SID present, or
    - secure-login challenge present.
    """
    if not text:
        return False
    return bool(_WL2K_SID_RE.search(text) or _WL2K_CHALLENGE_RE.search(text))


def extract_wl2k_challenge(text: str) -> Optional[str]:
    """
    Extract the WL2K secure-login challenge value from banner text.

    Returns:
        The challenge string (e.g. "96511784"), or None if not found.
    """
    if not text:
        return None

    m = _WL2K_CHALLENGE_RE.search(text)
    if not m:
        return None

    return m.group(1).strip()


def requires_wl2k_secure_login(text: str) -> bool:
    """
    Return True if the supplied text contains a WL2K secure-login request.
    """
    return extract_wl2k_challenge(text) is not None


# ----------------------------------------------------------------------
# Response calculation
# ----------------------------------------------------------------------
def _build_challenge_bytes(challenge: str, password: str) -> bytes:
    """
    Build the byte block hashed by the WL2K secure-login algorithm.

    Per Winlink reference logic:
        ASCII(challenge + password) + static salt
    """
    ch = (challenge or "").strip()
    pw = (password or "").strip()

    # Outpost/Winlink behavior is ASCII-oriented here.
    return (ch + pw).encode("ascii", errors="ignore") + _WL2K_SALT


def _process_digest_to_pr(digest: bytes) -> str:
    """
    Convert the 16-byte MD5 digest to the 8-digit WL2K PR value.
    """
    if len(digest) < 4:
        raise ValueError("MD5 digest is too short for WL2K processing")

    value = digest[3] & 0x3F
    value = (value << 8) | digest[2]
    value = (value << 8) | digest[1]
    value = (value << 8) | digest[0]

    # Format as 10 digits, then keep the last 8.
    return f"{value:010d}"[2:]


def compute_wl2k_pr_response(challenge: str, password: str) -> str:
    """
    Compute the WL2K ';PR:' response value for a given challenge/password pair.

    Args:
        challenge:
            The challenge text from ';PQ: <challenge>'
        password:
            The operator's Winlink account password

    Returns:
        8-digit decimal response string suitable for:
            ';PR: <response>'

    Raises:
        ValueError:
            If challenge or password is blank.
    """
    ch = (challenge or "").strip()
    pw = (password or "").strip()

    if not ch:
        raise ValueError("WL2K challenge is empty")
    if not pw:
        raise ValueError("WL2K password is empty")

    block = _build_challenge_bytes(ch, pw)
    digest = hashlib.md5(block).digest()
    return _process_digest_to_pr(digest)


def build_wl2k_pr_line(challenge: str, password: str) -> str:
    """
    Convenience helper that returns the full PR line to send.

    Example:
        ';PR: 83290120'
    """
    response = compute_wl2k_pr_response(challenge, password)
    return f";PR: {response}"


# ----------------------------------------------------------------------
# Client SID helpers
# ----------------------------------------------------------------------
def build_outpost_sid(major: int, minor: int, revision: int, *, prefix: str = "OUTPOST") -> str:
    """
    Build the client SID string in Classic Outpost style.

    Example:
        build_outpost_sid(3, 8, 10) -> '[OUTPOST-3.8.10]'

    Args:
        major:
            Major version number
        minor:
            Minor version number
        revision:
            Revision/build number
        prefix:
            SID prefix, defaults to 'OUTPOST'

    Returns:
        Bracketed SID string.
    """
    return f"[{prefix}-{int(major)}.{int(minor)}.{int(revision)}]"


def build_outpostx_sid(version_text: str, *, prefix: str = "OUTPOSTX") -> str:
    """
    Build a client SID string from a preformatted version string.

    Example:
        build_outpostx_sid('26.04.15') -> '[OUTPOSTX-26.04.15]'

    Args:
        version_text:
            Version text already formatted the way you want it to appear
        prefix:
            SID prefix, defaults to 'OUTPOSTX'

    Returns:
        Bracketed SID string.
    """
    v = (version_text or "").strip()
    if not v:
        raise ValueError("version_text is empty")
    return f"[{prefix}-{v}]"


# ----------------------------------------------------------------------
# High-level helper
# ----------------------------------------------------------------------
def prepare_wl2k_secure_login(
    banner_text: str,
    password: str,
    *,
    sid_text: str,
) -> tuple[str, str]:
    """
    High-level helper for callers that already have the received banner text.

    Args:
        banner_text:
            Accumulated received text containing WL2K banner/challenge
        password:
            Winlink account password
        sid_text:
            The client SID string to send, e.g. '[OUTPOSTX-26.04.15]'

    Returns:
        Tuple of:
            (sid_line, pr_line)

    Raises:
        ValueError:
            If no challenge is found or required inputs are empty.
    """
    challenge = extract_wl2k_challenge(banner_text)
    if not challenge:
        raise ValueError("No WL2K ';PQ:' challenge found in banner text")

    sid = (sid_text or "").strip()
    if not sid:
        raise ValueError("sid_text is empty")

    pr_line = build_wl2k_pr_line(challenge, password)
    return sid, pr_line