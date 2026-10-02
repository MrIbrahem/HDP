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
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from tqdm import tqdm

from ..config import TQDM_DISABLE
from ..wiki.client import WikiClient
from .json_cache import JsonCache

logger = logging.getLogger(__name__)

def validate_user_entry(entry: dict[str, Any], get_editcount: bool = False) -> dict[str, Any]:
    if entry and entry.get("home") and entry.get("registration"):
        data = {
            "home": entry["home"],
            "registration": entry["registration"],
        }
        if get_editcount and entry.get("editcount"):
            data["editcount"] = entry["editcount"]
        return data

    return {}

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

    def __init__(self, path: str | Path, wiki: WikiClient) -> None:
        self._store = JsonCache(path)
        self._wiki = wiki

    def _get_cached_user_data(self, users: list[str], cache: dict) -> dict[str, Any]:
        cached_result = {}
        for username in users:
            if username not in cache:
                continue

            data = validate_user_entry(cache[username])
            if data:
                cached_result[username] = data

        return cached_result

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

        result: dict[str, Mapping[str, Any]] = {}
        cached_result = self._get_cached_user_data(users, cache)

        result.update(cached_result)

        remain = [username for username in users if username not in cache]
        logger.info(
            "Home wiki cache: %s cached, %s to fetch",
            len(cached_result),
            len(remain),
        )

        if not remain:
            return result

        for username in tqdm(remain, desc="Fetching home wiki", unit="user", disable=TQDM_DISABLE):
            info = self._wiki.get_global_userinfo(username)

            user_entry = validate_user_entry(info, True)
            if not user_entry:
                logger.warning("Failed to fetch home wiki for %s", username)
                continue

            cache[username] = user_entry
            result[username] = user_entry
            new_count += 1

            time.sleep(0.1)

            if new_count % save_every == 0:
                self._store.save(cache)

        if new_count:
            self._store.save(cache)

        logger.info(
            "Home wiki cache: %s cached, %s fetched, all records: %s",
            len(cached_result),
            new_count,
            len(result),
        )
        return result


__all__ = [
    "HomeWikiCache",
]
