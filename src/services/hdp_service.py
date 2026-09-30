"""
Domain orchestration for the Hardware Donation Program tools.

``HdpService`` is the single entry point used by the CLI: discover subpages,
build enriched rows, generate or update wikitables.
"""

from __future__ import annotations

import logging

from ..cache import HomeWikiCache, RecentEditCache
from ..config import Settings
from ..models import (
    ApplicationRow,
)
from ..wiki.category import CategoryService
from ..wiki.client import WikiClient
from ..wiki.users import UserResolver
from ..xtools.client import XToolsClient
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
        settings: Settings,
        *,
        category: CategoryService | None = None,
        users: UserResolver | None = None,
        home_cache: HomeWikiCache | None = None,
        recent_cache: RecentEditCache | None = None,
        xtools: XToolsClient | None = None,
    ):
        self.wiki = wiki
        self.settings = settings
        self.category = category or CategoryService(wiki.site)
        self.users = users or UserResolver(wiki, settings.users_redirects)
        self.xtools = xtools or XToolsClient(user_agent=settings.user_agent)
        self.home_cache = home_cache or HomeWikiCache(settings.home_wiki_cache_path, wiki)
        self.recent_cache = recent_cache or RecentEditCache(
            settings.edit_counts_cache_path,
            self.xtools,
            recent_days=settings.recent_days,
        )

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
    # Subpage discovery
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Row building
    # ------------------------------------------------------------------

    def load_rows(
        self,
        api: WikiClient,
        subpages: set[str],
        unknown_placeholder: str = "unknown",
        load_recent_editcounts: bool = True,
        load_last_edits: bool = False,
        base_page: str = BASE_PAGE,
    ) -> dict[str, Any]:

        data: list[dict[str, str]] = []

        for sub in subpages:
            sub = sub.replace("_", " ")
            full_title = f"{base_page}/{sub}"
            user_name = sub.replace("(2nd Application)", "").split("/")[0].strip()
            username = users_redirects.get(user_name.lower()) or user_name

            # first letter upper (guard against empty username)
            if username:
                username = username[0].upper() + username[1:]

            data.append(
                {
                    "full_title": full_title,
                    "sub": sub,
                    "username": username,
                }
            )

        new_data = solve_users_redirects(api, data)

        users = [x["username"] for x in new_data if x["username"]]

        # Batch-fetch application page wikitexts to extract country
        application_titles = [x["full_title"] for x in new_data]
        application_wikitexts = api.get_pages_wikitext(application_titles)
        logger.info(f"Fetched wikitext for {len(application_wikitexts)} application pages")

        editcounts = api.get_global_editcounts(users)
        logger.info(f"Loaded {len(editcounts)} editcounts for {len(users)} users")

        wikidata_editcounts = api.get_wikidata_editcounts(users)
        logger.info(f"Loaded {len(wikidata_editcounts)} Wikidata editcounts for {len(users)} users")

        recent_editcounts = {}

        if not load_recent_editcounts:
            recent_editcounts = get_recent_editcounts_offline(users, set_zero=True)
            logger.info(f"Loaded {len(recent_editcounts)} recent editcounts for {len(users)} users")
        else:
            recent_editcounts = get_recent_editcounts_cached(users, set_zero=True)
            logger.info(f"Loaded {len(recent_editcounts)} recent editcounts for {len(users)} users")

        home_wikis = get_many(api, users)
        logger.info(f"Loaded {len(home_wikis)} home wikis and registration for {len(users)} users")

        last_edits = {}
        if load_last_edits:
            last_edits = self.xtools.last_edit_timestamps(users)

        logger.info(f"Loaded {len(last_edits)} last-edit timestamps for {len(users)} users")

        rows = {}
        for sub in new_data:
            editcount_str = unknown_placeholder
            global_without_wikidata_str = unknown_placeholder
            wikidata_editcount_str = unknown_placeholder
            age = ""
            user_link = unknown_placeholder
            home_wiki = unknown_placeholder
            recent_editcount_str = unknown_placeholder
            last_edit = unknown_placeholder

            username = sub["username"]

            if username:
                user_link = f"[[User:{username}]]"

                home_data = home_wikis.get(username, {})
                if not home_data or not home_data.get("home"):
                    logger.warning(f"Home data not found for {username}")

                home_wiki = home_data.get("home", unknown_placeholder)
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

                recent_editcount = recent_editcounts.get(username)
                if recent_editcount is not None:
                    recent_editcount_str = f"{recent_editcount:,}"

                last_edit = last_edits.get(username, unknown_placeholder)
            else:
                logger.warning(f"Username not found for {sub['full_title']}")

            # Extract country from application page wikitext
            app_wikitext = application_wikitexts.get(sub["full_title"], "")
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


__all__ = ["HdpService"]
