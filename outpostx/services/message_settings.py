from __future__ import annotations

from dataclasses import dataclass

from app_config import AppConfig


@dataclass
class MessageSettings:
    """
    Global Message Settings.

    These are global preferences stored in AppConfig/QSettings, matching the
    same persistence pattern used by Send/Receive settings.

    Phase 1 scope:
      - Store/load settings
      - Support the Message Settings preferences form
      - Apply new-message compose defaults later

    Deferred:
      - send_nts_as_private send-command override
      - inbound MID assignment
      - automatic delivery receipt generation
      - wire-format body tags such as !RDR!, !URG!, !B64!
    """

    # New Messages
    send_nts_as_private: bool = False
    use_default_destination: bool = False
    default_destination: str = ""

    # Message Numbering
    add_mid_to_outbound: bool = False
    add_mid_to_inbound: bool = False
    next_msg_number: int = 100
    mid_separator: str = ""
    mid_suffix: str = ""

    # Message Receipts
    request_dr: bool = False
    send_dr: bool = False


def load_message_settings(config: AppConfig) -> MessageSettings:
    """
    Load Message Settings from AppConfig/QSettings.
    """
    get = config.get

    return MessageSettings(
        send_nts_as_private=_as_bool(
            get("MessageSettings/sendNtsAsPrivate", False),
            default=False,
        ),
        use_default_destination=_as_bool(
            get("MessageSettings/useDefaultDestination", False),
            default=False,
        ),
        default_destination=_normalize_destination_for_storage(
            get("MessageSettings/defaultDestination", "") or ""
        ),

        add_mid_to_outbound=_as_bool(
            get("MessageSettings/addMidToOutbound", False),
            default=False,
        ),
        add_mid_to_inbound=_as_bool(
            get("MessageSettings/addMidToInbound", False),
            default=False,
        ),
        next_msg_number=_as_int(
            get("MessageSettings/nextMsgNumber", 100),
            default=100,
            minimum=0,
        ),
        mid_separator=str(get("MessageSettings/midSeparator", "") or ""),
        mid_suffix=str(get("MessageSettings/midSuffix", "") or ""),

        request_dr=_as_bool(
            get("MessageSettings/requestDr", False),
            default=False,
        ),
        send_dr=_as_bool(
            get("MessageSettings/sendDr", False),
            default=False,
        ),
    )


def save_message_settings(config: AppConfig, settings: MessageSettings) -> None:
    """
    Persist Message Settings to AppConfig/QSettings.
    """
    setv = config.set

    setv("MessageSettings/sendNtsAsPrivate", bool(settings.send_nts_as_private))
    setv("MessageSettings/useDefaultDestination", bool(settings.use_default_destination))
    setv(
        "MessageSettings/defaultDestination",
        _normalize_destination_for_storage(settings.default_destination),
    )

    setv("MessageSettings/addMidToOutbound", bool(settings.add_mid_to_outbound))
    setv("MessageSettings/addMidToInbound", bool(settings.add_mid_to_inbound))
    setv("MessageSettings/nextMsgNumber", int(max(0, settings.next_msg_number)))
    setv("MessageSettings/midSeparator", settings.mid_separator or "")
    setv("MessageSettings/midSuffix", settings.mid_suffix or "")

    setv("MessageSettings/requestDr", bool(settings.request_dr))
    setv("MessageSettings/sendDr", bool(settings.send_dr))


def build_next_mid(prefix: str, settings: MessageSettings) -> str:
    """
    Build a formatted MID from:
        prefix + separator + next_msg_number + suffix

    Example:
        prefix='CMV', next=304, separator='-', suffix='P'
        -> 'CMV-304P'

    This function does not increment next_msg_number.
    """
    pfx = (prefix or "").strip()
    sep = settings.mid_separator or ""
    num = str(int(max(0, settings.next_msg_number)))
    sfx = settings.mid_suffix or ""
    return f"{pfx}{sep}{num}{sfx}"


def increment_next_msg_number(config: AppConfig, settings: MessageSettings) -> MessageSettings:
    """
    Increment next_msg_number and persist the updated settings.

    Intended use:
        call immediately after a compose window retrieves a MID.
    """
    settings.next_msg_number = int(max(0, settings.next_msg_number)) + 1
    save_message_settings(config, settings)
    return settings


def allocate_next_mid(config: AppConfig, prefix: str) -> str:
    """ P132 260512
    Allocate the next formatted MID and immediately persist the incremented
    next_msg_number.

    This is the single supported API for consuming a MID.
    """
    settings = load_message_settings(config)
    mid = build_next_mid(prefix, settings)
    increment_next_msg_number(config, settings)
    return mid


def _normalize_destination_for_storage(value: str) -> str:
    """
    Normalize destination separators for storage.

    Accepts either semicolon or comma input, stores as comma-separated.
    Uses comma+space for readability. The actual send path can remove spaces
    for BBS types such as BPQ that require comma-with-no-spaces.
    """
    raw = (value or "").strip()
    if not raw:
        return ""

    parts = []
    for part in raw.replace(";", ",").split(","):
        p = part.strip()
        if p:
            parts.append(p)

    return ", ".join(parts)


def _as_int(value, *, default: int = 0, minimum: int | None = None) -> int:
    """
    Convert QSettings values into an int with fallback handling.
    """
    try:
        out = int(value)
    except (TypeError, ValueError):
        out = default

    if minimum is not None:
        out = max(minimum, out)

    return out


def _as_bool(value, default: bool = False) -> bool:
    """
    Convert QSettings values into a proper boolean.

    QSettings may return strings, and bool("false") is True in Python,
    so this parser mirrors the SendReceiveSettings helper.
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