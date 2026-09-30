"""
On-disk caches for home-wiki data and recent edit counts.

Network access is delegated to injected ``WikiClient`` / ``XToolsClient``
instances — this module never opens HTTP connections itself beyond those calls.
"""

from __future__ import annotations

import logging
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from tqdm import tqdm

from ..config import RECENT_DAYS
from ..xtools.client import XToolsClient
from .json_cache import JsonCache

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
            return self._offline(users, set_zero=set_zero)

        cache = self._store.load()
        cache.setdefault(META_KEY, {})
        start_s, end_s = XToolsClient.load_dates(self._recent_days)
        results: dict[str, int] = {}

        for i, username in enumerate(tqdm(users, desc="Fetching recent edits", unit="user"), start=1):
            was_cached = username in cache.get(META_KEY, {})
            count = self._get_one(username, start_s, end_s, cache)

            if set_zero or username in self._xtools.users_not_exists:
                results[username] = count or 0
            elif count is not None:
                results[username] = count

            if not was_cached:
                time.sleep(0.3)
            if i % save_every == 0:
                self._store.save(cache)

        self._store.save(cache)
        return results

    # -- internals -------------------------------------------------------

    def _offline(self, users: list[str], *, set_zero: bool) -> dict[str, int]:
        cache = self._store.load()
        start_s, end_s = XToolsClient.load_dates(self._recent_days)
        results: dict[str, int] = {}
        for username in tqdm(users, desc="Reading cached edits", unit="user"):
            user_counts = cache.get(username)
            if not user_counts:
                continue
            count = self._sum_in_range(user_counts, start_s, end_s)
            if set_zero or username in self._xtools.users_not_exists:
                results[username] = count or 0
            else:
                results[username] = count
        return results

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
