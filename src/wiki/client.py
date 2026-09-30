"""
MediaWiki API client built on mwclient.

Wraps the former ``WikiClient`` / ``client`` helpers in a single class
that receives credentials (or an already-connected Site) and exposes the
methods needed by ``HdpService``.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import mwclient.errors
from mwclient.client import Site
from tqdm import tqdm

from ..config import USER_AGENT, Credentials, Settings

logger = logging.getLogger(__name__)


class WikiClient:
    """
    Thin, injectable wrapper around a logged-in ``mwclient.Site``.
    """

    def __init__(self, site: Site) -> None:
        self._site = site

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def connect(
        cls,
        credentials: Credentials,
        *,
        user_agent: str = USER_AGENT,
        host: str = "meta.wikimedia.org",
    ) -> WikiClient | None:
        """
        Log in to Meta Wiki and return a client, or ``None`` on failure.
        """
        try:
            logger.info("Connecting to %s ...", host)
            site = Site(host, clients_useragent=user_agent)

            logger.info("Logging in as %s ...", credentials.username)
            site.login(credentials.username, credentials.password)

            logger.info("Successfully connected and logged in")
            return cls(site)
        except mwclient.errors.LoginError as err:
            logger.error("Login failed: %s", err)
            return None
        except Exception as err:
            logger.exception("Failed to connect to %s: %s", host, err)
            return None

    @classmethod
    def connect_by_user(
        cls,
        username: str,
        password: str,
        *,
        user_agent: str = USER_AGENT,
        host: str = "meta.wikimedia.org",
    ) -> WikiClient | None:
        return cls.connect(Credentials(username, password), user_agent=user_agent, host=host)

    @classmethod
    def from_settings(cls, settings: Settings) -> WikiClient | None:
        """Convenience: load credentials from env and connect."""
        credentials = Credentials.from_env()
        if not credentials:
            logger.error("Failed to load credentials. Set WIKIPEDIA_BOT_USERNAME and WIKIPEDIA_BOT_PASSWORD.")
            return None
        return cls.connect(credentials, user_agent=settings.user_agent)

    @property
    def site(self) -> Site:
        return self._site

    # ------------------------------------------------------------------
    # Page content
    # ------------------------------------------------------------------

    def get_page_wikitext(self, page_title: str) -> str:
        """Fetch the full raw wikitext of a page via the API.

        Args:
            site (Site): The Site object representing the MediaWiki site to query.
            page_title (str): The title of the page to fetch the wikitext from.

        Returns:
            str: The raw wikitext of the page as a string. Returns an empty
            string if an exception occurs during the API request.
        """
        logger.info(f"Fetching wikitext of {page_title}...")

        page = self.site.pages[page_title]

        try:
            return page.text()
        except Exception as e:
            logger.error("API request failed %s", str(e))
            return ""

    def get_pages_wikitext(self, titles: list[str]) -> dict[str, str]:
        """Fetch wikitext for multiple pages in batches of up to 50.

        Returns a dict mapping page title -> wikitext content.
        Pages that don't exist or have no revisions are omitted.
        """
        result: dict[str, str] = {}
        batch_size = 50

        for i in range(0, len(titles), batch_size):
            batch = titles[i : i + batch_size]
            logger.info(f"Fetching wikitext for batch {i // batch_size + 1} ({len(batch)} pages)...")
            params = {
                "format": "json",
                "prop": "revisions",
                "titles": "|".join(batch),
                "rvprop": "content",
                "rvslots": "main",
                "formatversion": "2",
            }
            try:
                data = self.site.get("query", **params)
            except Exception as e:
                logger.error(f"API request failed: {e}")
                continue

            pages = data.get("query", {}).get("pages", [])
            for page in pages:
                title = page.get("title", "")
                if "missing" in page:
                    continue
                revisions = page.get("revisions", [])
                if revisions:
                    content = revisions[0].get("slots", {}).get("main", {}).get("content", "")
                    result[title] = content

            time.sleep(0.1)

        return result

    def page_last_edit_timestamp(self, page_title: str) -> str | None:
        """
        Fetches the timestamp of the last edit for a given page on a site.

        This function queries the site's API for the most recent revision of the
        specified page and extracts its timestamp. If the API request fails or
        the page does not have any revisions, it returns None.

        Args:
            site (Site): The site object used to make the API request.
            page_title (str): The title of the page to fetch the last edit timestamp for.

        Returns:
            str: The timestamp of the last edit as a string, or None if the request
                fails, the page is missing, or there are no revisions.
        """
        logger.info("Fetching last edit timestamp of %s ...", page_title)
        params = {
            "prop": "revisions",
            "titles": page_title,
            "rvlimit": 1,
            "rvprop": "timestamp",
            "formatversion": 2,
            "format": "json",
        }
        try:
            data = self._site.get("query", **params)
        except Exception as e:
            logger.error("API request failed: %s", e)
            return None

        pages = data.get("query", {}).get("pages", [])
        if pages and "revisions" in pages[0]:
            return pages[0]["revisions"][0]["timestamp"]
        return None

    def get_page_creator(self, page_title: str) -> str | None:
        """
        Retrieve the username of the user who created the page.

        This function queries the site's API to fetch the oldest revision
        (i.e., the first revision) of the specified page and returns the
        username associated with that revision.

        Args:
            site (Site): The site object used to make the API request.
            page_title (str): The title of the page to query.

        Returns:
            None | str: The username of the page creator if successful,
            otherwise None if the API request fails or no revisions are found.
        """
        logger.info("Fetching page creator of %s ...", page_title)
        params = {
            "prop": "revisions",
            "titles": page_title,
            "rvlimit": 1,
            "rvdir": "newer",
            "rvprop": "user",
            "formatversion": 2,
            "format": "json",
        }
        try:
            data = self._site.get("query", **params)
        except Exception as e:
            logger.error("API request failed: %s", e)
            return None

        pages = data.get("query", {}).get("pages", [])
        if pages and "revisions" in pages[0]:
            return pages[0]["revisions"][0]["user"]

        return None

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    def get_wikidata_editcounts(self, users: list[str]) -> dict[str, int]:
        """Fetches edit counts on Wikidata (www.wikidata.org) for a list of users.

        Args:
            users (list[str]): A list of usernames.
            site (Site | None): Optional mwclient.Site instance for Wikidata.
                If None, connects to 'www.wikidata.org'.

        Returns:
            dict[str, int]: Mapping from username to their Wikidata edit count.
        """
        if not users:
            return {}

        logger.info(f"Fetching Wikidata edit count for {len(users)} users...")
        batch_size = 50
        result: dict[str, int] = dict.fromkeys(users, 0)

        for i in range(0, len(users), batch_size):
            batch = users[i : i + batch_size]
            params = {
                "list": "users",
                "usprop": "editcount",
                "ususers": "|".join(batch),
                "formatversion": 2,
                "format": "json",
            }
            try:
                data = self._site.get("query", **params)
                user_list = data.get("query", {}).get("users", [])
                for user_info in user_list:
                    name = user_info.get("name")
                    if name:
                        result[name] = user_info.get("editcount", 0)
            except Exception as e:
                logger.error(f"API request failed for Wikidata editcounts batch {i}: {e}")

        return result

    def get_global_editcounts(self, users: list[str]) -> dict[str, int]:
        """
        Fetches the global edit counts for a list of users from a MediaWiki site.

        Args:
            site (Site): A Site object representing the MediaWiki site to query.
            users (list[str]): A list of usernames to fetch the global edit counts for.

        Returns:
            dict[str, int]: A dictionary mapping usernames to their global edit counts.
                If the API request fails or a user's edit count is unavailable,
                it defaults to 0 for that user.

        Raises:
            Exception: Catches and logs any exceptions that occur during the API request,
                but does not re-raise them.
        """
        if not users:
            return {}

        logger.info("Fetching global edit counts for %s users ...", len(users))
        params = {
            "list": "globalusers",
            "gusprop": "editcount|registration",
            "gususers": "|".join(users),
            "formatversion": 2,
            "format": "json",
        }
        try:
            data = self._site.get("query", **params)
        except Exception as e:
            logger.error("API request failed: %s", e)
            return {}

        result = data.get("query", {}).get("globalusers", [])
        # [ { "centralid": 4327653, "name": "Mr. Ibrahem", "editcount": 2017792 }, ... ]

        logger.info("Received edit counts for %s users", len(result))
        return {x["name"]: x.get("editcount", 0) for x in result}

    def get_global_userinfo(self, username: str) -> dict[str, Any]:
        """
        CentralAuth ``meta=globaluserinfo`` for a single user.

        Returns the raw 'globaluserinfo' dict, which includes:
        - 'home': dbname of the user's home wiki (e.g. "enwiki"), may be empty

        Note: meta=globaluserinfo only accepts a single username at a time
        (no batching), so this is called once per user.
        """
        params = {
            # "action": "query",
            "meta": "globaluserinfo",
            "guiuser": username,
            "guiprop": "editcount",
            "formatversion": "2",
            "format": "json",
        }
        try:
            data = self._site.get("query", **params)
        except Exception as e:
            logger.error("API request failed for %s: %s", username, e)
            return {}

        # { "globaluserinfo": { "home": "enwiki", "id": 26378, "registration": "2008-07-24T01:18:05Z", "name": "Doc James", "editcount": 2066486 }
        return data.get("query", {}).get("globaluserinfo", {}) or {}

    def get_home_wikis_and_registration(
        self,
        users: list[str],
    ) -> dict[str, dict[str, str]]:
        """
        Uncached batch helper (prefer the cache layer in production).

        Returns ``{username: {"home": ..., "registration": ...}}``.
        """
        home_wikis: dict[str, dict[str, str]] = {}
        for username in tqdm(users, desc="Fetching home wiki", unit="user"):
            info = self.get_global_userinfo(username)
            # info = { "home": "enwiki", "id": 26378, "registration": "2008-07-24T01:18:05Z", "name": "Doc James", "editcount": 2066486 }
            home_wikis[username] = {
                "home": info.get("home", ""),
                "registration": info.get("registration", ""),
            }
            time.sleep(0.1)

        return home_wikis

    def solve_pages_redirects(self, pages: list[str]) -> dict[str, str]:
        """
        Fetches and resolves redirect information for a given list of pages from a site.

        This function queries the site's API in batches of 50 pages to determine which
        pages are redirects. It returns a dictionary mapping the titles of redirect pages
        to their corresponding non-redirect (target) page titles.

        Args:
            site (Site): The site object used to interact with the API.
            pages (list[str]): A list of page title strings to check for redirects.

        Returns:
            dict[str, str]: A dictionary where keys are redirect page titles and values
            are the corresponding non-redirect (target) page titles.
        """
        logger.info(f"Fetching redirects for {len(pages)} pages...")

        params = {
            # "action": "query",
            "format": "json",
            "prop": "redirects",
            "titles": "",
            "redirects": 1,
            "formatversion": "2",
            "rdprop": "title",
            "rdlimit": "max",
        }

        result = {}
        batch_size = 50

        for i in range(0, len(pages), batch_size):
            group = pages[i : i + batch_size]
            logger.info(f"Fetching pages {i} - {min(i + batch_size, len(pages))}...")
            params["titles"] = "|".join(group)
            try:
                data = self.site.get("query", **params)
            except Exception as e:
                logger.error("API request failed %s", str(e))
                continue

            fetched_pages = data.get("query", {}).get("pages", [])
            logger.debug(f"len of group: {len(group)}, fetched_pages: {len(fetched_pages)}")

            for page in fetched_pages:
                # page example: { "ns": 2, "title": "User:The Living love" }
                if not isinstance(page, dict):
                    continue

                non_redirect_title = page["title"]
                redirects = page.get("redirects", [])

                if not redirects:
                    continue

                for redirect in redirects:
                    result[redirect["title"]] = non_redirect_title

        logger.info(f"len of data: {len(result)}")

        return result


__all__ = [
    "WikiClient",
]
