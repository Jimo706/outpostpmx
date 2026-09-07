# services/tool_config.py
# #171 - configurable external Tools menu

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


class ToolConfigError(ValueError):
    """Raised when a tools configuration file is invalid."""


@dataclass(frozen=True)
class ToolDefinition:
    id: str
    name: str
    command: str
    arguments: tuple[str, ...]
    enabled: bool = True
    source: str = "system"       # "system" or "user"


def load_tools(data_dir: str | Path) -> list[ToolDefinition]:
    """
    Load OutpostX-supplied and optional user tool definitions.

    Files:
        <DataDir>/tools.json
        <DataDir>/user_tools.json

    Rules:
    - tools.json contains OutpostX-supplied definitions.
    - user_tools.json is optional and is never created/modified here.
    - A user entry with a new id adds a tool.
    - A user entry with an existing id overrides supplied values.
    - A user entry may set enabled=false to suppress a supplied tool.
    """
    data_dir = Path(data_dir)

    system_file = data_dir / "tools.json"
    user_file = data_dir / "user_tools.json"

    base_entries = _read_tools_file(
        system_file,
        required=False,
    )

    # Keep raw dictionaries during merge so user entries can be partial.
    merged: dict[str, dict] = {}
    order: list[str] = []
    source_by_id: dict[str, str] = {}

    for item in base_entries:
        tool_id = _required_id(item, system_file)

        if tool_id not in merged:
            order.append(tool_id)

        merged[tool_id] = dict(item)
        source_by_id[tool_id] = "system"

    if user_file.exists():
        user_entries = _read_tools_file(
            user_file,
            required=False,
        )

        for item in user_entries:
            tool_id = _required_id(item, user_file)

            if tool_id in merged:
                # Partial user override of supplied definition.
                updated = dict(merged[tool_id])
                updated.update(item)
                merged[tool_id] = updated

                # Keep it classified with the supplied tools so an
                # override of OpTermX doesn't move below the separator.
            else:
                merged[tool_id] = dict(item)
                order.append(tool_id)
                source_by_id[tool_id] = "user"

    result: list[ToolDefinition] = []

    for tool_id in order:
        raw = merged[tool_id]

        enabled = bool(raw.get("enabled", True))

        # Disabled entries need no further fields.
        if not enabled:
            continue

        name = str(raw.get("name", "") or "").strip()
        command = str(raw.get("command", "") or "").strip()

        if not name:
            raise ToolConfigError(
                f"Tool '{tool_id}' is missing a name."
            )

        if not command:
            raise ToolConfigError(
                f"Tool '{tool_id}' is missing a command."
            )

        arguments_raw = raw.get("arguments", [])

        if arguments_raw is None:
            arguments_raw = []

        if not isinstance(arguments_raw, list):
            raise ToolConfigError(
                f"Tool '{tool_id}' arguments must be a JSON array."
            )

        arguments = tuple(
            str(value)
            for value in arguments_raw
        )

        result.append(
            ToolDefinition(
                id=tool_id,
                name=name,
                command=command,
                arguments=arguments,
                enabled=True,
                source=source_by_id.get(tool_id, "system"),
            )
        )

    return result


def _read_tools_file(
    path: Path,
    *,
    required: bool,
) -> list[dict]:
    if not path.exists():
        if required:
            raise ToolConfigError(
                f"Tools configuration file does not exist:\n{path}"
            )
        return []

    try:
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)

    except json.JSONDecodeError as exc:
        raise ToolConfigError(
            f"{path.name}: invalid JSON at line "
            f"{exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc

    except OSError as exc:
        raise ToolConfigError(
            f"Unable to read {path.name}: {exc}"
        ) from exc

    if not isinstance(raw, dict):
        raise ToolConfigError(
            f"{path.name}: top-level value must be a JSON object."
        )

    tools = raw.get("tools", [])

    if not isinstance(tools, list):
        raise ToolConfigError(
            f"{path.name}: 'tools' must be a JSON array."
        )

    for index, item in enumerate(tools, start=1):
        if not isinstance(item, dict):
            raise ToolConfigError(
                f"{path.name}: tool #{index} must be a JSON object."
            )

    return tools


def _required_id(item: dict, source_file: Path) -> str:
    tool_id = str(item.get("id", "") or "").strip()

    if not tool_id:
        raise ToolConfigError(
            f"{source_file.name}: every tool requires an id."
        )

    return tool_id