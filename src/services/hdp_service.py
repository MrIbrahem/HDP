"""
Domain orchestration for the Hardware Donation Program tools.

``HdpService`` is the single entry point used by the CLI: discover subpages,
build enriched rows, generate or update wikitables.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from ..cache import HomeWikiCache, RecentEditCache
from ..cache.xtools_cached import get_recent_editcounts_cached, get_recent_editcounts_offline
from ..config import DEFAULT_USERS_REDIRECTS, Settings
from ..models import (
    ApplicationRow,
    calculate_age,
    extract_country,
)
from ..wiki.category import CategoryService
from ..wiki.client import WikiClient
from ..wiki.users import UserResolver
from ..xtools.client import XToolsClient
from .subpages_service import SubPages
from .tables_builder import build_wikitable

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
        *,
        category: CategoryService | None = None,
        users: UserResolver | None = None,
        home_cache: HomeWikiCache | None = None,
        recent_cache: RecentEditCache | None = None,
        xtools: XToolsClient | None = None,
    ):
        self.wiki = wiki
        self.settings = settings or Settings.from_env()
        self.category = category or CategoryService(wiki.site)
        self.users = users or UserResolver(wiki, settings.users_redirects)
        self.xtools = xtools or XToolsClient(user_agent=settings.user_agent)
        self.home_cache = home_cache or HomeWikiCache(settings.home_wiki_cache_path, wiki)
        self.recent_cache = recent_cache or RecentEditCache(
            settings.edit_counts_cache_path,
            self.xtools,
            recent_days=settings.recent_days,
        )
        self.subpages = SubPages(wiki, settings, category=self.category)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> HdpService | None:
        """Wire a fully configured service from env / defaults. ``None`` on login failure."""
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
        load_recent_editcounts: bool = True,
        load_last_edits: bool = False,
        unknown: str = "unknown",
    ) -> dict[str, Any]:
        """
        Build an enriched ``ApplicationRow`` for every application subpage.

        Steps mirror the former ``worker.load_rows`` pipeline.
        """
        base = self.settings.base_page

        # 1. Initial rows + username normalisation
        draft: list[dict[str, str]] = []
        for sub in subpages:
            sub = sub.replace("_", " ")
            full_title = f"{base}/{sub}"
            raw_user = sub.replace("(2nd Application)", "").split("/")[0].strip()
            username = DEFAULT_USERS_REDIRECTS.get(raw_user.lower()) or raw_user

            # first letter upper (guard against empty username)
            if username:
                username = username[0].upper() + username[1:]

            draft.append(
                {
                    "full_title": full_title,
                    "sub": sub,
                    "username": username,
                }
            )

        draft = solve_users_redirects(api, draft)

        users = [x["username"] for x in draft if x["username"]]

        # 3. Application wikitext (country)
        # Batch-fetch application page wikitexts to extract country
        titles = [r["full_title"] for r in draft]
        app_texts = self.wiki.get_pages_wikitext(titles)
        logger.info("Fetched wikitext for %s application pages", len(app_texts))

        # 4. Global edit counts
        editcounts = self.wiki.get_global_editcounts(users)
        logger.info("Loaded %s global edit counts", len(editcounts))

        wikidata_editcounts = self.wiki.get_wikidata_editcounts(users)
        logger.info(f"Loaded {len(wikidata_editcounts)} Wikidata editcounts for {len(users)} users")

        recent = {}

        # 5. Recent edit counts
        if load_recent_editcounts:
            recent = get_recent_editcounts_cached(users, set_zero=True)
        else:
            recent = get_recent_editcounts_offline(users, set_zero=True)
        logger.info("Loaded %s recent edit counts", len(recent))

        # 6. Home wiki + registration
        home_wikis = self.home_cache.get_many(users)
        logger.info("Loaded %s home-wiki records", len(home_wikis))

        # 7. Optional last-edit timestamps
        last_edits: dict[str, str] = {}
        if load_last_edits:
            last_edits = self.xtools.last_edit_timestamps(users)

            logger.info("Loaded %s last-edit timestamps", len(last_edits))

        # 8. Assemble
        rows = {}
        for sub in draft:
            editcount_str = unknown
            global_without_wikidata_str = unknown
            wikidata_editcount_str = unknown
            age = ""
            user_link = unknown
            home_wiki = unknown
            recent_editcount_str = unknown
            last_edit = unknown

            username = sub["username"]

            if username:
                user_link = f"[[User:{username}]]"

                home_data = home_wikis.get(username, {})
                if not home_data or not home_data.get("home"):
                    logger.warning(f"Home data not found for {username}")

                home_wiki = home_data.get("home", unknown)
                registration = home_data.get("registration", "")
                if registration:
                    age = calculate_age(registration)

                # logger.debug(f"User: {username}, {age=}, {home_wiki=}")

                editcount = editcounts.get(username)
                wikidata_count = wikidata_editcounts.get(username, 0)

                if isinstance(editcount, int):
                    editcount_str = f"{editcount:,}"
                    without_wikidata = max(0, editcount - wikidata_count)
                    global_without_wikidata_str = f"{without_wikidata:,}"
                    wikidata_editcount_str = f"{wikidata_count:,}"

                recent_editcount = recent.get(username)
                if recent_editcount is not None:
                    recent_editcount_str = f"{recent_editcount:,}"

                last_edit = last_edits.get(username, unknown)
            else:
                logger.warning(f"Username not found for {sub['full_title']}")

            # Extract country from application page wikitext
            app_wikitext = app_texts.get(sub["full_title"], "")
            country = extract_country(app_wikitext) if app_wikitext else ""

            row_data = {
                "age": age,
                "page_link": f"[[{sub['full_title']}]]",
                "last_update": f"{{{{#time:Y-m-d|{{{{REVISIONTIMESTAMP:{sub['full_title']}}}}}}}}}",
                "full_title": sub["full_title"],
                "user_link": user_link,
                "country": country,
                "editcount_str": editcount_str,
                "global_without_wikidata_str": global_without_wikidata_str,
                "wikidata_editcount_str": wikidata_editcount_str,
                "home_wiki": home_wiki,
                "recent_editcount_str": recent_editcount_str,
            }

            if load_last_edits:
                row_data["last_edit"] = last_edit

            rows[sub["full_title"]] = row_data

        return rows

    # ------------------------------------------------------------------
    # Table generation / update
    # ------------------------------------------------------------------

    def build_wikitable(
        self,
        rows: dict[str, ApplicationRow],
        *,
        add_last_edit: bool = False,
    ) -> str:
        """Render a fresh MediaWiki table from rows."""
        return build_wikitable(rows, add_last_edit=add_last_edit)

    def generate(
        self,
        page_title: str,
        section_names: Sequence[str],
        *,
        load_recent_editcounts: bool = True,
        load_last_edits: bool = False,
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
        rows = self.load_rows(
                subpages,
                load_recent_editcounts=load_recent_editcounts,
                load_last_edits=load_last_edits,
                unknown=unknown,
            )
            table = self.build_wikitable(rows, add_last_edit=load_last_edits)
            parts.append(f"=== {section_title} ===\n\n{table}\n")

        return "".join(parts)

    def update(
        self,
        page_title: str,
        section_names: Sequence[str],
        *,
        load_recent_editcounts: bool = True,
        load_last_edits: bool = False,
        unknown: str = "",
    ) -> str:
        """
        Refresh table cells inside an existing page (successor of ``v3_update.update``).

        Returns the full updated page wikitext.
        """
        full_wikitext = self.wiki.get_page_wikitext(page_title)
        subpages = self.subpages.discover_subpages(page_title, section_names)
        rows = self.load_rows(
            subpages,
            load_recent_editcounts=load_recent_editcounts,
            load_last_edits=load_last_edits,
            unknown=unknown,
        )

        header_map = dict(TABLE_HEADERS_TO_ROW_KEY)
        if not load_last_edits:
            header_map.pop("Last edit", None)

        # Convert rows to the dict shape the table updater expects
        row_dicts = {title: row.to_table_dict() for title, row in rows.items()}

        updater = WikiTableDataUpdater()
        return updater.update_wikitable_data(
            rows=rows,
            wikitext=full_wikitext,
            table_headers_to_row_key=header_map,
            replace_values=False,
        )


__all__ = ["HdpService"]
