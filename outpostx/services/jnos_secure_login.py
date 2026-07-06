from __future__ import annotations

import hashlib
import re


_JNOS_CHALLENGE_RX = re.compile(
    r"Password\s*\[([0-9A-Fa-f]{8})\]\s*:",
    re.IGNORECASE,
)


def check_jnos_secure_login(password: str, prompt_text: str) -> str:
    """
    Return the JNOS secure-login response if the prompt contains a bracketed
    8-hex-digit challenge. Otherwise return the original password unchanged.

    This intentionally mirrors Outpost Classic behavior:
      - "Password:"                -> clear-text password
      - "Password [12345678]:"     -> hashed 16-char response
    """
    password = "" if password is None else str(password)
    prompt_text = "" if prompt_text is None else str(prompt_text)

    m = _JNOS_CHALLENGE_RX.search(prompt_text)
    if not m:
        return password

    challenge = m.group(1)
    return jnos_get_md5_response(challenge, password)


def jnos_get_md5_response(challenge: str, password: str) -> str:
    """
    Compute the JNOS MD5 response from the 8-char challenge and the password.

    Compatible with Outpost Classic:
      1) process challenge into a 32-bit integer
      2) convert to 4-byte little-endian array
      3) MD5(challenge_bytes + password_bytes)
      4) return first 16 hex chars, lowercase
    """
    challenge_value = jnos_process_challenge(challenge)
    challenge_bytes = challenge_value.to_bytes(4, byteorder="little", signed=False)
    password_bytes = password.encode("latin-1", errors="replace")

    digest = hashlib.md5(challenge_bytes + password_bytes).hexdigest()
    return digest[:16].lower()


def jnos_process_challenge(challenge: str) -> int:
    """
    Convert the 8-character challenge into a 32-bit integer using the same
    nibble-processing logic as Outpost Classic / JNOS notes.
    """
    if challenge is None:
        raise ValueError("challenge is required")

    s = str(challenge).strip()
    if len(s) != 8:
        raise ValueError(f"JNOS challenge must be exactly 8 chars, got {s!r}")

    calc = 0
    for ch in s:
        one_byte = ord(ch) & 0x7F
        calc = (calc << 4) & 0xFFFFFFFF

        if ord("0") <= one_byte <= ord("9"):
            nibble = one_byte - ord("0")
        else:
            nibble = ord(chr(one_byte).lower()) - ord("a") + 10

        if nibble < 0 or nibble > 15:
            raise ValueError(f"Invalid JNOS challenge nibble in {s!r}")

        calc |= nibble

    return calc & 0xFFFFFFFF