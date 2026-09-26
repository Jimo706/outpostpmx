# services/form_substitutions.py
from __future__ import annotations

from datetime import datetime

from services.form_definition_loader import FormDefinition
from services.message_settings import allocate_next_mid


"""
OPXFORM runtime substitution variables.

Supported substitutions:

    $CURRENT_DATE
        Current local date.

    $CURRENT_TIME
        Current local time, 24-hour HH:mm.

    $MSG_ID
        Allocated OutpostX Message ID. A MID is consumed only when
        the selected form explicitly requests $MSG_ID.

    $CALL_SIGN
        User Call Sign from the active Station ID profile.

    $USER_NAME
        User Name from the active Station ID profile.

All OPXFORM runtime substitutions are defined and populated here.
The Forms Engine should not need to know where these values originate.
"""


CURRENT_DATE = "$CURRENT_DATE"
CURRENT_TIME = "$CURRENT_TIME"
MSG_ID = "$MSG_ID"
CALL_SIGN = "$CALL_SIGN"
USER_NAME = "$USER_NAME"


def build_form_substitutions(
    form: FormDefinition,
    *,
    config,
    system_config,
) -> dict[str, str]:
    """
    Build the runtime substitution dictionary for an OPXFORM.

    $MSG_ID is special because resolving it consumes a Message ID.
    Therefore, a MID is allocated only when the selected form
    explicitly references $MSG_ID as a field default.
    """

    now = datetime.now()    # guarantees $CURRENT_DATE and $CURRENT_TIME describe the same instant

    substitutions = {
        CURRENT_DATE: now.strftime("%Y-%m-%d"),
        CURRENT_TIME: now.strftime("%H:%M"),
        MSG_ID: "",
        CALL_SIGN: "",
        USER_NAME: "",
    }

    # ---------------------------------------------------------
    # Station substitutions
    # ---------------------------------------------------------
    try:
        station = system_config.get_active_station()
    except Exception:
        station = None

    if station is not None:
        substitutions[CALL_SIGN] = (
            getattr(station, "legal_call_sign", "") or ""
        ).strip()

        substitutions[USER_NAME] = (
            getattr(station, "user_name", "") or ""
        ).strip()

    # ---------------------------------------------------------
    # Determine whether this form explicitly requests $MSG_ID.
    # ---------------------------------------------------------
    fields = form.input.get("fields", []) or []

    needs_msg_id = any(
        field.get("default") == MSG_ID
        for field in fields
        if isinstance(field, dict)
    )

    if not needs_msg_id:
        return substitutions

    # ---------------------------------------------------------
    # The form explicitly requests $MSG_ID.
    #
    # Tactical MID prefix takes precedence over Station MID
    # prefix, matching normal OutpostX message behavior.
    # ---------------------------------------------------------
    try:
        tactical = system_config.get_active_tactical()
    except Exception:
        tactical = None

    tactical_prefix = (
        getattr(tactical, "msg_id_prefix", "") or ""
    ).strip().upper()

    station_prefix = (
        getattr(station, "msg_id_prefix", "") or ""
    ).strip().upper()

    prefix = tactical_prefix or station_prefix

    if prefix:
        substitutions[MSG_ID] = allocate_next_mid(
            config,
            prefix,
        )

    return substitutions