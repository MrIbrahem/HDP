"""
On-disk caches for home-wiki data and recent edit counts.

Network access is delegated to injected ``WikiClient`` / ``XToolsClientWithCache``
instances — this module never opens HTTP connections itself beyond those calls.

// src/cache/xtools_cache.py
"""

from __future__ import annotations

import logging
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from tqdm import tqdm

from ..config import RECENT_DAYS, TQDM_DISABLE
from ..xtools import XToolsClientWithCache
from .json_cache import JsonCache

logger = logging.getLogger(__name__)

# Reserved top-level key used to store per-user "what range have we already
# fetched" bookkeeping. Not a valid Wikimedia username, so no collision risk.
META_KEY = "_meta"

# ---------------------------------------------------------------------------
# Recent edit-count cache
# ---------------------------------------------------------------------------


class XtoolsRecentEditCache:
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
        xtools: XToolsClientWithCache,
        recent_days: int = RECENT_DAYS,
    ) -> None:
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
        """
        Cached, JSON-file-backed version of get_recent_editcounts.

        On first run, fetches everything from XTools like the original.
        On subsequent runs, only fetches the days not already covered by the
        cache file at `cache_path`, then merges and re-saves it.

        `save_every` controls how often the cache is flushed to disk while
        processing a long user list, so a crash partway through doesn't lose
        everything already fetched.
        """
        cache = self._store.load()
        cache.setdefault(META_KEY, {})
        start_s, end_s = XToolsClientWithCache.load_dates(self._recent_days)
        results: dict[str, int] = {}

        for i, username in enumerate(
            tqdm(
                users,
                desc="Fetching recent edits",
                unit="user",
                disable=TQDM_DISABLE,
            ),
            start=1,
        ):
            was_cached = username in cache.get(META_KEY, {})
            count = self._get_one(username, start_s, end_s, cache)

            if set_zero or username in self._xtools.users_not_exists:
                results[username] = count or 0
            elif count is not None:
                results[username] = count

            # Only throttle when we actually hit the network for this user.
            if not was_cached:
                time.sleep(0.3)

            if i % save_every == 0:
                self._store.save(cache)

        self._store.save(cache)
        return results

    def _offline(self, users: list[str], *, set_zero: bool) -> dict[str, int]:
        """
        Return cached-only edit counts for each user. Never hits the API.
        """
        cache = self._store.load()
        cache.setdefault(META_KEY, {})

        start_s, end_s = XToolsClientWithCache.load_dates(self._recent_days)
        results: dict[str, int] = {}
        for username in tqdm(users, desc="Reading cached edits", unit="user", disable=TQDM_DISABLE):
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
        """
        Cached version of get_recent_editcount.

        Looks at cache["_meta"][username] to see what date range has already
        been fetched for this user:
        - If [start, end] is fully covered -> no API call, sum from cache.
        - If it partially overlaps (the normal weekly-rerun case) -> fetch
            only the missing day(s) and merge them into the cache.
        - If there's no overlap at all (a real gap) -> fetch the whole
            [start, end] range fresh, to avoid silently leaving a hole.

        Mutates `cache` in place (adds/updates the user's entry). Caller is
        responsible for calling JsonCache.save() when done (batched for efficiency
        when processing many users).

        Returns None if we have no data at all for the user (mirrors the
        original function's contract).
        """
        meta = cache[META_KEY].get(username)
        user_counts: dict[str, int] = cache.setdefault(username, {})

        if meta is not None:
            cached_start = date.fromisoformat(meta["start"])
            cached_end = date.fromisoformat(meta["end"])
            req_start = date.fromisoformat(start)
            req_end = date.fromisoformat(end)

            if cached_start <= req_start and cached_end >= req_end:
                # Fully covered already -- no API call needed.
                return self._sum_in_range(user_counts, start, end)

            # Figure out if the ranges are contiguous/overlapping (the common
            # case: same start, end has moved forward by ~a week) so we only
            # need to fetch the new tail. Also handle the (rarer) case where
            # the window start has moved forward and we could fetch a new tail
            # on the front, though this is less common.
            gap_after = req_start > cached_end + timedelta(days=1)
            gap_before = req_end < cached_start - timedelta(days=1)

            if not gap_after and not gap_before:
                # Overlapping or adjacent ranges: only fetch what's missing.
                if req_start < cached_start:
                    new_var = (cached_start - timedelta(days=1)).isoformat()
                    front = self._xtools.recent_editcount_by_day(
                        username,
                        req_start.isoformat(),
                        new_var,
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

        # No cache entry, or a real gap between cached and requested ranges:
        # fetch the full range fresh.
        fetched = self._xtools.recent_editcount_by_day(username, start, end)

        if not fetched and meta is None:
            # Genuine failure/no-data case; don't record bogus meta so we
            # retry next time instead of "caching" a failure forever.
            return None

        user_counts.update(fetched)
        cache[META_KEY][username] = {"start": start, "end": end}
        return self._sum_in_range(user_counts, start, end)

    @staticmethod
    def _sum_in_range(user_counts: dict[str, Any], start: str, end: str) -> int:
        return sum(count for day, count in user_counts.items() if isinstance(count, int) and start <= day <= end)


__all__ = [
    "XtoolsRecentEditCache",
]
