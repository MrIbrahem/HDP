"""
Domain orchestration for the Hardware Donation Program tools.

``HdpService`` is the single entry point used by the CLI: discover subpages,
build enriched rows, generate or update wikitables.
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence

from ..cache import HomeWikiCache, RecentEditCache
from ..config import TABLE_HEADERS_TO_ROW_KEY, Settings
from ..models import (
    ApplicationRow,
    ApplicationTable,
    UserInfo,
)
from ..parsing import WikiTableDataUpdater
from ..wiki.category import CategoryService
from ..wiki.client import WikiClient
from ..wiki.users import UserResolver
from ..xtools.client import XToolsClient
from .subpages_service import SubPages

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
        category: CategoryService | None = None,
        users: UserResolver | None = None,
        home_cache: HomeWikiCache | None = None,
        recent_cache: RecentEditCache | None = None,
        xtools: XToolsClient | None = None,
        offline: bool = False,
    ) -> None:
        self.offline = offline
        self.wiki = wiki
        self.wd_client = wd_client if wd_client is not None else WikiClient.load(host="www.wikidata.org")
        self.settings = settings if settings is not None else Settings.from_env()
        self.category = category or CategoryService(wiki.site)

        self.users = users or UserResolver(wiki, self.settings.users_redirects)
        self.xtools = xtools or XToolsClient(user_agent=self.settings.user_agent)
        self.home_cache = home_cache or HomeWikiCache(self.settings.home_wiki_cache_path, wiki)
        self.recent_cache = recent_cache or RecentEditCache(
            self.settings.edit_counts_cache_path,
            self.xtools,
            recent_days=self.settings.recent_days,
        )
        self.subpages = SubPages(wiki, self.settings, category=self.category)

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
    def load(cls, settings: Settings | None = None) -> HdpService | None:
        """
        Wire a fully configured service from env / defaults. ``None`` on login failure.
        """
        settings = settings or Settings.from_env()
        wiki = WikiClient.from_settings(settings)
        if wiki is None:
            return None
        return cls(wiki=wiki, settings=settings)

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
        draft: list[ApplicationRow] = []

        for sub in subpages:
            username = self.users.normalize(sub)
            row = ApplicationRow.from_subpage(
                sub,
                base_page=base,
                username=username,
                unknown=unknown,
            )

            draft.append(row)

        # 2. Live User: redirects
        usernames = [r.username for r in draft if r.username]
        live_redirects = self.users.resolve_batch(usernames)
        for row in draft:
            if row.username in live_redirects:
                row.username = live_redirects[row.username]
                row.user_link = f"[[User:{row.username}]]"

        users = [r.username for r in draft if r.username]

        # 3. Application wikitext (country)
        # Batch-fetch application page wikitexts to extract country
        titles = [r.full_title for r in draft]
        app_texts = self.wiki.get_pages_wikitext(titles)
        logger.info("Fetched wikitext for %s application pages", len(app_texts))

        # 4. Global edit counts
        editcounts = self.wiki.get_global_editcounts(users)
        logger.info("Loaded %s global edit counts", len(editcounts))

        wikidata_editcounts = {}

        if not self.offline:
            wikidata_editcounts = self.wd_client.get_editcounts(users)  # pyright: ignore[reportOptionalMemberAccess]
            logger.info(f"Loaded {len(wikidata_editcounts)} Wikidata editcounts for {len(users)} users")

        # 5. Recent edit counts
        if self.load_recent_editcounts and not self.offline:
            recent = self.recent_cache.get_many(users, set_zero=True)
        else:
            recent = self.recent_cache.get_many(users, offline=True, set_zero=True)
        logger.info("Loaded %s recent edit counts", len(recent))

        # 6. Home wiki + registration
        home_wikis = self.home_cache.get_many(users)
        logger.info("Loaded %s home-wiki records", len(home_wikis))

        # 7. Optional last-edit timestamps
        last_edits: dict[str, str] = {}
        if self.load_last_edits and not self.offline:
            last_edits = self.xtools.last_edit_timestamps(users)
            logger.info("Loaded %s last-edit timestamps", len(last_edits))

        # 8. Assemble
        rows: list[ApplicationRow] = []
        for row in draft:
            username = row.username
            if username:
                user_info = home_wikis.get(username) or UserInfo(username=username)

                user_info = user_info.with_editcounts(
                    global_editcount=editcounts.get(username),
                    recent_editcount=recent.get(username),
                    last_edit=last_edits.get(username),
                    wikidata_count=wikidata_editcounts.get(username),
                )
                row.apply_user_info(user_info, unknown=unknown)
            else:
                logger.warning("Username not found for %s", row.full_title)

            wikitext = app_texts.get(row.full_title, "")
            # Extract country from application page wikitext
            if wikitext:
                row.apply_country(wikitext)

            rows.append(row)

        return ApplicationTable.load(draft)

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
        full_wikitext = self.wiki.get_page_wikitext(page_title)

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
        full_wikitext = self.wiki.get_page_wikitext(page_title)
        subpages = self.subpages.discover_subpages(page_title, section_names)

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
            replace_values=False,
        )


__all__ = ["HdpService"]
