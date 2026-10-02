"""
Home wiki data provider (wiki).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from ..cache import HomeWikiCache
from ..config import Settings
from ..wiki import WikiClient

logger = logging.getLogger(__name__)


class HomeWikiProvider:
    """Serve home wiki info from the cache, fetching only unknown users from the wiki."""

    def __init__(
        self,
        *,
        wiki_client: WikiClient,
        cache_client: HomeWikiCache | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or Settings.from_env()
        self.cache_client = cache_client or HomeWikiCache(path=self.settings.home_wiki_cache_path)
        self.wiki_client = wiki_client

    @property
    def _store(self) -> HomeWikiCache:
        return self.cache_client._store

    def get_many(
        self,
        users: list[str],
    ) -> dict[str, Mapping[str, Any]]:
        """
        Retrieve home wiki and registration details for multiple users.

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

        global_result = self.wiki_client.get_global_users_info(remain)

        live_result = {}
        for username, info in global_result.items():
            user_entry = self.cache_client.validate_user_entry(info, get_editcount=True)
            if not user_entry:
                logger.warning("Failed to fetch home wiki for %s", username)
                continue

            live_result[username] = user_entry

        if live_result:
            self.cache_client.update(live_result)
            self.cache_client.save()
            result.update(live_result)

        logger.info(
            "Home wiki cache: %s cached, %s fetched, all records: %s",
            cached_count,
            len(live_result),
            len(result),
        )
        return result


__all__ = [
    "HomeWikiProvider",
]
