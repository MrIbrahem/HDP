""" """

import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Optional

import requests
from urllib.parse import quote, urlencode
from tqdm import tqdm

from src. import USER_AGENT

# How many days back counts as "recent" for the recent-edits column.
RECENT_DAYS = 90
XTOOLS_GLOBALCONTRIBS_URL = "https://xtools.wmcloud.org/api/user/globalcontribs"

HEADERS = {"User-Agent": USER_AGENT}

logger = logging.getLogger(__name__)


def _get_recent_editcount(username: str, start: str, end: str) -> dict[str, int]:
    """
    Count a user's edits across all Wikimedia projects in the last `days`
    days, using XTools' Global Contributions API
    (GET /api/user/globalcontribs/{username}/{namespace}/{start}/{end}/{offset}),
    which paginates via a 'continue' timestamp offset.

    Returns None if the lookup fails (e.g. XTools returns an error, or the
    user has an exceptionally high edit count and the endpoint declines to
    serve it without authentication, per XTools' own rate-limiting rules).
    """
    encoded_username = quote(username)
    base_url = f"{XTOOLS_GLOBALCONTRIBS_URL}/{encoded_username}/all/{start}/{end}"

    total_by_day = {}
    offset = None
    delay = 0.5
    max_delay = 8.0
    max_pages = 50  # safety cap against runaway pagination

    for _ in range(max_pages):
        params = {"limit": 500}

        if offset:
            params["offset"] = offset

        logger.debug(f"XTools globalcontribs request for {username}, round: {_}")
        full_url = f"{base_url}?{urlencode(params)}"
        response = None
        try:
            response = requests.get(base_url, params=params, headers=HEADERS, timeout=15)
            response.raise_for_status()
            data = response.json()
            logger.debug("status_code:%s, url:%s", response.status_code, full_url)
        except (requests.RequestException, ValueError) as e:
            status_code = response.status_code if response is not None else "N/A"
            logger.debug("status_code:%s, url:%s", status_code, full_url)
            logger.error(f"XTools globalcontribs request failed for {username}: {e}")
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
            logger.warning(f"XTools globalcontribs error for {username}: {data}")
            return total_by_day

        contribs = data.get("globalcontribs", [])
        for contrib in contribs:
            # "timestamp": "2026-04-21T09:58:49Z",
            timestamp = contrib["timestamp"].split("T")[0]
            total_by_day.setdefault(timestamp, 0)
            total_by_day[timestamp] += 1

        offset = data.get("continue")
        if not offset:
            break

        # time.sleep(0.3)
    else:
        logger.warning(f"Hit max_pages cap fetching globalcontribs for {username}")

    return total_by_day

def get_recent_editcount(username: str, start: str, end: str) -> Optional[int]:
    """
    """
    total_by_day = _get_recent_editcount(username, start, end)

    if not total_by_day:
        return None
    return sum(total_by_day.values())


def get_recent_editcounts(
    users: list[str],
    recent_days: int = RECENT_DAYS,
) -> dict[str, int]:
    """
    For each username:
      - fetch their last-`recent_days`-day global edit count via XTools'
        Global Contributions API

    Returns recent_editcounts
    """
    recent_editcounts: dict[str, int] = {}

    today = datetime.now(UTC).date()
    start = today - timedelta(days=recent_days)

    for username in tqdm(users, desc="Fetching recent edits", unit="user"):

        recent_count = get_recent_editcount(username, start=start.isoformat(), end=today.isoformat())
        if recent_count is not None:
            recent_editcounts[username] = recent_count
        time.sleep(0.3)

    return recent_editcounts


__all__ = [
    "get_recent_editcount",
    "get_recent_editcounts",
]
