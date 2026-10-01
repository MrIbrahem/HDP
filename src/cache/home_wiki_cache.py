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

from collections.abc import Mapping
import logging
import time
from pathlib import Path
from typing import Any

from tqdm import tqdm

from ..config import TQDM_DISABLE
from ..wiki.client import WikiClient
from .json_cache import JsonCache

logger = logging.getLogger(__name__)

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
    ) -> dict[str, Mapping[str, Any]]:
        """
        Retrieve global user information for multiple users.

        This method fetches the home wiki and registration details for a list of users.
        It utilizes a local cache to avoid redundant API requests. For users not present
        in the cache, their information is fetched from the wiki, cached, and the cache
        is periodically saved to the underlying store based on the `save_every` parameter.

        Args:
            users (list[str]): A list of usernames to fetch information for.
            save_every (int, optional): The number of newly fetched users after which
                the cache is automatically saved to the store. Defaults to 5.

        Returns:
            dict[str, Mapping[str, Any]]: A dictionary mapping usernames to their informations

        Side Effects:
            - Sleeps for 0.1 seconds between fetching new users to avoid rate limiting.
            - Saves the updated cache to the store periodically and at the end if any
              new users were fetched.
            - Logs the number of cached and newly fetched users.
        """
        cache = self._store.load()
        new_count = 0

        result: dict[str, Mapping[str, Any]] = {
            username : cache[username] for username in users if username in cache
        }
        cached_result = len(result)

        remain = [username for username in users if username not in cache]
        logger.info(
            "Home wiki cache: %s cached, %s to fetch",
            cached_result,
            len(remain),
        )

        for username in tqdm(remain, desc="Fetching home wiki", unit="user", disable=TQDM_DISABLE):
            info = self._wiki.get_global_userinfo(username)
            entry = {
                "home": info.get("home", ""),
                "registration": info.get("registration", ""),
            }
            if not info or not (entry["home"] and entry["registration"]):
                logger.warning("Failed to fetch home wiki for %s", username)
                continue

            cache[username] = entry
            result[username] = info
            new_count += 1

            time.sleep(0.1)

            if new_count % save_every == 0:
                self._store.save(cache)

        if new_count:
            self._store.save(cache)

        logger.info(
            "Home wiki cache: %s cached, %s fetched, all records: %s",
            cached_result,
            new_count,
            len(result)
        )
        return result


__all__ = [
    "HomeWikiCache",
]
