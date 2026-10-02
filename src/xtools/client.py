"""
XTools Global Contributions API client (no caching).
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, date, datetime, timedelta
from urllib.parse import quote

import requests
from tqdm import tqdm

from ..config import (
    RECENT_DAYS,
    TQDM_DISABLE,
    USER_AGENT,
    XTOOLS_GLOBALCONTRIBS_URL,
)

logger = logging.getLogger(__name__)


class XToolsClient:
    """Pure HTTP adapter for XTools. Caching belongs in the cache layer."""

    def __init__(
        self,
        user_agent: str = USER_AGENT,
        timeout: int = 15,
        request_delay: float = 0.3,
    ) -> None:
        self._headers = {"User-Agent": user_agent}
        self._timeout = timeout
        self.users_not_exists: list[str] = []
        self.excluded_projects: list[str] = [
            "www.wikidata.org",
        ]
        self._request_delay = request_delay

    # ------------------------------------------------------------------
    # Date window
    # ------------------------------------------------------------------
    @staticmethod
    def load_dates(recent_days: int = RECENT_DAYS, today: date | None = None) -> tuple[str, str]:
        if today is None:
            today = datetime.now(UTC).date()
        elif isinstance(today, datetime):
            today = today.date()

        yesterday = today - timedelta(days=1)
        start = yesterday - timedelta(days=recent_days)
        return start.isoformat(), yesterday.isoformat()

    # ------------------------------------------------------------------
    # Recent edits by day
    # ------------------------------------------------------------------

    def recent_editcount_by_day(
        self,
        username: str,
        start: str,
        end: str,
    ) -> dict[str, int]:
        """
        Main orchestrator: Paginates through XTools API and aggregates edit counts.

        Count a user's edits across all Wikimedia projects in the last `days`
        days, using XTools' Global Contributions API
        (GET /api/user/globalcontribs/{username}/{namespace}/{start}/{end}/{offset}),
        which paginates via a 'continue' timestamp offset.

        Returns an empty dict if the lookup fails (e.g. XTools returns an error, or the
        user has an exceptionally high edit count and the endpoint declines to
        serve it without authentication, per XTools' own rate-limiting rules).
        """
        encoded = quote(username)
        base_url = f"{XTOOLS_GLOBALCONTRIBS_URL}/{encoded}/all/{start}/{end}"

        total_by_day: dict[str, int] = {}
        offset: str | None = None
        excluded_count = 0
        max_pages = 50  # Safety cap against runaway pagination

        for page_num in range(max_pages):
            data = self._fetch_xtools_page(base_url, username, offset, page_num)

            # Stop if request failed or XTools returned an RFC 7807 error
            # XTools error responses follow RFC 7807 (status/title/details).
            if not data or "error" in data or "status" in data:
                if data:
                    logger.warning("XTools error for %s: %s", username, data)
                logger.debug("Excluded contribs: %s", f"{excluded_count:,}")
                break

            contribs = data.get("globalcontribs") or []
            excluded_count += self._aggregate_page(contribs, total_by_day)

            offset = data.get("continue")
            if not offset:
                break
        else:
            logger.warning("Hit max_pages cap for %s", username)

        logger.debug(
            "Returning %s edit counts for %s. excluded contribs: %s",
            f"{len(total_by_day):,}",
            username,
            f"{excluded_count:,}",
        )
        return total_by_day

    def _fetch_xtools_page(self, base_url: str, username: str, offset: str | None, page_num: int) -> dict | None:
        """
        Handles the network request, specific error detection, and exponential backoff.
        """
        params: dict = {"limit": 500}
        if offset:
            params["offset"] = offset

        delay = 0.5
        max_delay = 8.0

        while delay <= max_delay:
            logger.debug("XTools globalcontribs %s round %s", username, page_num)
            try:
                response = requests.get(
                    base_url,
                    params=params,
                    headers=self._headers,
                    timeout=self._timeout,
                )
                logger.debug("status_code:%s, url:%s", response.status_code, response.url)

                # {"type":"https:\/\/tools.ietf.org\/html\/rfc2616#section-10","title":"Not Found","status":404,"detail":"The requested user does not exist","namespace":"all","limit":50,"username":"Aelita1cdcd4","elapsed_time":0.024}

                if "The requested user does not exist" in response.text:
                    self.users_not_exists.append(username)
                    logger.debug("User %s does not exist", username)
                    return None

                response.raise_for_status()
                return response.json()

            except (requests.RequestException, ValueError) as e:
                logger.error("XTools request failed for %s: %s", username, e)

                # Retry with exponential backoff
                time.sleep(delay)
                delay *= 2

        logger.debug("Giving up on %s after multiple attempts.", username)
        return None

    def _aggregate_page(self, contribs: list[dict], total_by_day: dict[str, int]) -> int:
        """
        Processes a single page of contributions, updates the totals dict in-place,
        and returns the number of excluded contributions.
        """
        excluded_count = 0
        for contrib in contribs:
            # "timestamp": "2026-04-21T09:58:49Z",
            day = contrib["timestamp"].split("T")[0]
            # "project": "ar.wikipedia.org",
            project = contrib.get("project")

            if project in self.excluded_projects:
                excluded_count += 1
                continue

            total_by_day[day] = total_by_day.get(day, 0) + 1

        return excluded_count

    def get_recent_editcount(self, username: str, start: str, end: str) -> int | None:
        """
        Sum of per-day counts, or ``None`` when no data was returned.
        """
        by_day = self.recent_editcount_by_day(username, start, end)
        if not by_day:
            return None
        return sum(by_day.values())

    # ------------------------------------------------------------------
    # recent_editcounts
    # ------------------------------------------------------------------

    def recent_editcounts(
        self,
        users: list[str],
        recent_days: int = RECENT_DAYS,
    ) -> dict[str, int]:
        """
        Uncached batch: last-``recent_days`` edit counts for each user.
        """
        start, end = self.load_dates(recent_days)
        results: dict[str, int] = {}
        logger.info("Fetching recent edits for %s users", len(users))

        for username in tqdm(users, desc="Fetching recent edits", unit="user", disable=TQDM_DISABLE):

            count = self.get_recent_editcount(username, start, end)
            if count is not None:
                results[username] = count
            time.sleep(self._request_delay)

        return results

    # ------------------------------------------------------------------
    # Last edit
    # ------------------------------------------------------------------

    def last_edit_timestamp(self, username: str) -> str | None:
        """
        Most recent global contribution date (``Y-m-d``), or ``None``.
        """
        encoded = quote(username)
        url = f"{XTOOLS_GLOBALCONTRIBS_URL}/{encoded}/all"
        try:
            response = requests.get(
                url,
                params={"limit": 1},
                headers=self._headers,
                timeout=self._timeout,
            )
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as e:
            logger.error("XTools last-edit failed for %s: %s", username, e)
            return None

        if "error" in data or "status" in data:
            logger.warning("XTools last-edit error for %s: %s", username, data)
            return None

        contribs = data.get("globalcontribs") or []
        if not contribs:
            return None

        # "timestamp": "2024-08-16T13:18:02Z" -> "2024-08-16"
        return contribs[0]["timestamp"].split("T")[0]

    def get_last_edit_timestamps(self, users: list[str]) -> dict[str, str]:
        """
        Fetch the last-edit timestamp for each user. Returns a dict mapping
        username -> date string (Y-m-d). Users with no data are omitted.
        """
        results: dict[str, str] = {}

        for username in tqdm(users, desc="Fetching last edit dates", unit="user", disable=TQDM_DISABLE):
            ts = self.last_edit_timestamp(username)
            if ts is not None:
                results[username] = ts
            time.sleep(self._request_delay)

        return results


__all__ = [
    "XToolsClient",
]
