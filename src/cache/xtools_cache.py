"""
On-disk storage for per-day recent edit counts.

This module is storage only: it knows nothing about XTools or the network.
Fetch / reuse decisions live in ``RecentEditCountsProvider``.

// src/cache/xtools_cache.py
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .json_cache import JsonCache

logger = logging.getLogger(__name__)

# Reserved top-level key used to store per-user "which range has been fetched"
# bookkeeping. Not a valid Wikimedia username, so no collision risk.
META_KEY = "_meta"

# ---------------------------------------------------------------------------
# Recent edit-count cache
# ---------------------------------------------------------------------------


class XtoolsRecentEditCache:
    """
    Per-day edit counts with per-user coverage tracking.

    File layout::

        {
          "_meta": {"SomeUser": {"start": "2026-01-01", "end": "2026-06-24"}},
          "SomeUser": {"2026-01-03": 2, "2026-04-21": 5, ...}
        }

    Usage: ``load()`` -> read / ``merge()`` many times -> ``save()``.
    """

    def __init__(self, path: str | Path) -> None:
        self._store = JsonCache(path)
        self._data: dict[str, Any] = {META_KEY: {}}

    # -- persistence -----------------------------------------------------

    def load(self) -> None:
        """Load the cache file into memory (replaces the in-memory state)."""
        self._data = self._store.load()
        self._data.setdefault(META_KEY, {})

    def save(self) -> None:
        """Flush the in-memory state to disk."""
        self._store.save(self._data)

    # -- queries ---------------------------------------------------------

    def get_coverage(self, username: str) -> dict[str, Any] | None:
        """Return the (start, end) ISO dates already fetched for the user, if any."""
        meta = self._data[META_KEY].get(username)
        if meta is None:
            return None
        return meta

    def has_coverage(self, username: str) -> bool:
        return username in self._data[META_KEY]

    def get_counts(self, username: str) -> dict[str, int]:
        """Return the stored per-day counts for the user (empty dict if none)."""
        return self._data.get(username) or {}

    def sum_in_range(self, username: str, start: str, end: str) -> int:
        """Sum the stored counts for days within [start, end] (ISO strings, inclusive)."""
        user_counts = self.get_counts(username)
        return self._sum_in_range(user_counts, start, end)

    @staticmethod
    def _sum_in_range(user_counts: dict[str, Any], start: str, end: str) -> int:
        return sum(count for day, count in user_counts.items() if isinstance(count, int) and start <= day <= end)


    # -- mutations -------------------------------------------------------

    def merge(
        self,
        username: str,
        counts: dict[str, int],
        start: str,
        end: str,
    ) -> None:
        """
        Merge per-day counts into the user's entry and record [start, end]
        as the covered range. The caller decides what the new range is.
        """
        self._data.setdefault(username, {}).update(counts)
        self._data[META_KEY][username] = {"start": start, "end": end}


__all__ = [
    "META_KEY",
    "XtoolsRecentEditCache",
]
