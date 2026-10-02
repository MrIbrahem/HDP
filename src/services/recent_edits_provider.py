"""
Recent edit counts provider: decides between the cache and the XTools client.

- ``XToolsClient`` is a pure HTTP adapter.
- ``XtoolsRecentEditCache`` is pure storage.
- ``RecentEditCountsProvider`` coordinates both.

// src/services/recent_edits_provider.py
"""

from __future__ import annotations

import logging
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
        wikidata_cache_client: XtoolsRecentEditCache | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or Settings.from_env()
        self.xtools_client = xtools_client or XToolsClient(user_agent=self.settings.user_agent)
        self.cache_client = cache_client or XtoolsRecentEditCache(self.settings.edit_counts_cache_path)
        self.wikidata_cache_client = wikidata_cache_client or XtoolsRecentEditCache(
            self.settings.wikidata_edit_counts_cache_path
        )

        self._recent_days = self.settings.recent_days

    # -- public ----------------------------------------------------------

    def get_many(
        self,
        users: list[str],
        *,
        offline: bool = False,
        set_zero: bool = False,
        save_every: int = 5,
    ) -> tuple[dict[str, int], dict[str, int]]:
        self.cache_client.load()
        self.wikidata_cache_client.load()
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
    ) -> tuple[dict[str, int], dict[str, int]]:
        """
        Fetch only the days missing from the cache, merge them, and flush the
        cache every ``save_every`` users so a crash does not lose everything.
        """
        start, end = XToolsClient.load_dates(self._recent_days)
        results: dict[str, int] = {}
        wd_results: dict[str, int] = {}

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
            count, wd_count = self._get_one(username, start, end)

            if set_zero or username in self.xtools_client.users_not_exists:
                results[username] = count or 0
                wd_results[username] = wd_count or 0
            else:
                if count is not None:
                    results[username] = count
                if wd_count is not None:
                    wd_results[username] = wd_count

            if i % save_every == 0:
                self.cache_client.save()
                self.wikidata_cache_client.save()

        self.cache_client.save()
        self.wikidata_cache_client.save()
        return results, wd_results

    def _get_offline(self, users: list[str], *, set_zero: bool) -> tuple[dict[str, int], dict[str, int]]:
        """
        Cache-only lookup. Never calls the client.
        """
        start, end = XToolsClient.load_dates(self._recent_days)
        results: dict[str, int] = {}
        wd_results: dict[str, int] = {}

        for username in tqdm(users, desc="Reading cached edits", unit="user", disable=TQDM_DISABLE):
            has_non_wd = bool(self.cache_client.get_counts(username))
            has_wd = bool(self.wikidata_cache_client.get_counts(username))

            if not has_non_wd and not has_wd:
                if set_zero:
                    results[username] = 0
                    wd_results[username] = 0
                continue

            results[username] = self.cache_client.sum_in_range(username, start, end)
            wd_results[username] = self.wikidata_cache_client.sum_in_range(username, start, end)

        return results, wd_results

    def _get_one(
        self,
        username: str,
        start: str,
        end: str,
    ) -> tuple[int | None, int | None]:
        """
        Return the edit counts (non-wikidata, wikidata) for [start, end], or ``(None, None)`` when no data exists.

        - Fully covered by the cache -> no API call.
        - Overlapping / adjacent -> fetch only the missing head and/or tail.
        - Real gap or no cache entry -> fetch the whole range fresh.
        """
        cov_non_wd = self.cache_client.get_coverage(username)
        cov_wd = self.wikidata_cache_client.get_coverage(username)

        if cov_non_wd is not None and cov_wd is not None:
            c_start = max(cov_non_wd["start"], cov_wd["start"])
            c_end = min(cov_non_wd["end"], cov_wd["end"])

            req_start = start
            req_end = end

            if c_start <= req_start and c_end >= req_end:
                # Fully covered already -- no API call needed.
                return (
                    self.cache_client.sum_in_range(username, start, end),
                    self.wikidata_cache_client.sum_in_range(username, start, end),
                )

            cached_start = date.fromisoformat(c_start)
            cached_end = date.fromisoformat(c_end)
            r_start = date.fromisoformat(req_start)
            r_end = date.fromisoformat(req_end)

            one_day = timedelta(days=1)
            # Figure out if the ranges are contiguous/overlapping (the common
            # case: same start, end has moved forward by ~a week) so we only
            # need to fetch the new tail. Also handle the (rarer) case where
            # the window start has moved forward and we could fetch a new tail
            # on the front, though this is less common.
            gap_after = r_start > cached_end + one_day
            gap_before = r_end < cached_start - one_day

            if not gap_after and not gap_before:
                # Overlapping or adjacent ranges: only fetch what's missing.
                fetched_non_wd: dict[str, int] = {}
                fetched_wd: dict[str, int] = {}

                if r_start < cached_start:
                    new_front_end = (cached_start - one_day).isoformat()
                    front_non_wd, front_wd = self.xtools_client.recent_editcount_by_day(
                        username,
                        r_start.isoformat(),
                        new_front_end,
                    )
                    fetched_non_wd.update(front_non_wd)
                    fetched_wd.update(front_wd)

                if r_end > cached_end:
                    tail_non_wd, tail_wd = self.xtools_client.recent_editcount_by_day(
                        username,
                        (cached_end + one_day).isoformat(),
                        end,
                    )
                    fetched_non_wd.update(tail_non_wd)
                    fetched_wd.update(tail_wd)

                min_start = min(cached_start, r_start).isoformat()
                max_end = max(cached_end, r_end).isoformat()

                self.cache_client.merge(username, fetched_non_wd, min_start, max_end)
                self.wikidata_cache_client.merge(username, fetched_wd, min_start, max_end)

                return (
                    self.cache_client.sum_in_range(username, start, end),
                    self.wikidata_cache_client.sum_in_range(username, start, end),
                )

        # No cache entry, or a real gap: fetch the full range fresh.
        fetched_non_wd, fetched_wd = self.xtools_client.recent_editcount_by_day(username, start, end)

        if not fetched_non_wd and not fetched_wd and cov_non_wd is None and cov_wd is None:
            # Genuine failure / no data: do not record coverage, so we retry next time.
            return None, None

        self.cache_client.merge(username, fetched_non_wd, start, end)
        self.wikidata_cache_client.merge(username, fetched_wd, start, end)

        return (
            self.cache_client.sum_in_range(username, start, end),
            self.wikidata_cache_client.sum_in_range(username, start, end),
        )


__all__ = [
    "RecentEditCountsProvider",
]
