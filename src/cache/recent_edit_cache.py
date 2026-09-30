"""
On-disk caches for home-wiki data and recent edit counts.

Network access is delegated to injected ``WikiClient`` / ``XToolsClient``
instances — this module never opens HTTP connections itself beyond those calls.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ..config import RECENT_DAYS
from ..xtools.client import XToolsClient
from .json_cache import JsonCache
from .xtools_cached import (
    get_recent_editcounts_cached,
    get_recent_editcounts_offline,
)

logger = logging.getLogger(__name__)

META_KEY = "_meta"

# ---------------------------------------------------------------------------
# Recent edit-count cache
# ---------------------------------------------------------------------------


class RecentEditCache:
    """
    Per-day edit counts backed by XTools, with contiguous range tracking.

    File layout::

        {
          "_meta": {"SomeUser": {"start": "2026-01-01", "end": "2026-06-24"}},
          "SomeUser": {"2026-01-03": 2, "2026-04-21": 5, ...}
        }
    """

    def __init__(
        self,
        path: str | Path,
        xtools: XToolsClient,
        recent_days: int = RECENT_DAYS,
    ):
        self._store = JsonCache(path)
        self._xtools = xtools
        self._recent_days = recent_days

    # -- public ----------------------------------------------------------

    def get_many(
        self,
        users: list[str],
        *,
        offline: bool = False,
        set_zero: bool = False,
        save_every: int = 5,
    ) -> dict[str, int]:
        if offline:
            return get_recent_editcounts_offline(users, set_zero=set_zero)

        return get_recent_editcounts_cached(users, set_zero=set_zero)


__all__ = [
    "RecentEditCache",
]
