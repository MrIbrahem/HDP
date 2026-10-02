"""
On-disk storage for per-day recent edit counts.

This module is storage only: it knows nothing about XTools or the network.
Fetch / reuse decisions live in ``RecentEditCountsProvider``.

// src/cache/xtools_cache.py

cache file example:
{
  "Mr. Ibrahem": {
    "2026-07-02": 11,
    "2026-07-03": 20,
    ....,
    "2026-09-26": 6,
    "2026-09-30": 0
  },
  "Ogundele1": {
    "2026-07-02": 0,
    "2026-07-06": 4,
    ....,
    "2026-09-13": 1,
    "2026-09-30": 0
  }
}

Coverage is derived from the first and last date stored for each user.
``merge()`` writes the boundary days (``start`` / ``end``) with a count of 0
when they have no edits, so the covered range is never lost.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .json_cache import JsonCache

logger = logging.getLogger(__name__)

# Legacy key from older cache files. It is dropped on load.
_LEGACY_META_KEY = "_meta"

# ---------------------------------------------------------------------------
# Recent edit-count cache
# ---------------------------------------------------------------------------


class XtoolsRecentEditCache:
    """
    Per-day edit counts. Coverage is derived from the min / max stored date.

    File layout::

        {
          "SomeUser": {"2026-01-01": 0, "2026-01-03": 2, "2026-04-21": 5, "2026-06-24": 0}
        }

    Usage: ``load()`` -> read / ``merge()`` many times -> ``save()``.
    """

    def __init__(self, path: str | Path) -> None:
        self._store = JsonCache(path)
        self._data: dict[str, Any] = {}

    # -- persistence -----------------------------------------------------

    def load(self) -> None:
        """Load the cache file into memory (replaces the in-memory state)."""
        self._data = self._store.load()
        # Drop the old bookkeeping table if the file was written by an older version.
        self._data.pop(_LEGACY_META_KEY, None)

    def save(self) -> None:
        """Flush the in-memory state to disk."""
        self._store.save(self._data)

    # -- queries ---------------------------------------------------------

    def get_coverage(self, username: str) -> dict[str, Any] | None:
        """Return {"start", "end"} (ISO dates) already fetched for the user, if any."""
        days = self.get_counts(username)
        if not days:
            return None
        # ISO dates sort correctly as strings.
        return {"start": min(days), "end": max(days)}

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

    def merge(self, username: str, counts: dict[str, int], start: str, end: str) -> None:
        """
        Merge per-day counts into the user's entry.

        ``start`` and ``end`` are stored as boundary days (count 0 if they had
        no edits) so that min/max of the stored dates reflects the covered range.
        """
        user_data = self._data.setdefault(username, {})
        user_data.update(counts)
        user_data.setdefault(start, 0)
        user_data.setdefault(end, 0)


__all__ = [
    "XtoolsRecentEditCache",
]
