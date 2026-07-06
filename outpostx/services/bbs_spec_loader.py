# services/bbs_spec_loader.py
"""
BBS spec loader.

This module loads JSON "spec" files that describe how to interact with specific
BBS implementations (KPC-3+, JNOS, etc.).

Why specs exist
--------------
Different BBS flavors vary in:
- Prompts (how you know the BBS is ready for the next command)
- Message listing formats (LM/LB/LT output)
- Read-message header formats (R <msgno> output)
- Success/failure strings for connects and commands

OutpostX isolates those differences in data files under:

    <project_root>/data/bbs_specs/*_spec.json

Architectural role
------------------
- BBSSpecLoader finds and loads the JSON file into a BBSSpec wrapper.
- BBSProtocolAdapter binds a BBSSpec to drive parsing and prompt matching.
- This module does not parse terminal output itself; it only loads and exposes spec data.

Design notes
------------
- resolve_spec_id() maps a SID token (e.g., "KPC3P") to a spec id ("kpc3").
- load_by_id("kpc3") loads "kpc3_spec.json" from the spec directory.
- Spec directory defaults to <project_root>/data/bbs_specs based on this file's path.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from services.app_paths import AppPaths


@dataclass(frozen=True)
class BBSSpec:
    """Loaded BBS spec wrapper (raw dict plus convenience properties).

    The underlying JSON is kept in `raw` to avoid coupling this wrapper to a
    particular schema version. Properties expose the most commonly used fields.
    """
    raw: dict[str, Any]
    source_path: Path

    @property
    def id(self) -> str:
        """Spec identifier (raw['id'])."""
        return str(self.raw.get("id", "")).strip()

    @property
    def name(self) -> str:
        """Human-friendly spec name (raw['name'])."""
        return str(self.raw.get("name", "")).strip()

    @property
    def prompt_pattern(self) -> str:
        """Regex pattern used to detect the BBS prompt."""
        prompt = self.raw.get("prompt", {}) or {}
        return str(prompt.get("pattern", "")).strip()

    @property
    def prompt_case_insensitive(self) -> bool:
        """Whether prompt matching should be case-insensitive."""
        prompt = self.raw.get("prompt", {}) or {}
        return bool(prompt.get("case_insensitive", False))


class BBSSpecLoader:
    """
    Loader for spec JSON files under a directory.

    Default location:
      <project_root>/data/bbs_specs/

    Resolution helpers:
      - resolve_spec_id(sid_type) maps SID token -> spec id
      - load_by_id('kpc3') loads: data/bbs_specs/kpc3_spec.json
      - load_for_sid_type('KPC3P') loads: data/bbs_specs/kpc3_spec.json

    This class does not validate the schema in depth; validation is intentionally
    lightweight so you can iterate on spec structure quickly.
    """

    DEFAULT_ALIAS_MAP = {
        "KPC3": "kpc3",
        "KPC3P": "kpc3",
        "JNOS": "jnos",
        "WL2K": "wl2k",  
        "BPQ": "bpq",
    }

    def __init__(self, spec_dir: Optional[Path] = None, app_paths: Optional[AppPaths] = None) -> None:
        """
        Create a BBS spec loader.

        If spec_dir is provided, use it directly.
        Otherwise, use the standard OutpostX data directory:

            <DataDir>/bbs_specs
        """
        self.app_paths = app_paths or AppPaths(app_name="OutpostX")
        self.spec_dir = Path(spec_dir) if spec_dir else self.app_paths.bspecs_dir

    def resolve_spec_id(self, sid_type: str) -> str:
        """Map a SID token (e.g., 'KPC3P') to a normalized spec id (e.g., 'kpc3')."""
        key = (sid_type or "").strip().upper()
        return self.DEFAULT_ALIAS_MAP.get(key, key.lower())

    def load_by_id(self, spec_id: str) -> BBSSpec:
        """Load a spec by id from <spec_dir>/<id>_spec.json."""
        sid = (spec_id or "").strip().lower()
        path = self.spec_dir / f"{sid}_spec.json"
        if not path.exists():
            raise FileNotFoundError(f"Spec file not found: {path}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        return BBSSpec(raw=raw, source_path=path)

    def load_for_sid_type(self, sid_type: str) -> BBSSpec:
        """Resolve and load a spec by SID type token (convenience helper)."""
        spec_id = self.resolve_spec_id(sid_type)
        return self.load_by_id(spec_id)
