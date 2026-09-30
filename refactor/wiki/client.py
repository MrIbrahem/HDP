"""
MediaWiki API client built on mwclient.

Wraps the former ``MwclientApi`` / ``mwclient_req`` helpers in a single class
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
    """Thin, injectable wrapper around a logged-in ``mwclient.Site``."""

    def __init__(self, site: Site):
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
        """Fetch raw wikitext for a single page. Empty string on failure."""
        logger.info("Fetching wikitext of %s ...", page_title)
        try:
            return self._site.pages[page_title].text() or ""
        except Exception as e:
            logger.error("API request failed for %s: %s", page_title, e)
            return ""

    def get_pages_wikitext(self, titles: list[str], batch_size: int = 50) -> dict[str, str]:
        """
        Fetch wikitext for many pages in batches of up to ``batch_size``.

        Missing pages are omitted from the result.
        """
        result: dict[str, str] = {}

        for i in range(0, len(titles), batch_size):
            batch = titles[i : i + batch_size]
            logger.info(
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

            time.sleep(0.1)

        return result

    def page_last_edit_timestamp(self, page_title: str) -> str | None:
        """Most recent revision timestamp, or ``None``."""
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
        """Username of the first revision (page creator), or ``None``."""
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

    def get_global_editcounts(self, users: list[str]) -> dict[str, int]:
        """
        Global edit counts via ``list=globalusers``.

        Users that cannot be resolved are omitted (caller can default to 0).
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
        logger.info("Received edit counts for %s users", len(result))
        return {x["name"]: x.get("editcount", 0) for x in result}

    def get_global_userinfo(self, username: str) -> dict[str, Any]:
        """
        CentralAuth ``meta=globaluserinfo`` for a single user.

        Returns the raw ``globaluserinfo`` dict (may be empty on failure).
        """
        params = {
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
            home_wikis[username] = {
                "home": info.get("home", ""),
                "registration": info.get("registration", ""),
            }
            time.sleep(0.1)
        return home_wikis

    def solve_pages_redirects(self, pages: list[str], batch_size: int = 50) -> dict[str, str]:
        """
        Resolve redirects for a list of page titles.

        Returns ``{redirect_title: target_title}``.
        """
        logger.info("Fetching redirects for %s pages ...", len(pages))
        result: dict[str, str] = {}

        for i in range(0, len(pages), batch_size):
            group = pages[i : i + batch_size]
            logger.info(
                "Fetching redirects %s – %s ...",
                i,
                min(i + batch_size, len(pages)),
            )
            params = {
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
                if not isinstance(page, dict):
                    continue
                target = page.get("title", "")
                for redirect in page.get("redirects") or []:
                    result[redirect["title"]] = target

        logger.info("Resolved %s redirects", len(result))
        return result


__all__ = ["WikiClient"]
