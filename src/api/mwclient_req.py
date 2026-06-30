""" """

import logging
import time

import mwclient.errors
from mwclient.client import Site
from tqdm import tqdm

# User-Agent header (required by Wikimedia)
USER_AGENT = "OWID-Commons-Categorizer/1.0 (https://github.com/MrIbrahem/OWID-categories; contact via GitHub)"

logger = logging.getLogger(__name__)


def connect_to_meta(username: str, password: str) -> Site | None:
    """
    Connect to Wikimedia Commons using mwclient.

    Args:
        username: Bot username
        password: Bot password

    Returns:
        Connected Site object or None on failure
    """
    try:
        logger.info("Connecting to meta.wikimedia.org...")
        site = Site("meta.wikimedia.org", clients_useragent=USER_AGENT)

        logger.info(f"Logging in as {username}...")
        site.login(username, password)

        logger.info("Successfully connected and logged in")
        return site
    except mwclient.errors.LoginError as e:
        logger.error(f"Login failed: {e}")
        return None
    except Exception as e:
        logger.exception(f"Failed to connect to meta.wikimedia.org: {e}")
        return None


def get_page_wikitext(site: Site, page_title):
    """Fetch the full raw wikitext of a page via the API."""
    logger.info(f"Fetching wikitext of {page_title}...")
    params = {
        "prop": "revisions",
        "titles": page_title,
        "rvslots": "main",
        "rvprop": "content",
        "formatversion": 2,
        "format": "json",
    }
    data = {}

    try:
        data = site.get("query", **params)
    except Exception as e:
        logger.error("API request failed %s", str(e))

    pages = data.get("query", {}).get("pages", [])

    return pages[0]["revisions"][0]["slots"]["main"]["content"]


def get_last_edit_timestamp(site: Site, page_title):
    logger.info(f"Fetching last edit timestamp of {page_title}...")
    params = {
        "prop": "revisions",
        "titles": page_title,
        "rvlimit": 1,
        "rvprop": "timestamp",
        "formatversion": 2,
        "format": "json",
    }
    data = {}
    try:
        data = site.get("query", **params)
    except Exception as e:
        logger.error("API request failed %s", str(e))
        return None

    pages = data.get("query", {}).get("pages", [])
    if pages and "revisions" in pages[0]:
        return pages[0]["revisions"][0]["timestamp"]

    return None


def get_page_creator(site: Site, page_title):
    """Username of the oldest revision (i.e. who created the page)."""
    logger.info(f"Fetching page creator of {page_title}...")
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
        data = site.get("query", **params)
    except Exception as e:
        logger.error("API request failed %s", str(e))
        return None

    pages = data.get("query", {}).get("pages", [])
    if pages and "revisions" in pages[0]:
        return pages[0]["revisions"][0]["user"]

    return None


def get_global_editcounts(site: Site, users) -> dict[str, int]:
    logger.info(f"Fetching global edit count of {len(users)}...")

    params = {
        "list": "globalusers",
        "gusprop": "editcount|registration",
        "gususers": "|".join(users),
        "formatversion": 2,
        "format": "json",
    }

    data = {}

    try:
        data = site.get("query", **params)
    except Exception as e:
        logger.error("API request failed %s", str(e))

    result = data.get("query", {}).get("globalusers", [])
    # [ { "centralid": 4327653, "name": "Mr. Ibrahem", "editcount": 2017792 }, ... ]

    logger.info(f"len of data: {len(result)}")
    return {x["name"]: x["editcount"] for x in result if x.get("editcount")}


def get_global_userinfo(site: Site, username: str) -> dict:
    """
    Fetch CentralAuth global user info for a single user from meta.wikimedia.org.

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
    data = {}
    try:
        data = site.get("query", **params)
    except Exception as e:
        logger.error("API request failed %s", str(e))
        return {}

    return data.get("query", {}).get("globaluserinfo", {})


def get_home_wikis(
    site: Site,
    users: list[str],
) -> dict[str, str]:
    """
    For each username:
      - fetch their CentralAuth home wiki via meta=globaluserinfo

    Returns home_wikis
    """
    home_wikis: dict[str, str] = {}

    for username in tqdm(users, desc="Fetching home wiki", unit="user"):
        # info = get_global_userinfo(username)
        info = get_global_userinfo(site, username)
        home_wikis[username] = (info.get("home") or "unknown") if info else "unknown"
        time.sleep(0.1)

    return home_wikis


class MwclientApi:
    def __init__(self, site):
        self.site = site

    def get_page_wikitext(self, page_title):
        return get_page_wikitext(self.site, page_title)

    def get_last_edit_timestamp(self, page_title):
        return get_last_edit_timestamp(self.site, page_title)

    def get_page_creator(self, page_title):
        return get_page_creator(self.site, page_title)

    def get_global_editcounts(self, users) -> dict[str, int]:
        return get_global_editcounts(self.site, users)

    def get_global_userinfo(self, username: str) -> dict:
        return get_global_userinfo(self.site, username)

    def get_home_wikis(
        self,
        users: list[str],
    ) -> dict[str, str]:
        return get_home_wikis(self.site, users)


__all__ = [
    "connect_to_meta",
    "MwclientApi",
]
