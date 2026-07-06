# services/send_receive_settings.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List

from app_config import AppConfig


class AutomationMode(str, Enum):
    """Automation modes for Send/Receive Sessions."""
    MANUAL = "manual"
    EVERY_N_MINUTES = "every_n_minutes"
    SLOT_TIMES = "slot_times"


@dataclass
class SendReceiveSettings:
    """
    Global Send/Receive Settings.

    These are *global* (per OutpostX instance) and apply regardless of which
    Station / BBS / Interface is active.

    Fields:
        mode:
            Automation mode:
                - MANUAL
                - EVERY_N_MINUTES
                - SLOT_TIMES

        interval_minutes:
            When mode == EVERY_N_MINUTES, run every N minutes.

        slot_minutes:
            When mode == SLOT_TIMES, run at these minutes past the hour (0–59).

        play_sound_on_receive:
            If True, play a sound when new messages are received.

        sound_file_path:
            Full path to the sound file to play (typically .mp3 or 
            ).

        print_received:
            If True, automatically print received messages.

        print_received_copies:
            Number of copies for received-message printing (1–9).

        print_sent:
            If True, automatically print sent messages.

        print_sent_copies:
            Number of copies for sent-message printing (1–9).

        print_receipts:
            If True, print receipt/acknowledgment messages.

        print_plain_headers:
            If True, print headers for plain-text messages (non-form messages).
    """
    mode: AutomationMode
    interval_minutes: int
    slot_minutes: List[int]

    play_sound_on_receive: bool
    sound_file_path: str

    print_received: bool
    print_received_copies: int
    print_sent: bool
    print_sent_copies: int
    print_receipts: bool
    print_plain_headers: bool


# ----------------------------------------------------------------------
# Helpers for slot times
# ----------------------------------------------------------------------


def _parse_slot_minutes(raw: str) -> List[int]:
    """
    Parse a comma/semicolon-separated list of integers in [0, 59].
    Invalid values are ignored; duplicates are removed; result is sorted.
    """
    if not raw:
        return []

    parts = raw.replace(";", ",").split(",")
    seen = set()
    slots: List[int] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        try:
            val = int(part)
        except ValueError:
            continue
        if 0 <= val <= 59 and val not in seen:
            seen.add(val)
            slots.append(val)
    return sorted(slots)


def _format_slot_minutes(slots: List[int]) -> str:
    """
    Format slot minutes as a comma-separated string for storage.
    """
    if not slots:
        return ""
    uniq_sorted = sorted({int(s) for s in slots if 0 <= int(s) <= 59})
    return ",".join(str(s) for s in uniq_sorted)


# ----------------------------------------------------------------------
# Persistence helpers (backed by AppConfig / QSettings)
# ----------------------------------------------------------------------


def load_send_receive_settings(config: AppConfig) -> SendReceiveSettings:
    """
    Load Send/Receive settings from AppConfig (QSettings).

    Defaults:
      - MANUAL mode
      - interval_minutes = 15
      - slot_minutes = []
      - play_sound_on_receive = False
      - sound_file_path = ""
      - print_received = False, copies = 1
      - print_sent = False, copies = 1
      - print_receipts = False
      - print_plain_headers = False
    """
    get = config.get

    raw_mode = (get("SendReceive/mode", AutomationMode.MANUAL.value) or "").strip()
    try:
        mode = AutomationMode(raw_mode)
    except ValueError:
        mode = AutomationMode.MANUAL

    try:
        interval = int(get("SendReceive/intervalMinutes", 15) or 15)
    except (TypeError, ValueError):
        interval = 15
    if interval <= 0:
        interval = 15

    raw_slots = (get("SendReceive/slotMinutes", "") or "").strip()
    slots = _parse_slot_minutes(raw_slots)

    play_sound = _as_bool(get("SendReceive/playSoundOnReceive", False),default=False,)
    sound_path = get("SendReceive/soundFilePath", "") or ""

    print_received = _as_bool(get("SendReceive/printReceived", False),default=False,)
    try:
        print_received_copies = int(get("SendReceive/printReceivedCopies", 1) or 1)
    except (TypeError, ValueError):
        print_received_copies = 1
    print_received_copies = min(max(print_received_copies, 1), 9)

    print_sent = _as_bool(get("SendReceive/printSent", False),default=False,)
    try:
        print_sent_copies = int(get("SendReceive/printSentCopies", 1) or 1)
    except (TypeError, ValueError):
        print_sent_copies = 1
    print_sent_copies = min(max(print_sent_copies, 1), 9)

    print_receipts = _as_bool(get("SendReceive/printReceipts", False),default=False,)
    print_plain_headers = _as_bool(get("SendReceive/printPlainHeaders", False),default=False,)

    return SendReceiveSettings(
        mode=mode,
        interval_minutes=interval,
        slot_minutes=slots,
        play_sound_on_receive=play_sound,
        sound_file_path=sound_path,
        print_received=print_received,
        print_received_copies=print_received_copies,
        print_sent=print_sent,
        print_sent_copies=print_sent_copies,
        print_receipts=print_receipts,
        print_plain_headers=print_plain_headers,
    )


def save_send_receive_settings(config: AppConfig, settings: SendReceiveSettings) -> None:
    """
    Persist Send/Receive settings to AppConfig (QSettings).
    """
    setv = config.set

    setv("SendReceive/mode", settings.mode.value)
    setv("SendReceive/intervalMinutes", int(settings.interval_minutes))
    setv("SendReceive/slotMinutes", _format_slot_minutes(settings.slot_minutes))

    setv("SendReceive/playSoundOnReceive", bool(settings.play_sound_on_receive))
    setv("SendReceive/soundFilePath", settings.sound_file_path or "")

    setv("SendReceive/printReceived", bool(settings.print_received))
    setv("SendReceive/printReceivedCopies", int(settings.print_received_copies))

    setv("SendReceive/printSent", bool(settings.print_sent))
    setv("SendReceive/printSentCopies", int(settings.print_sent_copies))

    setv("SendReceive/printReceipts", bool(settings.print_receipts))
    setv("SendReceive/printPlainHeaders", bool(settings.print_plain_headers))


# -----------------------
# bool helper / parser
# -----------------------
def _as_bool(value, default=False) -> bool:
    """
    Convert a QSettings value to a proper boolean.

    QSettings may return values as strings (e.g., "true", "false"),
    and Python's bool() is unsafe for these cases:

        bool("false") == True   # incorrect

    This helper normalizes common representations:

        True  → True
        False → False
        "true", "1", "yes", "on"  → True
        "false", "0", "no", "off" → False

    Any unrecognized or None value returns the provided default.

    Args:
        value: Value returned from QSettings (bool, str, or None)
        default: Fallback value if input cannot be interpreted

    Returns:
        bool: Correctly interpreted boolean value
    """
    if value is None:
        return default
    if isinstance(value, bool):
        return value

    s = str(value).strip().lower()
    if s in ("1", "true", "yes", "y", "on"):
        return True
    if s in ("0", "false", "no", "n", "off"):
        return False

    return default

