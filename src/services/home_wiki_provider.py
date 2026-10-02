"""
Home wiki data provider (wiki).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping
from typing import Any

from tqdm import tqdm

from ..cache import HomeWikiCache
from ..config import TQDM_DISABLE, Settings
from ..wiki import WikiClient

logger = logging.getLogger(__name__)


class HomeWikiProvider:
    """Serve home wiki info from the cache, fetching only unknown users from the wiki."""

    def __init__(
        self,
        *,
        wiki_client: WikiClient,
        cache_client: HomeWikiCache | None = None,
        request_delay: float = 0.1,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or Settings.from_env()
        self.cache_client = cache_client or HomeWikiCache(path=self.settings.home_wiki_cache_path)
        self.wiki_client = wiki_client
        self._request_delay = request_delay

    @property
    def _store(self) -> HomeWikiCache:
        return self.cache_client._store

    def get_many(
        self,
        users: list[str],
        *,
        save_every: int = 5,
    ) -> dict[str, Mapping[str, Any]]:
        """
        Retrieve home wiki and registration details for multiple users.

        Users with a valid cached entry are served from the cache. The others are
        fetched from the wiki, cached, and the cache is flushed every ``save_every``
        newly fetched users and once more at the end if anything new was fetched.

        Returns:
            A dict mapping usernames to their info. Users whose lookup failed are omitted.
        """
        self.cache_client.load()

        result: dict[str, Mapping[str, Any]] = {}
        remain: list[str] = []
        for username in users:
            entry = self.cache_client.get(username)
            if entry:
                result[username] = entry
            else:
                remain.append(username)

        cached_count = len(result)
        logger.info("Home wiki cache: %s cached, %s to fetch", cached_count, len(remain))

        if not remain:
            return result

        new_count = 0
        for username in tqdm(remain, desc="Fetching home wiki", unit="user", disable=TQDM_DISABLE):
            info = self.wiki_client.get_global_userinfo(username)

            user_entry = self.cache_client.validate_user_entry(info, get_editcount=True)
            if not user_entry:
                logger.warning("Failed to fetch home wiki for %s", username)
                continue

            self.cache_client.set(username, user_entry)
            result[username] = user_entry
            new_count += 1

            time.sleep(self._request_delay)

            if new_count % save_every == 0:
                self.cache_client.save()

        if new_count:
            self.cache_client.save()

        logger.info(
            "Home wiki cache: %s cached, %s fetched, all records: %s",
            cached_count,
            new_count,
            len(result),
        )
        return result


__all__ = [
    "HomeWikiProvider",
]
