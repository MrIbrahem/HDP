"""
MediaWiki API client built on mwclient.

Wraps the former ``WikiClient`` / ``client`` helpers in a single class
that receives credentials (or an already-connected Site) and exposes the
methods needed by ``HdpService``.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

import mwclient.errors
from mwclient.client import Site
from tqdm import tqdm

from ..config import TQDM_DISABLE, USER_AGENT, Credentials, Settings

logger = logging.getLogger(__name__)

METAWIKI_HOST: str = "meta.wikimedia.org"


class WikiClientLoader:
    """ """

    DEFAULT_BATCH_SIZE = 50
    # HIGH_LIMIT_BATCH_SIZE = 500 API request failed: 414 Client Error: URI Too Long for url:
    HIGH_LIMIT_BATCH_SIZE = 100
    HIGH_LIMIT_RIGHT = "apihighlimits"

    def __init__(
        self,
        site: Site,
        batch_size: int | None = None,
        request_delay: float = 0.1,
    ) -> None:
        self._site = site
        self._batch_size = batch_size  # None => auto-detect from user rights
        self._request_delay = request_delay

    @property
    def batch_size(self) -> int:
        # Lazily detected once, then cached
        if self._batch_size is None:
            self._batch_size = self._detect_batch_size()
            logger.info("Using batch size %s", self._batch_size)
        return self._batch_size

    def _detect_batch_size(self) -> int:
        # 1) Use the rights cached by mwclient (populated on login / site init)
        #  self._site.rights: ['apihighlimits', 'read', ...]
        if self.HIGH_LIMIT_RIGHT in self._site.rights:
            logger.info(
                "User has %s right, using high limit batch size: %s", self.HIGH_LIMIT_RIGHT, self.HIGH_LIMIT_BATCH_SIZE
            )
            return self.HIGH_LIMIT_BATCH_SIZE

        logger.info(
            "User does not have %s right, using default batch size: %s", self.HIGH_LIMIT_RIGHT, self.DEFAULT_BATCH_SIZE
        )
        return self.DEFAULT_BATCH_SIZE

    # ------------------------------------------------------------------
    # Page content
    # ------------------------------------------------------------------

    def get_page_wikitext(self, page_title: str) -> str:
        """
        Fetch raw wikitext for a single page. Empty string on failure.
        """
        logger.info("Fetching wikitext of %s ...", page_title)
        try:
            return self._site.pages[page_title].text() or ""
        except Exception as e:
            logger.error("API request failed for %s: %s", page_title, e)
            return ""

    def get_pages_wikitext(self, titles: list[str]) -> dict[str, str]:
        """
        Fetch wikitext for many pages in batches of up to ``batch_size``.

        Missing pages are omitted from the result.
        """
        result: dict[str, str] = {}
        batch_size = self.batch_size

        batchs = range(0, len(titles), batch_size)
        for i in tqdm(batchs, desc="Fetching wikitext", unit=f"({batch_size}: batch", disable=TQDM_DISABLE):
            batch = titles[i : i + batch_size]
            logger.debug(
                "Fetching wikitext for batch %s (%s pages) ...",
                i // batch_size + 1,
                len(batch),
            )
            params = {
                "format": "json",
                "prop": "revisions",
                "titles": "|".join(batch),
                "rvprop": "content",
                "rvslots": "main",
                "formatversion": "2",
            }
            try:
                data = self._site.get("query", **params)
            except Exception as e:
                logger.error("API request failed: %s", e)
                continue

            for page in data.get("query", {}).get("pages", []):
                if "missing" in page:
                    continue
                title = page.get("title", "")
                revisions = page.get("revisions") or []
                if not revisions:
                    continue
                content = revisions[0].get("slots", {}).get("main", {}).get("content", "")
                result[title] = content

            time.sleep(self._request_delay)

        logger.info("Fetched wikitext for %s pages", len(result))
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

        logger.info("Page %s is missing or has no revisions", page_title)
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

    def get_editcounts(self, users: list[str]) -> dict[str, int]:
        """
        Fetches edit counts for a list of users.

        Args:
            users (list[str]): A list of usernames.

        Returns:
            dict[str, int]: Mapping from username to their edit count.
        """
        if not users:
            logger.debug("No users provided, returning empty dict")
            return {}

        logger.info(f"Fetching edit count for {len(users)} users...")
        batch_size = self.batch_size
        result: dict[str, int] = dict.fromkeys(users, 0)

        batchs = range(0, len(users), batch_size)
        for i in tqdm(batchs, desc="Fetching edit counts", unit=f"({batch_size}: batch", disable=TQDM_DISABLE):
            batch = users[i : i + batch_size]
            params = {
                "list": "users",
                "usprop": "editcount",
                "ususers": "|".join(batch),
                "formatversion": 2,
                "format": "json",
            }
            try:
                # API schema: "query": { "users": [{"userid":000,"name":"User","editcount":1000} ]}
                data = self._site.get("query", **params)
                user_list = data.get("query", {}).get("users", [])
                for user_info in user_list:
                    name = user_info.get("name")
                    if name:
                        result[name] = user_info.get("editcount", 0)
            except Exception as e:
                logger.error(f"API request failed for editcounts batch {i}: {e}")

        logger.info("Received edit counts for %s users", len(result))
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
            logger.debug("No users provided, returning empty dict")
            return {}

        batch_size = self.batch_size
        result: dict[str, int] = dict.fromkeys(users, 0)
        logger.info("Fetching global edit counts for %s users ...", len(users))

        batchs = range(0, len(users), batch_size)
        for i in tqdm(batchs, desc="Fetching global edit counts", unit=f"({batch_size}: batch", disable=TQDM_DISABLE):
            batch = users[i : i + batch_size]
            params = {
                "list": "globalusers",
                "gusprop": "editcount|registration",
                "gususers": "|".join(batch),
                "formatversion": 2,
                "format": "json",
            }
            try:
                data = self._site.get("query", **params)

                user_list = data.get("query", {}).get("globalusers", [])
                # API schema: [ { "centralid": 4327653, "name": "Mr. Ibrahem", "editcount": 2017792 }, ... ]

                logger.debug("Received edit counts for %s users", len(user_list))
                batch_data = {x["name"]: x.get("editcount", 0) for x in user_list}

                result.update(batch_data)

            except Exception as e:
                logger.error(f"API request failed for editcounts batch {i}: {e}")

        logger.info("Loaded %s global edit counts", len(result))
        return result

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
            "guiprop": "merged|editcount",
            "formatversion": "2",
            "format": "json",
            # "redirects": 1,
            # "converttitles": 1,
        }
        try:
            data = self._site.get("query", **params)
        except Exception as e:
            logger.error("API request failed for %s: %s", username, e)
            return {}

        # API schema: {"globaluserinfo":{"home":"enwiki","id":000,"registration":...}
        globaluserinfo = data.get("query", {}).get("globaluserinfo", {}) or {}

        logger.debug("Fetched globaluserinfo for %s: %s", username, globaluserinfo)
        return globaluserinfo

    def get_global_users_info(
        self,
        users: list[str],
    ) -> dict[str, dict[str, str]]:
        """
        Uncached batch helper (prefer the cache layer in production).

        Returns ``{username: {"home": ..., "registration": ...}}``.
        """
        home_wikis: dict[str, dict[str, str]] = {}

        for username in tqdm(users, desc="Fetching home wiki", unit="user", disable=TQDM_DISABLE):
            info = self.get_global_userinfo(username)
            # API schema: {"home":"enwiki","id":000,"registration":"1970-01-01T01:00:00Z","name":"User","editcount":1000}
            home_wikis[username] = {
                "home": info.get("home", ""),
                "registration": info.get("registration", ""),
                "editcount": info.get("editcount", ""),
            }
            # "globaluserinfo": { "merged": [ { "wiki": "wikidatawiki", "url": "https://www.wikidata.org", "editcount": 1711575, "registration": "2012-10-29T19:52:11Z" }
            merged = info.get("merged", []) or []
            wikidata_editcount = next((x.get("editcount", 0) for x in merged if x.get("wiki") == "wikidatawiki"), 0)
            if wikidata_editcount:
                home_wikis[username]["wikidata_editcount"] = wikidata_editcount

            time.sleep(self._request_delay)

        logger.info("Resolved %s home wikis", len(home_wikis))
        return home_wikis

    def solve_pages_redirects(self, pages: list[str]) -> dict[str, str]:
        """
        Resolve redirects for a list of page titles.

        Returns ``{redirect_title: target_title}``.
        """
        logger.info("Fetching redirects for %s pages ...", len(pages))
        batch_size = self.batch_size
        result: dict[str, str] = {}

        batchs = range(0, len(pages), batch_size)
        for i in tqdm(batchs, desc="Resolve redirects for pages", unit=f"({batch_size}: batch", disable=TQDM_DISABLE):
            group = pages[i : i + batch_size]
            logger.debug(
                "Fetching redirects %s – %s ...",
                i,
                min(i + batch_size, len(pages)),
            )
            params = {
                # "action": "query",
                "format": "json",
                "prop": "redirects",
                "titles": "|".join(group),
                "redirects": 1,
                "formatversion": "2",
                "rdprop": "title",
                "rdlimit": "max",
            }
            try:
                data = self._site.get("query", **params)
            except Exception as e:
                logger.error("API request failed: %s", e)
                continue

            for page in data.get("query", {}).get("pages", []):
                # page example: { "ns": 2, "title": "User:The Living love" }
                if not isinstance(page, dict):
                    continue
                target = page.get("title", "")
                for redirect in page.get("redirects") or []:
                    result[redirect["title"]] = target

        logger.info("Resolved %s redirects", len(result))
        return result

    # ------------------------------------------------------------------
    # Last edit
    # ------------------------------------------------------------------

    def last_edit_timestamp(self, username: str) -> str | None:
        """
        Most recent global contribution date (``Y-m-d``), or ``None``.
        """
        params = {
            # "action": "query",
            "format": "json",
            "list": "globalcontributions",
            "utf8": 1,
            "formatversion": 2,
            "guctarget": username,
            "guclimit": "1",
        }
        try:
            data = self._site.get("query", **params)
        except Exception as e:
            logger.error("API request failed for %s: %s", username, e)
            return None

        # API schema: "globalcontributions": { "entries": [ { "wikiid": "metawiki", "revid": "31116293", "timestamp": "20261002001304" }, { "wikiid": "arwiki", "revid": "76823306", "timestamp": "20261001061625" } ] }
        entries = data.get("query", {}).get("globalcontributions", {}).get("entries", []) or []
        if not entries:
            return None

        # sort by timestamp descending
        entries.sort(key=lambda x: int(x["timestamp"]), reverse=True)
        timestamp = entries[0]["timestamp"][:8]  # 20261002

        return datetime.strptime(timestamp, "%Y%m%d").strftime("%Y-%m-%d")

    def get_last_edit_timestamps(self, users: list[str]) -> dict[str, str]:
        """
        Fetch the last-edit timestamp for each user. Returns a dict mapping
        username -> date string (Y-m-d). Users with no data are omitted.
        """
        results: dict[str, str] = {}

        for username in tqdm(users, desc="Fetching last edit dates", unit="user", disable=TQDM_DISABLE):
            ts = self.last_edit_timestamp(username)
            if ts is not None:
                results[username] = ts
            # time.sleep(0.3)

        return results


class WikiClient(WikiClientLoader):
    """
    Thin, injectable wrapper around a logged-in ``mwclient.Site``.
    """

    def __init__(self, site: Site, batch_size: int | None = None) -> None:
        super().__init__(site, batch_size=batch_size)

    @property
    def site(self) -> Site:
        return self._site

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def connect(
        cls,
        credentials: Credentials,
        *,
        user_agent: str = USER_AGENT,
        host: str = METAWIKI_HOST,
        login: bool = True,
        do_init: bool = True,
    ) -> WikiClient | None:
        """
        Log in to Meta Wiki and return a client, or ``None`` on failure.
        """
        try:
            logger.info("Connecting to %s ...", host)
            site = Site(host, clients_useragent=user_agent, do_init=do_init)
            if credentials:
                if login:
                    logger.info("Logging in as %s ...", credentials.username)
                    site.login(credentials.username, credentials.password)
                else:
                    site.credentials = (credentials.username, credentials.password, None)

            logger.info("Successfully connected and logged in")
            return cls(site)
        except mwclient.errors.LoginError as err:
            logger.error("Login failed: %s", err)
            return None
        except Exception as err:
            logger.exception("Failed to connect to %s: %s", host, err)
            return None

    @classmethod
    def load(
        cls,
        settings: Settings | None = None,
        host: str = METAWIKI_HOST,
        login: bool = True,
        do_init: bool = True,
    ) -> WikiClient | None:
        """
        Convenience: load credentials from env and connect.
        """
        if not settings:
            settings = Settings.from_env()

        credentials = Credentials.from_env()

        if not credentials and login:
            logger.error("Failed to load credentials. Set WIKIPEDIA_BOT_USERNAME and WIKIPEDIA_BOT_PASSWORD.")
            return None

        return cls.connect(
            credentials=credentials,
            user_agent=settings.user_agent,
            host=host,
            login=login,
            do_init=do_init,
        )

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        host: str = METAWIKI_HOST,
        login: bool = True,
        do_init: bool = True,
    ) -> WikiClient | None:
        """Convenience: load credentials from env and connect."""
        return cls.load(
            settings=settings,
            host=host,
            login=login,
            do_init=do_init,
        )


__all__ = [
    "WikiClient",
]
