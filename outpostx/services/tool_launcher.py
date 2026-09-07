# services/tool_launcher.py
# #171 - external tool launching

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

from services.tool_config import ToolDefinition


class ToolLaunchError(RuntimeError):
    """Raised when an external tool cannot be launched."""


def launch_tool(
    tool: ToolDefinition,
    *,
    program_dir: str | Path,
) -> None:
    """
    Launch one configured external tool.

    Supported substitutions:
        $PROGRAM_DIR

    The launched tool is detached from OutpostX and receives a cleaned
    environment on Linux so PyInstaller's bundled libraries are not
    inherited by the external application.
    """
    program_dir = Path(program_dir).resolve()

    command_text = _expand_value(
        tool.command,
        program_dir=program_dir,
    )

    arguments = [
        _expand_value(arg, program_dir=program_dir)
        for arg in tool.arguments
    ]

    executable, prefix_args = _resolve_executable(
        command_text,
        program_dir=program_dir,
    )

    argv = [
        executable,
        *prefix_args,
        *arguments,
    ]

    try:
        subprocess.Popen(
            argv,
            cwd=str(program_dir),
            env=_system_environment(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    except FileNotFoundError as exc:
        raise ToolLaunchError(
            f"Program not found:\n{command_text}"
        ) from exc

    except OSError as exc:
        raise ToolLaunchError(
            f"Unable to launch '{tool.name}'.\n\n"
            f"Program:\n{command_text}\n\n"
            f"{exc}"
        ) from exc


def _expand_value(
    value: str,
    *,
    program_dir: Path,
) -> str:
    """
    Expand supported path variables using native platform separators.
    """
    value = str(value)

    prefix_forward = "$PROGRAM_DIR/"
    prefix_backward = "$PROGRAM_DIR\\"

    if value.startswith(prefix_forward):
        relative = value[len(prefix_forward):]
        return str(program_dir / relative)

    if value.startswith(prefix_backward):
        relative = value[len(prefix_backward):]
        return str(program_dir / relative)

    if value == "$PROGRAM_DIR":
        return str(program_dir)

    return value
    

def _resolve_executable(
    command: str,
    *,
    program_dir: Path,
) -> tuple[str, list[str]]:
    """
    Resolve common OutpostPMX development and packaged layouts.

    For a configured command such as:

        $PROGRAM_DIR/optermx

    try:
        Windows: optermx.exe
        Linux/macOS: optermx

    During source development, also permit:
        optermx.py

    A bare command such as 'notepad.exe' or 'gedit' is left alone so
    normal operating-system PATH lookup can occur.
    """
    path = Path(command)

    # A command containing a path is treated as a file location.
    looks_like_path = (
        path.is_absolute()
        or "/" in command
        or "\\" in command
    )

    if not looks_like_path:
        return command, []

    candidates: list[Path] = []

    if sys.platform == "win32":
        if path.suffix.lower() == ".exe":
            candidates.append(path)
        else:
            candidates.append(
                path.with_suffix(".exe")
            )

    else:
        candidates.append(path)

    # Development/source-tree fallback.
    if not path.suffix:
        candidates.append(
            path.with_suffix(".py")
        )

    for candidate in candidates:
        if not candidate.exists():
            continue

        if candidate.suffix.lower() == ".py":
            return sys.executable, [str(candidate)]

        return str(candidate), []

    # Return the normal platform candidate so the resulting error
    # reports the path the operator expected.
    if sys.platform == "win32" and not path.suffix:
        return str(path.with_suffix(".exe")), []

    return str(path), []


def _system_environment() -> dict[str, str]:
    """
    Return an environment appropriate for launching an external program.

    PyInstaller modifies LD_LIBRARY_PATH on Linux. External applications
    must use the operating system's normal library search path.
    """
    env = os.environ.copy()

    if sys.platform.startswith("linux"):
        original_path = env.get("LD_LIBRARY_PATH_ORIG")

        if original_path:
            env["LD_LIBRARY_PATH"] = original_path
        else:
            env.pop("LD_LIBRARY_PATH", None)

    return env