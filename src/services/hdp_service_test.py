"""
Domain orchestration for the Hardware Donation Program tools.

``HdpService`` is the single entry point used by the CLI: discover subpages,
build enriched rows, generate or update wikitables.

// src/services/hdp_service.py
"""

from __future__ import annotations

import logging

from ..cache import XtoolsRecentEditCache
from ..config import Settings
from ..wiki import WikiClient
from ..xtools import XToolsClientWithCache

logger = logging.getLogger(__name__)


class HdpService:
    """
    Orchestrates wiki + XTools + cache to produce / update HDP tracking tables.

    All collaborators are injected so unit tests can supply fakes.
    """

    def __init__(
        self,
        wiki: WikiClient,
        settings: Settings | None = None,
        wd_client: WikiClient | None = None,
        *,
        recent_cache: XtoolsRecentEditCache | None = None,
        xtools: XToolsClientWithCache | None = None,
        offline: bool = False,
    ) -> None:
        self.offline = offline
        self.wiki = wiki
        self.wd_client = wd_client if wd_client is not None else WikiClient.load(host="www.wikidata.org")
        self.settings = settings if settings is not None else Settings.from_env()
        self.xtools = xtools or XToolsClientWithCache(user_agent=self.settings.user_agent)
        self.recent_cache = recent_cache or XtoolsRecentEditCache(
            self.settings.edit_counts_cache_path,
            self.xtools,
            recent_days=self.settings.recent_days,
        )

    def _fetch_recent_edit_counts(self, users: list[str]) -> dict[str, int]:
        recent = self.recent_cache.get_many(users, offline=self.offline, set_zero=True)
        logger.info("Loaded %s recent edit counts", len(recent))
        return recent
