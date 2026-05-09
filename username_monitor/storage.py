import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict

LOGGER = logging.getLogger(__name__)
CACHE_VERSION = 8


class CheckedStore:
    def __init__(self, path: str) -> None:
        self.path = path
        self.data: Dict[str, Any] = {"checked": {}}

    def load(self) -> None:
        if not os.path.exists(self.path):
            self.data = {"checked": {}}
            return
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            if isinstance(loaded, dict) and isinstance(loaded.get("checked"), dict):
                self.data = loaded
            else:
                LOGGER.warning("Invalid cache format; starting with an empty cache")
                self.data = {"checked": {}}
        except (OSError, json.JSONDecodeError) as exc:
            LOGGER.warning("Could not read cache %s: %s", self.path, exc)
            self.data = {"checked": {}}

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        tmp_path = f"{self.path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(self.data, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(tmp_path, self.path)

    def seen(self, username: str) -> bool:
        entry = self.data.get("checked", {}).get(username.lower())
        return isinstance(entry, dict) and entry.get("cache_version") == CACHE_VERSION

    def mark(self, username: str, payload: Dict[str, Any]) -> None:
        checked = self.data.setdefault("checked", {})
        checked[username.lower()] = {
            **payload,
            "cache_version": CACHE_VERSION,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
