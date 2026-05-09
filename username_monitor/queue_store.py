import json
import os
import logging
from typing import List, Dict, Any

LOGGER = logging.getLogger(__name__)


class QueueStore:
    def __init__(self, path: str = "data/pending_queue.json"):
        self.path = path
        self.items: List[Dict[str, Any]] = []

    def load(self):
        if not os.path.exists(self.path):
            self.items = []
            return
        try:
            with open(self.path) as f:
                self.items = json.load(f)
        except Exception as exc:
            LOGGER.warning("Could not load queue: %s", exc)
            self.items = []

    def save(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self.items, f)

    def pop_batch(self, n: int) -> List[Dict[str, Any]]:
        batch = self.items[:n]
        self.items = self.items[n:]
        return batch

    def push_back(self, items: List[Dict[str, Any]]):
        self.items = items + self.items

    def size(self) -> int:
        return len(self.items)

    def is_empty(self) -> bool:
        return len(self.items) == 0
