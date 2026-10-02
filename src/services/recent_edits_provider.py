"""
Recent edit counts provider: decides between the cache and the XTools client.

- ``XToolsClient`` is a pure HTTP adapter.
- ``XtoolsRecentEditCache`` is pure storage.
- ``RecentEditCountsProvider`` coordinates both.

// src/services/recent_edits_provider.py
"""

from __future__ import annotations

import logging
import time
from datetime import date, timedelta

from tqdm import tqdm

from ..cache import XtoolsRecentEditCache
from ..config import TQDM_DISABLE, Settings
from ..xtools import XToolsClient

logger = logging.getLogger(__name__)


class RecentEditCountsProvider:
    """Serve recent edit counts from the cache, fetching only what is missing."""

    def __init__(
        self,
        *,
        xtools_client: XToolsClient | None = None,
        cache_client: XtoolsRecentEditCache | None = None,
        settings: Settings | None = None,
        request_delay: float = 0.3,
    ) -> None:
        self.settings = settings or Settings.from_env()
        self.xtools_client = xtools_client or XToolsClient(user_agent=self.settings.user_agent)
        self.cache_client = cache_client or XtoolsRecentEditCache(self.settings.edit_counts_cache_path)

        self._recent_days = self.settings.recent_days
        self._request_delay = request_delay

    # -- public ----------------------------------------------------------

    def get_many(
        self,
        users: list[str],
        *,
        offline: bool = False,
        set_zero: bool = False,
        save_every: int = 5,
    ) -> dict[str, int]:
        self.cache_client.load()
        if offline:
            return self._get_offline(users, set_zero=set_zero)

        return self._get_online(
            users=users,
            set_zero=set_zero,
            save_every=save_every,
        )

    # -- internals -------------------------------------------------------

    def _get_online(
        self,
        users: list[str],
        *,
        set_zero: bool = False,
        save_every: int = 5,
    ) -> dict[str, int]:
        """
        Fetch only the days missing from the cache, merge them, and flush the
        cache every ``save_every`` users so a crash does not lose everything.
        """
        start, end = XToolsClient.load_dates(self._recent_days)
        results: dict[str, int] = {}

        logger.info("Fetching recent edits for %s users", len(users))
        for i, username in enumerate(
            tqdm(
                users,
                desc="Fetching recent edits",
                unit="user",
                disable=TQDM_DISABLE,
            ),
            start=1,
        ):
            was_cached = self.cache_client.has_coverage(username)
            count = self._get_one(username, start, end)

            if set_zero or username in self.xtools_client.users_not_exists:
                results[username] = count or 0
            elif count is not None:
                results[username] = count

            # Only throttle when the network may have been hit for this user.
            if not was_cached:
                time.sleep(self._request_delay)

            if i % save_every == 0:
                self.cache_client.save()

        self.cache_client.save()
        return results

    def _get_offline(self, users: list[str], *, set_zero: bool) -> dict[str, int]:
        """
        Cache-only lookup. Never calls the client.
        """
        start, end = XToolsClient.load_dates(self._recent_days)
        results: dict[str, int] = {}

        for username in tqdm(users, desc="Reading cached edits", unit="user", disable=TQDM_DISABLE):
            if not self.cache_client.get_counts(username):
                if set_zero:
                    results[username] = 0
                continue
            results[username] = self.cache_client.sum_in_range(username, start, end)
        return results

    def _get_one(
        self,
        username: str,
        start: str,
        end: str,
    ) -> int | None:
        """
        Return the edit count for [start, end], or ``None`` when no data exists.

        - Fully covered by the cache -> no API call.
        - Overlapping / adjacent -> fetch only the missing head and/or tail.
        - Real gap or no cache entry -> fetch the whole range fresh.
        """
        coverage = self.cache_client.get_coverage(username)

        if coverage is not None:
            cached_start = date.fromisoformat(coverage["start"])
            cached_end = date.fromisoformat(coverage["end"])
            req_start = date.fromisoformat(start)
            req_end = date.fromisoformat(end)

            if cached_start <= req_start and cached_end >= req_end:
                # Fully covered already -- no API call needed.
                return self.cache_client.sum_in_range(username, start, end)

            one_day = timedelta(days=1)
            # Figure out if the ranges are contiguous/overlapping (the common
            # case: same start, end has moved forward by ~a week) so we only
            # need to fetch the new tail. Also handle the (rarer) case where
            # the window start has moved forward and we could fetch a new tail
            # on the front, though this is less common.
            gap_after = req_start > cached_end + one_day
            gap_before = req_end < cached_start - one_day

            if not gap_after and not gap_before:
                # Overlapping or adjacent ranges: only fetch what's missing.
                fetched: dict[str, int] = {}
                if req_start < cached_start:
                    new_front_end = (cached_start - one_day).isoformat()
                    front = self.xtools_client.recent_editcount_by_day(
                        username,
                        req_start.isoformat(),
                        new_front_end,
                    )
                    fetched.update(front)

                if req_end > cached_end:
                    tail = self.xtools_client.recent_editcount_by_day(
                        username,
                        (cached_end + one_day).isoformat(),
                        end,
                    )
                    fetched.update(tail)

                self.cache_client.merge(
                    username,
                    fetched,
                    min(cached_start, req_start).isoformat(),
                    max(cached_end, req_end).isoformat(),
                )
                return self.cache_client.sum_in_range(username, start, end)

        # No cache entry, or a real gap: fetch the full range fresh.
        fetched = self.xtools_client.recent_editcount_by_day(username, start, end)

        if not fetched and coverage is None:
            # Genuine failure / no data: do not record coverage, so we retry next time.
            return None

        self.cache_client.merge(username, fetched, start, end)
        return self.cache_client.sum_in_range(username, start, end)


__all__ = [
    "RecentEditCountsProvider",
]
