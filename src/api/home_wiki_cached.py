"""
Cached wrapper around ``get_home_wikis_and_registration``.

Home wiki and account registration date are immutable for a given user,
so once we've fetched them we never need to hit the API again.

Cache file layout (JSON)::

    {
        "SomeUser": {
            "home": "enwiki",
            "registration": "2008-07-24T01:18:05Z"
        },
        ...
    }

Usage::

    from src.api.home_wiki_cached import get_home_wikis_cached

    home_wikis = get_home_wikis_cached(api, users)
"""

import json
import logging
import os
import time

from tqdm import tqdm

from .mwclient_req import MwclientApi

logger = logging.getLogger(__name__)

DEFAULT_CACHE_PATH = "data/home_wiki_cache.json"


def load_cache(cache_path: str = DEFAULT_CACHE_PATH) -> dict:
    """Load the cache file, returning an empty dict if it doesn't exist."""
    if not os.path.exists(cache_path):
        return {}

    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Could not read cache file {cache_path} ({e}); starting fresh")
        return {}


def save_cache(cache: dict, cache_path: str = DEFAULT_CACHE_PATH) -> None:
    """Write the cache atomically (write to temp file, then rename)."""
    tmp_path = f"{cache_path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, sort_keys=True, ensure_ascii=False)
    os.replace(tmp_path, cache_path)


def get_home_wikis_cached(
    api: MwclientApi,
    users: list[str],
    cache_path: str = DEFAULT_CACHE_PATH,
    save_every: int = 5,
) -> dict[str, dict[str, str]]:
    """Return ``{username: {"home": ..., "registration": ...}}`` for each user.

    Uses a persistent JSON cache so that users already present are never
    re-fetched from the API.  Only new (uncached) users trigger a network
    call, with a 0.1 s throttle between requests.

    Args:
        api: A ``MwclientApi`` instance (must expose ``get_global_userinfo``).
        users: List of usernames to look up.
        cache_path: Path to the JSON cache file.
        save_every: Flush the cache to disk every *save_every* new fetches
            so a crash partway through doesn't lose everything.
    """
    cache = load_cache(cache_path)

    result: dict[str, dict[str, str]] = {}
    new_count = 0

    for _, username in enumerate(tqdm(users, desc="Fetching home wiki", unit="user"), start=1):
        if username in cache:
            result[username] = cache[username]
            continue

        info = api.get_global_userinfo(username)
        entry = {
            "home": info.get("home", ""),
            "registration": info.get("registration", ""),
        }
        cache[username] = entry
        result[username] = entry
        new_count += 1

        time.sleep(0.1)

        if new_count % save_every == 0:
            save_cache(cache, cache_path)

    if new_count:
        save_cache(cache, cache_path)

    logger.info(f"Home wiki cache: {len(users) - new_count} cached, {new_count} fetched")
    return result


__all__ = [
    "get_home_wikis_cached",
]
