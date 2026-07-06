# services/hotkey_profile_service.py

"""
Hot Key profile service for OpTermX.

Manages named profiles of F1-F8 text strings stored in JSON.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path


HOTKEY_NAMES = [f"F{i}" for i in range(1, 9)]


@dataclass
class HotkeyProfile:
    name: str
    keys: dict[str, str] = field(default_factory=dict)

    def normalized(self) -> "HotkeyProfile":
        clean_keys = {key: str(self.keys.get(key, "")) for key in HOTKEY_NAMES}
        return HotkeyProfile(name=self.name.strip(), keys=clean_keys)


class HotkeyProfileService:
    """
    Load, save, create, delete, and retrieve OpTermX hot key profiles.
    """

    def __init__(self, storage_path: str | Path):
        self.storage_path = Path(storage_path)
        self.active_profile: str = ""
        self.profiles: dict[str, HotkeyProfile] = {}
        self.load()

    def load(self) -> None:
        if not self.storage_path.exists():
            self._set_defaults()
            self.save()
            return

        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                raw = json.load(f)

            self.active_profile = str(raw.get("active_profile", ""))

            self.profiles = {}
            for item in raw.get("profiles", []):
                profile = HotkeyProfile(
                    name=str(item.get("name", "")).strip(),
                    keys=dict(item.get("keys", {})),
                ).normalized()

                if profile.name:
                    self.profiles[profile.name] = profile

            if self.active_profile not in self.profiles:
                self.active_profile = next(iter(self.profiles), "")

        except Exception:
            self._set_defaults()

    def save(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "active_profile": self.active_profile,
            "profiles": [
                asdict(profile.normalized())
                for profile in sorted(
                    self.profiles.values(),
                    key=lambda p: p.name.lower()
                )
            ],
        }

        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def profile_names(self) -> list[str]:
        return sorted(self.profiles.keys(), key=str.lower)

    def get_profile(self, name: str) -> HotkeyProfile | None:
        return self.profiles.get(name)

    def save_profile(self, name: str, keys: dict[str, str]) -> None:
        profile = HotkeyProfile(name=name, keys=keys).normalized()

        if not profile.name:
            raise ValueError("Profile name cannot be blank.")

        self.profiles[profile.name] = profile
        self.active_profile = profile.name
        self.save()

    def delete_profile(self, name: str) -> None:
        if name in self.profiles:
            del self.profiles[name]

        if self.active_profile == name:
            self.active_profile = next(iter(self.profile_names()), "")

        self.save()

    def set_active_profile(self, name: str) -> None:
        if name not in self.profiles:
            raise ValueError(f"Unknown hot key profile: {name}")

        self.active_profile = name
        self.save()

    def get_active_profile(self) -> HotkeyProfile | None:
        if not self.active_profile:
            return None

        return self.profiles.get(self.active_profile)

    def get_active_key_text(self, key_name: str) -> str:
        profile = self.get_active_profile()
        if profile is None:
            return ""

        key_name = key_name.upper().strip()
        return profile.keys.get(key_name, "")

    def _set_defaults(self) -> None:
        self.active_profile = "Default"
        self.profiles = {
            "Default": HotkeyProfile(
                name="Default",
                keys={key: "" for key in HOTKEY_NAMES},
            )
        }