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

# Reserved top-level key used to store per-user "what range have we already
# fetched" bookkeeping. Not a valid Wikimedia username, so no collision risk.
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
            return self._offline(users, set_zero=set_zero)

        return self.get_online(
            users=users,
            set_zero=set_zero,
            save_every=save_every,
        )

    # -- internals -------------------------------------------------------

    def get_online(
        self,
        users: list[str],
        *,
        set_zero: bool = False,
        save_every: int = 5,
    ) -> dict[str, int]:
        return get_recent_editcounts_cached(
            users,
            set_zero=set_zero,
        )

    def _offline(self, users: list[str], *, set_zero: bool) -> dict[str, int]:
        return get_recent_editcounts_offline(users, set_zero=set_zero)

    def _get_one(
        self,
        username: str,
        start: str,
        end: str,
        cache: dict,
    ) -> int | None:
        meta = cache[META_KEY].get(username)
        user_counts: dict[str, int] = cache.setdefault(username, {})

        if meta is not None:
            cached_start = date.fromisoformat(meta["start"])
            cached_end = date.fromisoformat(meta["end"])
            req_start = date.fromisoformat(start)
            req_end = date.fromisoformat(end)

            if cached_start <= req_start and cached_end >= req_end:
                return self._sum_in_range(user_counts, start, end)

            gap_after = req_start > cached_end + timedelta(days=1)
            gap_before = req_end < cached_start - timedelta(days=1)

            if not gap_after and not gap_before:
                if req_start < cached_start:
                    front = self._xtools.recent_editcount_by_day(
                        username,
                        req_start.isoformat(),
                        (cached_start - timedelta(days=1)).isoformat(),
                    )
                    user_counts.update(front)

                if req_end > cached_end:
                    tail = self._xtools.recent_editcount_by_day(
                        username,
                        (cached_end + timedelta(days=1)).isoformat(),
                        end,
                    )
                    user_counts.update(tail)

                cache[META_KEY][username] = {
                    "start": min(cached_start, req_start).isoformat(),
                    "end": max(cached_end, req_end).isoformat(),
                }
                return self._sum_in_range(user_counts, start, end)

        fetched = self._xtools.recent_editcount_by_day(username, start, end)
        if not fetched and meta is None:
            return None

        user_counts.update(fetched)
        cache[META_KEY][username] = {"start": start, "end": end}
        return self._sum_in_range(user_counts, start, end)

    @staticmethod
    def _sum_in_range(user_counts: dict[str, Any], start: str, end: str) -> int:
        return sum(count for day, count in user_counts.items() if isinstance(count, int) and start <= day <= end)


__all__ = [
    "RecentEditCache",
]
