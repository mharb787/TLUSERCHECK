import json
import os
import logging
from typing import Any

LOGGER = logging.getLogger(__name__)


class PaginationState:
    def __init__(self, path: str = "data/pagination_state.json"):
        self.path = path
        self.state: dict = {}

    def load(self):
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path) as f:
                self.state = json.load(f)
        except Exception as exc:
            LOGGER.warning("Could not load pagination state: %s", exc)
            self.state = {}

    def save(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self.state, f, indent=2)

    def get(self, source: str, key: str, default: Any = None) -> Any:
        return self.state.get(source, {}).get(key, default)

    def set(self, source: str, key: str, value: Any):
        self.state.setdefault(source, {})[key] = value
