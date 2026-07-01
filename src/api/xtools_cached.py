""" """

import json
import logging
import os
import time
from datetime import UTC, date, datetime, timedelta
from typing import Optional
from urllib.parse import urlencode

import requests
from tqdm import tqdm

# How many days back counts as "recent" for the recent-edits column.
RECENT_DAYS = 90
XTOOLS_GLOBALCONTRIBS_URL = "https://xtools.wmcloud.org/api/user/globalcontribs"

USER_AGENT = "OWID-Commons-Categorizer/1.0 (https://github.com/MrIbrahem/OWID-categories; contact via GitHub)"

HEADERS = {"User-Agent": USER_AGENT}

# Default location for the on-disk cache. Override via the `cache_path`
# argument on the public functions if you want it somewhere else.
DEFAULT_CACHE_PATH = "edit_counts_cache.json"

# Reserved top-level key used to store per-user "what range have we already
# fetched" bookkeeping. Not a valid Wikimedia username, so no collision risk.
META_KEY = "_meta"

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
    base_url = f"{XTOOLS_GLOBALCONTRIBS_URL}/{username}/all/{start}/{end}"

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
        try:
            response = requests.get(base_url, params=params, headers=HEADERS, timeout=15)
            logger.debug("status_code:%s, url:%s", response.status_code, full_url)
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as e:
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
    """ """
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


# --------------------------------------------------------------------------
# Caching layer
# --------------------------------------------------------------------------
#
# Cache file layout (JSON):
#
# {
#   "_meta": {
#     "SomeUser": {"start": "2026-01-01", "end": "2026-06-24"}
#   },
#   "SomeUser": {
#     "2026-01-03": 2,
#     "2026-04-21": 5,
#     ...
#   }
# }
#
# "_meta"[user] records the contiguous [start, end] date range that has
# already been fetched from XTools for that user. Days with zero edits
# don't get a key in the per-day dict, so we can't infer "already fetched"
# from the presence/absence of a date key alone -- hence the separate
# bookkeeping.


def _iso(d: date) -> str:
    return d.isoformat()


def _parse_iso(s: str) -> date:
    return date.fromisoformat(s)


def load_cache(cache_path: str = DEFAULT_CACHE_PATH) -> dict:
    """Load the cache file, creating an empty structure if it doesn't exist."""
    if not os.path.exists(cache_path):
        return {META_KEY: {}}

    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            cache = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Could not read cache file {cache_path} ({e}); starting fresh")
        cache = {}

    cache.setdefault(META_KEY, {})
    return cache


def save_cache(cache: dict, cache_path: str = DEFAULT_CACHE_PATH) -> None:
    """Write the cache atomically (write to temp file, then rename)."""
    tmp_path = f"{cache_path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, sort_keys=True, ensure_ascii=False)
    os.replace(tmp_path, cache_path)


def _sum_in_range(user_counts: dict, start: str, end: str) -> int:
    return sum(count for day, count in user_counts.items() if start <= day <= end)


def get_recent_editcount_cached(
    username: str,
    start: str,
    end: str,
    cache: dict,
) -> Optional[int]:
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
    responsible for calling save_cache() when done (batched for efficiency
    when processing many users).

    Returns None if we have no data at all for the user (mirrors the
    original function's contract).
    """
    meta = cache[META_KEY].get(username)
    user_counts = cache.setdefault(username, {})

    if meta is not None:
        cached_start = _parse_iso(meta["start"])
        cached_end = _parse_iso(meta["end"])
        req_start = _parse_iso(start)
        req_end = _parse_iso(end)

        if cached_start <= req_start and cached_end >= req_end:
            # Fully covered already -- no API call needed.
            return _sum_in_range(user_counts, start, end)

        # Figure out if the ranges are contiguous/overlapping (the common
        # case: same start, end has moved forward by ~a week) so we only
        # need to fetch the new tail. Also handle the (rarer) case where
        # the window start has moved forward and we could fetch a new tail
        # on the front, though this is less common.
        gap_after = req_start > cached_end + timedelta(days=1)
        gap_before = req_end < cached_start - timedelta(days=1)

        if not gap_after and not gap_before:
            # Overlapping or adjacent ranges: only fetch what's missing.
            fetch_start = cached_end + timedelta(days=1) if req_end > cached_end else None
            fetch_start_front = req_start if req_start < cached_start else None

            if fetch_start_front is not None:
                new_days = _get_recent_editcount(
                    username, _iso(fetch_start_front), _iso(cached_start - timedelta(days=1))
                )
                user_counts.update(new_days)

            if fetch_start is not None:
                new_days = _get_recent_editcount(username, _iso(fetch_start), end)
                user_counts.update(new_days)

            new_start = min(cached_start, req_start)
            new_end = max(cached_end, req_end)
            cache[META_KEY][username] = {"start": _iso(new_start), "end": _iso(new_end)}

            total = _sum_in_range(user_counts, start, end)
            return total

    # No cache entry, or a real gap between cached and requested ranges:
    # fetch the full range fresh.
    fetched = _get_recent_editcount(username, start, end)

    if not fetched and meta is None:
        # Genuine failure/no-data case; don't record bogus meta so we
        # retry next time instead of "caching" a failure forever.
        return None

    user_counts.update(fetched)
    cache[META_KEY][username] = {"start": start, "end": end}
    return _sum_in_range(user_counts, start, end)


def get_recent_editcounts_cached(
    users: list[str],
    recent_days: int = RECENT_DAYS,
    cache_path: str = DEFAULT_CACHE_PATH,
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
    cache = load_cache(cache_path)

    recent_editcounts: dict[str, int] = {}

    today = datetime.now(UTC).date()
    start = today - timedelta(days=recent_days)
    start_s, end_s = start.isoformat(), today.isoformat()

    for i, username in enumerate(tqdm(users, desc="Fetching recent edits", unit="user"), start=1):
        was_cached = username in cache.get(META_KEY, {})

        recent_count = get_recent_editcount_cached(username, start=start_s, end=end_s, cache=cache)
        if recent_count is not None:
            recent_editcounts[username] = recent_count

        # Only throttle when we actually hit the network for this user.
        if not was_cached:
            time.sleep(0.3)

        if i % save_every == 0:
            save_cache(cache, cache_path)

    save_cache(cache, cache_path)
    return recent_editcounts


__all__ = [
    "get_recent_editcount",
    "get_recent_editcounts",
    "get_recent_editcount_cached",
    "get_recent_editcounts_cached",
    "load_cache",
    "save_cache",
]
