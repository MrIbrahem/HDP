"""
On-disk caches for home-wiki data and recent edit counts.

Network access is delegated to injected ``WikiClient`` / ``XToolsClient``
instances — this module never opens HTTP connections itself beyond those calls.

Cache file layout (JSON)::
    {
        "SomeUser": {
            "home": "enwiki",
            "registration": "2008-07-24T01:18:05Z"
        },
        ...
    }
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from tqdm import tqdm

from ..wiki.client import WikiClient
from .json_cache import JsonCache

logger = logging.getLogger(__name__)

DEFAULT_CACHE_PATH = "data/home_wiki_cache.json"

# ---------------------------------------------------------------------------
# Home wiki cache
# ---------------------------------------------------------------------------


class HomeWikiCache:
    """
    Persistent cache of CentralAuth home wiki + registration date.

    File layout::

        {
          "SomeUser": {"home": "enwiki", "registration": "2008-07-24T01:18:05Z"},
          ...
        }
    """

    def __init__(self, path: str | Path, wiki: WikiClient):
        self._store = JsonCache(path)
        self._wiki = wiki

    def get_many(
        self,
        users: list[str],
        *,
        save_every: int = 5,
    ) -> dict[str, dict[str, str]]:
        """Return ``{username: {"home": ..., "registration": ...}}`` for each user.

        Uses a persistent JSON cache so that users already present are never
        re-fetched from the API.  Only new (uncached) users trigger a network
        call, with a 0.1 s throttle between requests.

        Args:
            users: List of usernames to look up.
            save_every: Flush the cache to disk every *save_every* new fetches
                so a crash partway through doesn't lose everything.
        """
        cache = self._store.load()
        result: dict[str, dict[str, str]] = {}
        new_count = 0

        for username in tqdm(users, desc="Fetching home wiki", unit="user"):
            if username in cache:
                entry = cache[username]
                result[username] = entry
                continue

            info = self._wiki.get_global_userinfo(username)
            entry = {
                "home": info.get("home", ""),
                "registration": info.get("registration", ""),
            }
            cache[username] = entry
            result[username] = entry
            new_count += 1

            time.sleep(0.1)

            if new_count % save_every == 0:
                self._store.save(cache)

        if new_count:
            self._store.save(cache)

        logger.info(
            "Home wiki cache: %s cached, %s fetched",
            len(users) - new_count,
            new_count,
        )
        return result


def get_many(
    api: WikiClient,
    users: list[str],
    cache_path: str = DEFAULT_CACHE_PATH,
    save_every: int = 5,
) -> dict[str, dict[str, str]]:
    return HomeWikiCache(cache_path, api).get_many(
        users,
        save_every=save_every,
    )


__all__ = [
    "get_many",
    "HomeWikiCache",
]
