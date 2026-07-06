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


def ensure_runtime_dirs(paths: AppPaths) -> None:
    """
    Ensure all standard runtime directories exist.
    """
    paths.data_dir.mkdir(parents=True, exist_ok=True)
    paths.logs_dir.mkdir(parents=True, exist_ok=True)
    paths.docs_dir.mkdir(parents=True, exist_ok=True)
    paths.bspecs_dir.mkdir(parents=True, exist_ok=True)
    paths.sounds_dir.mkdir(parents=True, exist_ok=True)


def seed_bbs_specs(paths: AppPaths) -> None:
    """
    Copy packaged BBS spec JSON files into the runtime bbs_specs directory.

    Source:
        <program resources>/data/bbs_specs/*.json

    Destination:
        <DataDir>/bbs_specs/*.json
    """
    copy_missing_files(
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
    copy_missing_files(
        source_dir = Path(paths.resource_path("data/sounds")), 
        target_dir=paths.sounds_dir,
        patterns=("*.wav", "*.mp3", "*.ogg"),
    )


def copy_missing_files(
    *,
    source_dir: Path,
    target_dir: Path,
    patterns: tuple[str, ...],
) -> None:
    """
    Copy files from source_dir to target_dir only if missing.

    Existing destination files are preserved.
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

            if dst.exists():
                continue

            shutil.copy2(src, dst)