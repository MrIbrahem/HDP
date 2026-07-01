""" """

import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Optional

import requests
from urllib.parse import urlencode
from tqdm import tqdm

# How many days back counts as "recent" for the recent-edits column.
RECENT_DAYS = 90
XTOOLS_GLOBALCONTRIBS_URL = "https://xtools.wmcloud.org/api/user/globalcontribs"

USER_AGENT = "OWID-Commons-Categorizer/1.0 (https://github.com/MrIbrahem/OWID-categories; contact via GitHub)"

HEADERS = {"User-Agent": USER_AGENT}

logger = logging.getLogger(__name__)


def get_recent_editcount(username: str, days: int = RECENT_DAYS) -> Optional[int]:
    """
    Count a user's edits across all Wikimedia projects in the last `days`
    days, using XTools' Global Contributions API
    (GET /api/user/globalcontribs/{username}/{namespace}/{start}/{end}/{offset}),
    which paginates via a 'continue' timestamp offset.

    Returns None if the lookup fails (e.g. XTools returns an error, or the
    user has an exceptionally high edit count and the endpoint declines to
    serve it without authentication, per XTools' own rate-limiting rules).
    """
    today = datetime.now(UTC).date()
    start = today - timedelta(days=days)
    base_url = f"{XTOOLS_GLOBALCONTRIBS_URL}/{username}/all/{start.isoformat()}/{today.isoformat()}"

    total = 0
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
        try:
            response = requests.get(base_url, params=params, headers=HEADERS, timeout=15)
            response.raise_for_status()
            data = response.json()
            logger.debug(response.status_code, full_url)
        except (requests.RequestException, ValueError) as e:
            logger.debug(response.status_code, full_url)
            logger.error(f"XTools globalcontribs request failed for {username}: {e}")
            if total > 0:
                # We got partial data before the failure; treat as a lower bound.
                return total
            if delay >= max_delay:
                return None
            time.sleep(delay)
            delay = min(delay * 2, max_delay)
            continue

        if "error" in data or "status" in data:
            # XTools error responses follow RFC 7807 (status/title/details).
            logger.warning(f"XTools globalcontribs error for {username}: {data}")
            return None

        contribs = data.get("globalcontribs", [])
        total += len(contribs)

        offset = data.get("continue")
        if not offset:
            break

        # time.sleep(0.3)
    else:
        logger.warning(f"Hit max_pages cap fetching globalcontribs for {username}")

    return total


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

    for username in tqdm(users, desc="Fetching recent edits", unit="user"):

        recent_count = get_recent_editcount(username, days=recent_days)
        if recent_count is not None:
            recent_editcounts[username] = recent_count
        time.sleep(0.3)

    return recent_editcounts


__all__ = [
    "get_recent_editcount",
    "get_recent_editcounts",
]
