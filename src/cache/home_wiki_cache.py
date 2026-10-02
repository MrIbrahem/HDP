"""
Home wiki data: on-disk cache (storage only).

// src/cache/home_wiki_cache.py
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .json_cache import JsonCache

logger = logging.getLogger(__name__)


def validate_user_entry(entry: dict[str, Any] | None, get_editcount: bool = False) -> dict[str, Any]:
    """Return a clean entry (home + registration, optional editcount) or ``{}`` if invalid."""
    if entry and entry.get("home") and entry.get("registration"):
        data = {
            "home": entry["home"],
            "registration": entry["registration"],
        }
        if get_editcount and entry.get("editcount"):
            data["editcount"] = entry["editcount"]
        return data

    return {}


# ---------------------------------------------------------------------------
# Home wiki cache
# ---------------------------------------------------------------------------


class HomeWikiCache:
    """
    Persistent storage of CentralAuth home wiki + registration date.

    Storage only: it never touches the network.

    File layout::

        {
          "SomeUser": {"home": "enwiki", "registration": "2008-07-24T01:18:05Z"},
          ...
        }

    Usage: ``load()`` -> ``get()`` / ``set()`` many times -> ``save()``.
    """

    def __init__(self, path: str | Path) -> None:
        self._store = JsonCache(path)
        self._data: dict[str, Any] = {}

    def load(self) -> None:
        """Load the cache file into memory (replaces the in-memory state)."""
        self._data = self._store.load()

    def save(self) -> None:
        """Flush the in-memory state to disk."""
        self._store.save(self._data)

    def get(self, username: str) -> dict[str, Any]:
        """Return the validated entry for the user, or ``{}`` if missing / invalid."""
        return validate_user_entry(self._data.get(username))

    def set(self, username: str, entry: dict[str, Any]) -> None:
        self._data[username] = entry

    def update(self, entries: dict[str, Any]) -> None:
        for username, entry in entries.items():
            self.set(username, entry)

    @staticmethod
    def validate_user_entry(entry: dict[str, Any] | None, get_editcount: bool = False) -> dict[str, Any]:
        return validate_user_entry(entry, get_editcount)


__all__ = [
    "HomeWikiCache",
    "validate_user_entry",
]
