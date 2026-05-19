from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from endlessdb import CollectionLogicContainer, EndlessDatabase

CONFIG_PATH = Path(__file__).with_name("config.yml")


class StorageService:
    """Tiny Mongo-backed task storage service used by the sample app."""

    def __init__(self, edb: EndlessDatabase | None = None, collection_name: str | None = None) -> None:
        self._edb = edb or EndlessDatabase()
        self.config = CollectionLogicContainer.from_yml(CONFIG_PATH)
        settings = self.config.storage

        self.DEBUG = bool(settings.debug)
        self.owner = settings.owner
        self.default_tags = list(settings.default_tags)
        self.collection_name = collection_name or settings.collection
        self.items = self._edb[self.collection_name]

    def put(self, key: str, title: str, notes: str = "", tags: list[str] | None = None) -> None:
        """Create or patch a task item."""
        self.items[key] = {
            "title": title,
            "notes": notes,
            "tags": list(tags) if tags else list(self.default_tags),
            "done": False,
            "owner": self.owner,
            "created_at": datetime.now(timezone.utc),
        }

    def complete(self, key: str) -> None:
        """Mark an item as completed."""
        if not self.items().exists({"_id": key}):
            raise KeyError(f"storage item does not exist: {key}")
        item = self.items[key]
        item.done = True
        item.completed_at = datetime.now(timezone.utc)

    def list_items(self, done: bool | None = None) -> list[Any]:
        """Return task documents, optionally filtered by completion state."""
        filter_value = {} if done is None else {"done": done}
        return list(self.items().find(filter_value, sort=[("created_at", 1)]))

    def export(self) -> dict[str, Any]:
        """Return all stored items as a dictionary."""
        return self.items().to_dict()

    def reset(self) -> None:
        """Drop sample app data."""
        self._edb().mongo().drop_collection(self.collection_name)
        self._edb().collections().pop(self.collection_name, None)


EndlessService = StorageService
