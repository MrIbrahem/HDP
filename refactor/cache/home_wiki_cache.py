"""
On-disk caches for home-wiki data and recent edit counts.

Network access is delegated to injected ``WikiClient`` / ``XToolsClient``
instances — this module never opens HTTP connections itself beyond those calls.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from tqdm import tqdm

from ..config import RECENT_DAYS
from ..models import UserInfo
from ..wiki.client import WikiClient
from ..xtools.client import XToolsClient

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
    ) -> dict[str, UserInfo]:
        cache = self._store.load()
        result: dict[str, UserInfo] = {}
        new_count = 0

        for username in tqdm(users, desc="Fetching home wiki", unit="user"):
            if username in cache:
                entry = cache[username]
                result[username] = UserInfo(
                    username=username,
                    home_wiki=entry.get("home", ""),
                    registration=entry.get("registration", ""),
                )
                continue

            info = self._wiki.get_global_userinfo(username)
            entry = {
                "home": info.get("home", ""),
                "registration": info.get("registration", ""),
            }
            cache[username] = entry
            result[username] = UserInfo.from_globaluserinfo(username, info)
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

__all__ = [
    "HomeWikiCache",
]
