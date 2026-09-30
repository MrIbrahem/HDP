"""
XTools Global Contributions API client (no caching).
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import quote, urlencode

import requests
from tqdm import tqdm

from ..config import RECENT_DAYS, USER_AGENT, XTOOLS_GLOBALCONTRIBS_URL

logger = logging.getLogger(__name__)


class XToolsClient:
    """Pure HTTP adapter for XTools. Caching belongs in the cache layer."""

    def __init__(self, user_agent: str = USER_AGENT, timeout: int = 15):
        self._headers = {"User-Agent": user_agent}
        self._timeout = timeout
        self.users_not_exists: list[str] = []

    # ------------------------------------------------------------------
    # Date window
    # ------------------------------------------------------------------

    @staticmethod
    def load_dates(recent_days: int = RECENT_DAYS) -> tuple[str, str]:
        """Return ``(start, end)`` ISO dates covering the last ``recent_days`` days ending yesterday."""
        today = datetime.now(UTC).date()
        yesterday = today - timedelta(days=1)
        start = yesterday - timedelta(days=recent_days)
        return start.isoformat(), yesterday.isoformat()

    # ------------------------------------------------------------------
    # Recent edits
    # ------------------------------------------------------------------

    def recent_editcount_by_day(
        self,
        username: str,
        start: str,
        end: str,
    ) -> dict[str, int]:
        """
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
        delay = 0.5
        max_delay = 8.0
        max_pages = 50  # safety cap against runaway pagination

        for page_num in range(max_pages):
            params: dict = {"limit": 500}
            if offset:
                params["offset"] = offset

            logger.debug("XTools globalcontribs %s round %s", username, page_num)
            full_url = f"{base_url}?{urlencode(params)}"
            try:
                response = requests.get(
                    base_url,
                    params=params,
                    headers=self._headers,
                    timeout=self._timeout,
                )
                logger.debug("status_code:%s, url:%s", response.status_code, full_url)
                if "The requested user does not exist" in response.text:
                    # {"type":"https:\/\/tools.ietf.org\/html\/rfc2616#section-10","title":"Not Found","status":404,"detail":"The requested user does not exist","namespace":"all","limit":50,"username":"Aelita1cdcd4","elapsed_time":0.024}
                    self.users_not_exists.append(username)
                    return {}

                response.raise_for_status()
                data = response.json()
            except (requests.RequestException, ValueError) as e:
                logger.error("XTools request failed for %s: %s", username, e)
                if total_by_day:
                    # We got partial data before the failure; treat as a lower bound.
                    return total_by_day

                if delay >= max_delay:
                    return total_by_day

                time.sleep(delay)
                delay = min(delay * 2, max_delay)
                continue

            if "error" in data or "status" in data:
                # XTools error responses follow RFC 7807 (status/title/details).
                logger.warning("XTools error for %s: %s", username, data)
                return total_by_day

            for contrib in data.get("globalcontribs") or []:
                # "timestamp": "2026-04-21T09:58:49Z",
                day = contrib["timestamp"].split("T")[0]
                total_by_day[day] = total_by_day.get(day, 0) + 1

            offset = data.get("continue")
            if not offset:
                break

            # time.sleep(0.3)
        else:
            logger.warning("Hit max_pages cap for %s", username)

        return total_by_day

    def recent_editcount(self, username: str, start: str, end: str) -> int | None:
        """
        Sum of per-day counts, or ``None`` when no data was returned.
        """
        by_day = self.recent_editcount_by_day(username, start, end)
        if not by_day:
            return None
        return sum(by_day.values())

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
        for username in tqdm(users, desc="Fetching recent edits", unit="user"):

            count = self.recent_editcount(username, start, end)
            if count is not None:
                results[username] = count
            time.sleep(0.3)

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

    def last_edit_timestamps(self, users: list[str]) -> dict[str, str]:
        """
        Fetch the last-edit timestamp for each user. Returns a dict mapping
        username -> date string (Y-m-d). Users with no data are omitted.
        """
        results: dict[str, str] = {}

        for username in tqdm(users, desc="Fetching last edit dates", unit="user"):
            ts = self.last_edit_timestamp(username)
            if ts is not None:
                results[username] = ts
            # time.sleep(0.3)

        return results


__all__ = [
    "XToolsClient",
]
