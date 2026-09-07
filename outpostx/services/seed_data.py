# services/seed_data.py
"""
Seed writable runtime data from packaged application defaults.

Purpose
-------
AppPaths answers: "Where are the files?"
This module answers: "Which default files should be copied there?"

Policy
------
- Safe to call on every application startup.
- Creates required runtime directories if missing.
- Copies default files only when the destination file does not already exist.
- Never overwrites user-created or user-edited files.
- Logs/docs are directories only; they are not seeded with files by default.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from .app_paths import AppPaths


def seed_runtime_data(paths: AppPaths) -> None:
    """
    Seed all writable runtime data directories.

    Call once during application startup after AppPaths is created.
    """
    ensure_runtime_dirs(paths)

    seed_bbs_specs(paths)
    seed_sounds(paths)
    seed_forms(paths)                                       # #164
    seed_tools(paths)                                       # #171

def ensure_runtime_dirs(paths: AppPaths) -> None:
    """
    Ensure all standard runtime directories exist.
    """
    paths.data_dir.mkdir(parents=True, exist_ok=True)
    paths.logs_dir.mkdir(parents=True, exist_ok=True)
    paths.docs_dir.mkdir(parents=True, exist_ok=True)
    paths.bspecs_dir.mkdir(parents=True, exist_ok=True)
    paths.sounds_dir.mkdir(parents=True, exist_ok=True)
    paths.forms_dir.mkdir(parents=True, exist_ok=True)      # #164


def seed_bbs_specs(paths: AppPaths) -> None:
    """
    Copy packaged BBS spec JSON files into the runtime bbs_specs directory.

    Source:
        <program resources>/data/bbs_specs/*.json

    Destination:
        <DataDir>/bbs_specs/*.json
    """
    copy_files(
        source_dir = Path(paths.resource_path("data/bbs_specs")),
        target_dir=paths.bspecs_dir,
        patterns=("*.json",),
    )


def seed_sounds(paths: AppPaths) -> None:
    """
    Copy packaged sound files into the runtime sounds directory.

    Source:
        <program resources>/sounds/

    Destination:
        <DataDir>/sounds/
    """
    copy_files(
        source_dir = Path(paths.resource_path("data/sounds")), 
        target_dir=paths.sounds_dir,
        patterns=("*.wav", "*.mp3", "*.ogg"),
    )

def seed_forms(paths: AppPaths) -> None:
    """
    #164, 260825
    Copy packaged OutpostX form definitions and PDF templates into
    the writable runtime forms directory.

    Source:
        <program resources>/data/forms/

    Destination:
        <DataDir>/forms/

    Policy:
        Packaged form files are OutpostPMX-managed official assets.
        They are refreshed from the packaged copy on startup.

        User-created forms use different filenames/namespaces and are
        therefore left untouched.
    """
    copy_files(
        source_dir=Path(paths.resource_path("data/forms")),
        target_dir=paths.forms_dir,
        patterns=("*.opxform", "*.pdf"),
        overwrite=True,
    )

def seed_tools(paths: AppPaths) -> None:
    """
    Copy the packaged default tools.json into the writable Data Directory.

    Source:
        <program resources>/data/tools.json

    Destination:
        <DataDir>/tools.json

    Existing tools.json is never overwritten.
    user_tools.json is never created or modified by OutpostX.
    """
    source = Path(
        paths.resource_path("data/tools.json")
    )

    target = paths.data_dir / "tools.json"

    if not source.exists() or not source.is_file():
        return

    if target.exists():
        return

    shutil.copy2(source, target)


def copy_files(
    *,
    source_dir: Path,
    target_dir: Path,
    patterns: tuple[str, ...],
    overwrite: bool = False,
) -> None:
    """
    # 164. 260825
    Copy matching files from source_dir to target_dir.

    Args:
        source_dir:
            Packaged resource directory.

        target_dir:
            Writable runtime directory.

        patterns:
            Filename patterns to copy.

        overwrite:
            False -> preserve existing destination files.
            True  -> replace destination files with packaged copies.

    Subdirectories are not copied.
    """
    if not source_dir.exists() or not source_dir.is_dir():
        return

    target_dir.mkdir(parents=True, exist_ok=True)

    for pattern in patterns:
        for src in source_dir.glob(pattern):
            if not src.is_file():
                continue

            dst = target_dir / src.name

            if dst.exists() and not overwrite:
                continue

            shutil.copy2(src, dst)