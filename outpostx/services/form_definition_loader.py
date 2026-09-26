# services/form_definition_loader.py    # #164

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


SUPPORTED_OPXFORM_VERSION = 1

# #190, 260912, added radio (radio button) and select (dropdown list)
SUPPORTED_FIELD_TYPES = {
    "text",
    "multiline",
    "date",
    "time",
    "checkbox",
    "radio",
    "select",
    "section",
}

class FormDefinitionError(ValueError):
    """Raised when an .opxform definition is invalid."""


@dataclass(frozen=True)
class FormDefinition:
    """
    One validated OutpostX form definition.

    The original JSON dictionary is retained in 'raw' so later
    components can consume input, transport, and pdf sections
    without the loader knowing how those sections are rendered.
    """

    source_path: Path
    opxform_version: int
    form_id: str
    form_version: int
    name: str
    raw: dict[str, Any]

    @property
    def input(self) -> dict[str, Any]:
        return self.raw.get("input", {}) or {}

    @property
    def transport(self) -> dict[str, Any]:
        return self.raw.get("transport", {}) or {}

    @property
    def pdf(self) -> dict[str, Any] | None:
        value = self.raw.get("pdf")
        return value if isinstance(value, dict) else None

    @property
    def supports_pdf(self) -> bool:
        return self.pdf is not None


class FormRegistry:
    """
    Load and hold all valid .opxform definitions from one directory.

    Rules:
    - Only *.opxform files are scanned.
    - OPXFORM schema version 1 is currently supported.
    - form_id must be unique.
    - One bad file does not prevent other forms from loading.
    - Forms are returned alphabetically by display name.
    """

    def __init__(self, forms_dir: str | Path) -> None:
        self.forms_dir = Path(forms_dir)
        self._forms: dict[str, FormDefinition] = {}
        self._errors: list[str] = []

    @property
    def errors(self) -> list[str]:
        return list(self._errors)

    def forms(self) -> list[FormDefinition]:
        return sorted(
            self._forms.values(),
            key=lambda form: form.name.casefold(),
        )

    def get(self, form_id: str) -> FormDefinition | None:
        return self._forms.get(form_id)

    def reload(self) -> list[FormDefinition]:
        """
        Rescan the forms directory.

        Invalid files are skipped and recorded in errors.
        """
        self._forms.clear()
        self._errors.clear()

        self.forms_dir.mkdir(parents=True, exist_ok=True)

        for path in sorted(self.forms_dir.glob("*.opxform")):
            try:
                form = self._load_file(path)

                if form.form_id in self._forms:
                    existing = self._forms[form.form_id]
                    raise FormDefinitionError(
                        f"Duplicate form_id '{form.form_id}'. "
                        f"Already defined by {existing.source_path.name}"
                    )

                self._forms[form.form_id] = form

            except Exception as exc:
                message = f"{path.name}: {exc}"
                self._errors.append(message)
                print(f"WARNING: OPXFORM load failed: {message}")

        return self.forms()

    def _load_file(self, path: Path) -> FormDefinition:
        try:
            with path.open("r", encoding="utf-8") as f:
                raw = json.load(f)
        except json.JSONDecodeError as exc:
            raise FormDefinitionError(
                f"Invalid JSON at line {exc.lineno}, column {exc.colno}: "
                f"{exc.msg}"
            ) from exc
        except OSError as exc:
            raise FormDefinitionError(
                f"Unable to read file: {exc}"
            ) from exc

        if not isinstance(raw, dict):
            raise FormDefinitionError(
                "Top-level OPXFORM definition must be a JSON object."
            )

        opxform_version = raw.get("opxform_version")
        if opxform_version != SUPPORTED_OPXFORM_VERSION:
            raise FormDefinitionError(
                f"Unsupported opxform_version '{opxform_version}'. "
                f"Supported version is {SUPPORTED_OPXFORM_VERSION}."
            )

        form_id = self._required_string(raw, "form_id")
        name = self._required_string(raw, "name")

        form_version = raw.get("form_version")
        if not isinstance(form_version, int) or form_version < 1:
            raise FormDefinitionError(
                "'form_version' must be an integer greater than or equal to 1."
            )

        input_def = raw.get("input")
        if not isinstance(input_def, dict):
            raise FormDefinitionError(
                "'input' must be a JSON object."
            )

        fields = input_def.get("fields")
        if not isinstance(fields, list):
            raise FormDefinitionError(
                "'input.fields' must be a JSON array."
            )

        self._validate_fields(fields)
        self._validate_subject(input_def, fields)       # #164, 260827

        transport = raw.get("transport")
        if transport is not None and not isinstance(transport, dict):
            raise FormDefinitionError(
                "'transport' must be a JSON object."
            )

        pdf = raw.get("pdf")
        if pdf is not None and not isinstance(pdf, dict):
            raise FormDefinitionError(
                "'pdf' must be a JSON object when present."
            )

        return FormDefinition(
            source_path=path,
            opxform_version=opxform_version,
            form_id=form_id,
            form_version=form_version,
            name=name,
            raw=raw,
        )

    @staticmethod
    def _required_string(raw: dict[str, Any], key: str) -> str:
        value = raw.get(key)

        if not isinstance(value, str) or not value.strip():
            raise FormDefinitionError(
                f"'{key}' must be a non-empty string."
            )

        return value.strip()

    #  #164. 260827, replaced to add "section"
    @staticmethod
    def _validate_fields(fields: list[Any]) -> None:
        seen_ids: set[str] = set()
        seen_wire_ids: set[str] = set()

        for index, field in enumerate(fields, start=1):
            if not isinstance(field, dict):
                raise FormDefinitionError(
                    f"Field #{index} must be a JSON object."
                )

            # ----------------------------------------------------------
            # Field type
            # ----------------------------------------------------------
            field_type = field.get("type")

            if not isinstance(field_type, str) or not field_type.strip():
                raise FormDefinitionError(
                    f"Field #{index} is missing a valid 'type'."
                )

            field_type = field_type.strip().lower()

            if field_type not in SUPPORTED_FIELD_TYPES:
                raise FormDefinitionError(
                    f"Field #{index} has unsupported type "
                    f"'{field_type}'."
                )

            # ----------------------------------------------------------
            # Presentation-only section
            #
            # A section is not a data field.  It requires only:
            #
            #     type = "section"
            #     label = "<section heading>"
            #
            # It does not require id, wire_id, required, etc.
            # ----------------------------------------------------------
            if field_type == "section":
                label = field.get("label")

                if not isinstance(label, str) or not label.strip():
                    raise FormDefinitionError(
                        f"Section #{index} is missing a valid 'label'."
                    )

                continue

            # ----------------------------------------------------------
            # Normal data field
            # ----------------------------------------------------------
            field_id = field.get("id")

            if not isinstance(field_id, str) or not field_id.strip():
                raise FormDefinitionError(
                    f"Field #{index} is missing a valid 'id'."
                )

            field_id = field_id.strip()

            if field_id in seen_ids:
                raise FormDefinitionError(
                    f"Duplicate field id '{field_id}'."
                )

            seen_ids.add(field_id)

            # ----------------------------------------------------------
            # #190, 260912
            # Choice options
            #
            # radio and select fields must define one or more choices.  Each option is:
            #     {
            #         "value": "<stored/wire value>",
            #         "label": "<displayed value>"
            #     }
            # Option values must be unique within the field.
            # ----------------------------------------------------------
            if field_type in ("radio", "select"):
                options = field.get("options")

                if not isinstance(options, list) or not options:
                    raise FormDefinitionError(
                        f"Field '{field_id}' of type '{field_type}' "
                        "must define a non-empty 'options' array."
                    )

                seen_option_values: set[str] = set()

                for option_index, option in enumerate(options, start=1):
                    if not isinstance(option, dict):
                        raise FormDefinitionError(
                            f"Field '{field_id}' option #{option_index} "
                            "must be a JSON object."
                        )

                    value = option.get("value")
                    label = option.get("label")

                    if not isinstance(value, str) or not value.strip():
                        raise FormDefinitionError(
                            f"Field '{field_id}' option #{option_index} "
                            "must define a non-empty 'value'."
                        )

                    if not isinstance(label, str) or not label.strip():
                        raise FormDefinitionError(
                            f"Field '{field_id}' option #{option_index} "
                            "must define a non-empty 'label'."
                        )

                    value = value.strip()

                    if value in seen_option_values:
                        raise FormDefinitionError(
                            f"Field '{field_id}' has duplicate option "
                            f"value '{value}'."
                        )

                    seen_option_values.add(value)

            # ----------------------------------------------------------
            # Wire ID
            # ----------------------------------------------------------
            wire_id = field.get("wire_id")

            if wire_id is not None:
                wire_id = str(wire_id).strip()

                if not wire_id:
                    raise FormDefinitionError(
                        f"Field '{field_id}' has an empty wire_id."
                    )

                if wire_id in seen_wire_ids:
                    raise FormDefinitionError(
                        f"Duplicate wire_id '{wire_id}'."
                    )

                seen_wire_ids.add(wire_id)


    @staticmethod
    def _validate_subject(
        input_def: dict[str, Any],
        fields: list[Any],
    ) -> None:
        """
        Validate the optional Outpost packet Subject rule.

        Supported forms:

            "subject": {
                "source": "field",
                "value": "field_id"
            }

        or:

            "subject": {
                "source": "fixed",
                "value": "Fixed packet subject"
            }

        If omitted, older OPXFORM definitions remain valid.
        """

        subject_def = input_def.get("subject")

        # Backward compatibility for existing forms.
        if subject_def is None:
            return

        if not isinstance(subject_def, dict):
            raise FormDefinitionError(
                "'input.subject' must be a JSON object."
            )

        source = subject_def.get("source")
        value = subject_def.get("value")

        if not isinstance(source, str) or not source.strip():
            raise FormDefinitionError(
                "'input.subject.source' must be a non-empty string."
            )

        source = source.strip().lower()

        if source not in ("field", "fixed"):
            raise FormDefinitionError(
                "'input.subject.source' must be either "
                "'field' or 'fixed'."
            )

        if not isinstance(value, str) or not value.strip():
            raise FormDefinitionError(
                "'input.subject.value' must be a non-empty string."
            )

        value = value.strip()

        # For a field-based subject, make sure the named field really exists.
        if source == "field":
            field_ids = {
                str(field.get("id", "")).strip()
                for field in fields
                if isinstance(field, dict)
                and str(field.get("type", "")).strip().lower() != "section"
                and str(field.get("id", "")).strip()
            }

            if value not in field_ids:
                raise FormDefinitionError(
                    f"'input.subject.value' references unknown "
                    f"field id '{value}'."
                )

            