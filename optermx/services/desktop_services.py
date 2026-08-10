"""
optermx > services > desktop_services.py
Cross-platform helpers for opening files and directories
with the operating system's default application.

On Linux, external programs must not inherit PyInstaller's
bundled-library search path.

The final flow is:
Tools → Open Data Folder
        ↓
open_data_folder()
        ↓
open_directory(self.paths.data_dir)
        ↓
Windows: os.startfile()
macOS:   open
Linux:   xdg-open with cleaned LD_LIBRARY_PATH
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


class DesktopOpenError(RuntimeError):
    """Raised when a file or directory cannot be opened."""


def _system_environment() -> dict[str, str]:
    """
    Return an environment suitable for launching an external system program.

    PyInstaller changes LD_LIBRARY_PATH on Linux so the frozen application
    loads its bundled libraries. External programs such as xdg-open and
    kde-open must instead use the operating system's libraries.
    """
    env = os.environ.copy()

    if sys.platform.startswith("linux"):
        original_path = env.get("LD_LIBRARY_PATH_ORIG")

        if original_path:
            env["LD_LIBRARY_PATH"] = original_path
        else:
            env.pop("LD_LIBRARY_PATH", None)

    # print("DEBUG51>>> LD_LIBRARY_PATH      =", env.get("LD_LIBRARY_PATH"))
    # print("DEBUG52>>> LD_LIBRARY_PATH_ORIG =", env.get("LD_LIBRARY_PATH_ORIG"))

    return env


def open_directory(directory: str | Path) -> None:
    """
    Open a directory in the operating system's default file manager.

    Raises:
        DesktopOpenError: If the directory does not exist or cannot be opened.
    """
    path = Path(directory).expanduser().resolve()

    if not path.exists():
        raise DesktopOpenError(f"Directory does not exist:\n{path}")

    if not path.is_dir():
        raise DesktopOpenError(f"Path is not a directory:\n{path}")

    try:
        if sys.platform == "win32":
            os.startfile(str(path))  # type: ignore[attr-defined]

        elif sys.platform == "darwin":
            subprocess.Popen(
                ["open", str(path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

        elif sys.platform.startswith("linux"):
            # subprocess.Popen(..., env=...) lets us give only the child process the corrected environment. 
            # start_new_session=True separates the external file manager from OpTermX’s process session.
            subprocess.Popen(
                ["xdg-open", str(path)],
                env=_system_environment(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

        else:
            raise DesktopOpenError(
                f"Opening directories is not supported on platform: "
                f"{sys.platform}"
            )


    except FileNotFoundError as exc:
        raise DesktopOpenError(
            f"The operating-system folder-opening utility was not found.\n\n"
            f"Directory:\n{path}"
        ) from exc

    except OSError as exc:
        raise DesktopOpenError(
            f"Unable to open the directory:\n{path}\n\n"
            f"{exc}"
        ) from exc