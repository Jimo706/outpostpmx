# services/form_transport.py

from __future__ import annotations

import re
from dataclasses import dataclass

from services.form_definition_loader import (
    FormDefinition,
    FormRegistry,
)


class FormTransportError(ValueError):
    """Raised when OPXFORM transport data cannot be rendered."""


# ==============================================================
# OUTBOUND: completed form -> OPXFORM message body
# ==============================================================

def render_form_body(
    form: FormDefinition,
    values: dict[str, object],
) -> str:
    """
    Convert completed form values into an OPXFORM packet-message body.
    """
    transport = form.transport or {}

    show_labels = bool(transport.get("show_labels", False))
    omit_empty = bool(transport.get("omit_empty", False))

    lines: list[str] = [
        f"!OPXFORM:{form.form_id}:{form.form_version}!"
    ]

    fields = form.input.get("fields", []) or []

    for field in fields:
        field_id = str(field.get("id", "")).strip()
        wire_id = str(field.get("wire_id", "")).strip()

        if not field_id or not wire_id:
            continue

        raw_value = values.get(field_id)
        text = _wire_value(field, raw_value)

        if omit_empty and not text:
            continue

        prefix = _wire_prefix(
            field,
            wire_id=wire_id,
            show_labels=show_labels,
        )

        value_lines = text.splitlines()

        if not value_lines:
            lines.append(prefix)
            continue

        lines.append(f"{prefix} {value_lines[0]}".rstrip())

        for continuation in value_lines[1:]:
            lines.append(continuation)

    lines.append("!/OPXFORM!")

    return "\n".join(lines)


def _wire_prefix(
    field: dict,
    *,
    wire_id: str,
    show_labels: bool,
) -> str:

    if not show_labels:
        return f"{wire_id}:"

    wire_label = str(
        field.get("wire_label")
        or field.get("label")
        or field.get("id")
        or ""
    ).strip()

    if wire_label:
        return f"{wire_id}-{wire_label.upper()}:"

    return f"{wire_id}:"


def _wire_value(field: dict, value: object) -> str:

    field_type = str(field.get("type", "text")).strip().lower()

    if field_type == "checkbox":
        return "Y" if bool(value) else ""

    if value is None:
        return ""

    return str(value).strip()


# ==============================================================
# INBOUND: OPXFORM message body -> structured field values
# ==============================================================

@dataclass(frozen=True)
class ParsedFormMessage:
    form_id: str
    form_version: int
    form: FormDefinition | None
    values: dict[str, object]


_START_RE = re.compile(
    r"^!OPXFORM:(?P<form_id>[^:!]+):(?P<form_version>\d+)!$",
    re.IGNORECASE,
)


def parse_form_body(
    body: str,
    registry: FormRegistry,
) -> ParsedFormMessage | None:
    """
    Parse an OPXFORM message body.

    Returns None when the body is not an OPXFORM message.
    """
    lines = (body or "").splitlines()

    if not lines:
        return None

    first = lines[0].strip()
    match = _START_RE.match(first)

    if not match:
        return None

    form_id = match.group("form_id").strip()

    try:
        form_version = int(match.group("form_version"))
    except ValueError as exc:
        raise FormTransportError(
            "Invalid OPXFORM form version."
        ) from exc

    form = registry.get(form_id)

    # Recognized OPXFORM, but definition isn't installed.
    if form is None:
        return ParsedFormMessage(
            form_id=form_id,
            form_version=form_version,
            form=None,
            values={},
        )

    # Installed definition does not match transmitted version.
    if form.form_version != form_version:
        return ParsedFormMessage(
            form_id=form_id,
            form_version=form_version,
            form=None,
            values={},
        )

    wire_to_field: dict[str, dict] = {}

    for field in form.input.get("fields", []) or []:
        wire_id = str(field.get("wire_id", "")).strip()

        if wire_id:
            wire_to_field[wire_id.upper()] = field

    values: dict[str, object] = {}

    current_field: dict | None = None
    current_lines: list[str] = []

    def flush_current() -> None:
        nonlocal current_field, current_lines

        if current_field is None:
            return

        field_id = str(current_field.get("id", "")).strip()
        field_type = str(
            current_field.get("type", "text")
        ).strip().lower()

        text = "\n".join(current_lines).strip()

        if field_type == "checkbox":
            values[field_id] = text.upper() in (
                "Y",
                "YES",
                "TRUE",
                "1",
                "X",
            )
        else:
            values[field_id] = text

        current_field = None
        current_lines = []

    for raw_line in lines[1:]:
        line = raw_line.rstrip()

        if line.strip().upper() == "!/OPXFORM!":
            flush_current()
            break

        field_match = re.match(
            r"^(?P<wire>[A-Za-z0-9]+)"
            r"(?:-[^:]*)?"
            r":\s?(?P<value>.*)$",
            line,
        )

        if field_match:
            wire_id = field_match.group("wire").strip().upper()
            field = wire_to_field.get(wire_id)

            if field is not None:
                flush_current()

                current_field = field
                current_lines = [
                    field_match.group("value")
                ]
                continue

        # Continuation lines belong only to multiline fields.
        if current_field is not None:
            field_type = str(
                current_field.get("type", "text")
            ).strip().lower()

            if field_type == "multiline":
                current_lines.append(line)

    flush_current()

    return ParsedFormMessage(
        form_id=form_id,
        form_version=form_version,
        form=form,
        values=values,
    )
