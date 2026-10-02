"""
Domain orchestration for the Hardware Donation Program tools.

``HdpService`` is the single entry point used by the CLI: discover subpages,
build enriched rows, generate or update wikitables.

// src/services/hdp_service.py
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence

from ..config import TABLE_HEADERS_TO_ROW_KEY, Settings
from ..models import (
    ApplicationRow,
    ApplicationTable,
)
from ..parsing import WikiTableDataUpdater
from ..wiki import CategoryService, UserResolver, WikiClient
from ..xtools import XToolsClient
from .home_wiki_provider import HomeWikiProvider
from .recent_edits_provider import RecentEditCountsProvider
from .subpages_service import SubPagesService

logger = logging.getLogger(__name__)


class HdpService:
    """
    Orchestrates wiki + XTools + cache to produce / update HDP tracking tables.

    All collaborators are injected so unit tests can supply fakes.
    """

    def __init__(
        self,
        wiki_client: WikiClient,
        *,
        settings: Settings | None = None,
        wd_client: WikiClient | None = None,
        category_service: CategoryService | None = None,
        users_resolver: UserResolver | None = None,
        home_wiki_provider: HomeWikiProvider | None = None,
        recent_provider: RecentEditCountsProvider | None = None,
        xtools_client: XToolsClient | None = None,
        offline: bool = False,
    ) -> None:
        self.offline = offline
        self.wiki_client = wiki_client
        self.wd_client = wd_client if wd_client is not None else WikiClient.load(host="www.wikidata.org")
        self.settings = settings if settings is not None else Settings.from_env()
        self.category_service = category_service or CategoryService(wiki_client.site)

        self.users_resolver = users_resolver or UserResolver(wiki_client, self.settings.users_redirects)
        self.home_wiki_provider = home_wiki_provider or HomeWikiProvider(
            wiki_client=wiki_client, settings=self.settings
        )
        self.subpages = SubPagesService(
            wiki_client=wiki_client, settings=self.settings, category_service=self.category_service
        )

        self.xtools_client = xtools_client or XToolsClient(user_agent=self.settings.user_agent)

        self.recent_provider = recent_provider or RecentEditCountsProvider(
            settings=self.settings,
            xtools_client=self.xtools_client,
        )

    def set_args(self, args: argparse.Namespace) -> None:
        self.offline = args.offline
        self.load_recent_editcounts = not args.no_recent
        self.load_last_edits = args.last_edits

        if self.offline:
            logger.info("Running in offline mode")

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def load(
        cls,
        settings: Settings | None = None,
        login: bool = True,
        do_init: bool = True,
    ) -> HdpService | None:
        """
        Wire a fully configured service from env / defaults. ``None`` on login failure.
        """
        settings = settings or Settings.from_env()
        wiki = WikiClient.from_settings(
            settings=settings,
            login=login,
            do_init=do_init,
        )

        if wiki is None:
            return None

        wd_client = WikiClient.from_settings(
            settings=settings,
            host="www.wikidata.org",
            login=login,
            do_init=do_init,
        )
        return cls(wiki_client=wiki, wd_client=wd_client, settings=settings)

    # ------------------------------------------------------------------
    # Row building
    # ------------------------------------------------------------------

    def load_rows(
        self,
        subpages: set[str] | Sequence[str],
        *,
        unknown: str = "unknown",
    ) -> ApplicationTable:
        """
        Build an enriched ``ApplicationRow`` for every application subpage.

        Steps mirror the former ``worker.load_rows`` pipeline.
        """
        base = self.settings.base_page

        # 1. Initial rows + username normalisation
        rows: list[ApplicationRow] = []

        for sub in subpages:
            username = self.users_resolver.normalize(sub)
            row = ApplicationRow.from_subpage(
                sub,
                base_page=base,
                username=username,
            )

            rows.append(row)

        # 2. Live User: redirects
        usernames = [r.username for r in rows if r.username]
        live_redirects = self.users_resolver.resolve_batch(usernames)
        for row in rows:
            if row.username in live_redirects:
                row.user_info.update_username(live_redirects[row.username])

        # 3. Application wikitext (country)
        # Batch-fetch application page wikitexts to extract country
        app_texts = self.wiki_client.get_pages_wikitext([r.full_title for r in rows])

        # 9. Apply country
        for row in rows:
            wikitext = app_texts.get(row.full_title, "")
            # Extract country from application page wikitext
            if wikitext:
                row.apply_country(wikitext)

        # process rows
        rows = self._process_rows_users(rows)

        return ApplicationTable.load(rows, unknown=unknown)

    def _process_rows_users(self, rows: list[ApplicationRow]) -> list[ApplicationRow]:
        users = [r.username for r in rows if r.username]

        # 4. Global edit counts
        editcounts = self.wiki_client.get_global_editcounts(users)

        # 5. Recent edit counts
        wikidata_editcounts = self._fetch_wikidata_editcounts(users)

        # 6. Recent edit counts
        recent = self._fetch_recent_edit_counts(users)

        # 7. Home wiki + registration
        home_wikis = self.home_wiki_provider.get_many(users)

        # 8. Optional last-edit timestamps
        last_edits = self._get_last_edit_timestamps(users)

        # 9. Assemble
        for row in rows:
            if not row.username:
                logger.warning("Username not found for %s", row.full_title)
                continue

            username = row.username
            row.user_info.update(
                globaluser_data=home_wikis.get(username),
                global_editcount=editcounts.get(username),
                recent_editcount=recent.get(username),
                last_edit=last_edits.get(username),
                wikidata_count=wikidata_editcounts.get(username),
            )

        return rows

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _fetch_recent_edit_counts(self, users: list[str]) -> dict[str, int]:
        is_offline = not self.load_recent_editcounts or self.offline
        recent = self.recent_provider.get_many(users, offline=is_offline, set_zero=True)
        logger.info("Loaded %s recent edit counts", len(recent))
        return recent

    def _fetch_wikidata_editcounts(self, users: list[str]) -> dict[str, int]:

        if not self.offline:
            wikidata_editcounts = self.wd_client.get_editcounts(users)  # pyright: ignore[reportOptionalMemberAccess]
            logger.info(f"Loaded {len(wikidata_editcounts)} Wikidata editcounts for {len(users)} users")
            return wikidata_editcounts

        return {}

    def _get_last_edit_timestamps(self, users: list[str]) -> dict[str, str]:
        if self.load_last_edits and not self.offline:
            last_edits = self.wiki_client.get_last_edit_timestamps(users)
            logger.info("Loaded %s last-edit timestamps", len(last_edits))
            return last_edits

        return {}

    # ------------------------------------------------------------------
    # Table generation / update
    # ------------------------------------------------------------------

    def generate(
        self,
        page_title: str,
        section_names: Sequence[str],
        *,
        unknown: str = "unknown",
    ) -> str:
        """
        Build section-scoped tables (successor of ``v3_main.main``).

        Returns a single wikitext string with ``=== Section ===`` headings.
        """
        parts: list[str] = []
        full_wikitext = self.wiki_client.get_page_wikitext(page_title)

        for section_title in section_names:
            subpages = self.subpages._subpages_for_section(full_wikitext, section_title)
            logger.info("Section %r: %s subpages", section_title, len(subpages))
            table = self.load_rows(
                subpages,
                unknown=unknown,
            )
            table_str = table.build_wikitable(self.load_last_edits)

            parts.append(f"=== {section_title} ===\n\n{table_str}\n")

        return "".join(parts)

    def update(
        self,
        page_title: str,
        section_names: Sequence[str],
        *,
        unknown: str = "",
    ) -> str:
        """
        Refresh table cells inside an existing page (successor of ``v3_update.update``).

        Returns the full updated page wikitext.
        """
        full_wikitext = self.wiki_client.get_page_wikitext(page_title)
        subpages = self.subpages.discover_subpages(page_title, section_names, full_wikitext)

        table = self.load_rows(subpages, unknown=unknown)

        header_map = dict(TABLE_HEADERS_TO_ROW_KEY)
        if not self.load_last_edits:
            header_map.pop("Last edit", None)

        row_dicts = table.as_row_dicts()

        updater = WikiTableDataUpdater()
        return updater.update_wikitable_data(
            rows=row_dicts,
            wikitext=full_wikitext,
            table_headers_to_row_key=header_map,
            replace_values=True,
        )


__all__ = ["HdpService"]
