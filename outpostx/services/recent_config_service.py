# services/recent_config_service.py
#
# 260702: Stores OutpostX Most Recent Config entries in DataDir JSON
# instead of QSettings/Windows registry.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class RecentConfigService:
    """
    Manage the OutpostX Most Recent Config list.

    Stored at:
        <DataDir>/outpostx_mrc.json
    """

    FILE_NAME = "outpostx_mrc.json"
    VERSION = 1
    KEY = "recent_active_configurations"

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir).expanduser().resolve()
        self.path = self.data_dir / self.FILE_NAME

    def load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []

        try:
            with self.path.open("r", encoding="utf-8") as f:
                payload = json.load(f)
        except (OSError, json.JSONDecodeError):
            return []

        items = payload.get(self.KEY, [])
        if not isinstance(items, list):
            return []

        return [item for item in items if isinstance(item, dict)]

    def save(self, items: list[dict[str, Any]]) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)

        payload = {
            "version": self.VERSION,
            self.KEY: items,
        }

        with self.path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def add(self, item: dict[str, Any], max_items: int = 10) -> None:
        items = self.load()

        # Remove duplicate item if already present.
        items = [existing for existing in items if existing != item]

        # Add newest item at the top.
        items.insert(0, item)

        # Trim list.
        items = items[:max_items]

        self.save(items)

    def clear(self) -> None:
        self.save([])
        