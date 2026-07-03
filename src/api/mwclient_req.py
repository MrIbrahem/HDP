""" """

import logging
import time

import mwclient.errors
from mwclient.client import Site
from tqdm import tqdm

from src.utils import USER_AGENT

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
    except mwclient.errors.LoginError as err:
        logger.error(f"Login failed: {err}")
        return None
    except Exception as err:
        logger.exception(f"Failed to connect to meta.wikimedia.org: {err}")
        return None


def get_page_wikitext(site: Site, page_title: str) -> str:
    """Fetch the full raw wikitext of a page via the API.

    Args:
        site (Site): The Site object representing the MediaWiki site to query.
        page_title (str): The title of the page to fetch the wikitext from.

    Returns:
        str: The raw wikitext of the page as a string. Returns an empty
        string if an exception occurs during the API request.
    """
    logger.info(f"Fetching wikitext of {page_title}...")

    page = site.pages[page_title]

    try:
        return page.text()
    except Exception as e:
        logger.error("API request failed %s", str(e))
        return ""


def get_last_edit_timestamp(site: Site, page_title: str):
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


def get_page_creator(site: Site, page_title: str) -> None | str:
    """Retrieve the username of the user who created the page.

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


def get_global_editcounts(site: Site, users: list[str]) -> dict[str, int]:
    """Fetches the global edit counts for a list of users from a MediaWiki site.

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
    return {x["name"]: x.get("editcount", 0) for x in result}


def solve_pages_redirects(site: Site, pages: list[str]) -> dict[str, str]:
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
    logger.info(f"Fetching global edit count of {len(pages)}...")

    params = {
        # "action": "query",
        "format": "json",
        "prop": "redirects",
        "titles": "|".join(pages),
        "redirects": 1,
        "formatversion": "2",
        "rdprop": "title",
        "rdlimit": "max",
    }

    result = {}

    for i in range(0, len(pages), 30):
        logger.info(f"Fetching {i} - {i + 30}...")
        params["titles"] = "|".join(pages[i : i + 30])
        try:
            data = site.get("query", **params)
        except Exception as e:
            logger.error("API request failed %s", str(e))

        fetched_pages = data.get("query", {}).get("pages", [])
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

    # { "globaluserinfo": { "home": "enwiki", "id": 26378, "registration": "2008-07-24T01:18:05Z", "name": "Doc James", "editcount": 2066486 }
    return data.get("query", {}).get("globaluserinfo", {})


def get_home_wikis_and_registration(
    site: Site,
    users: list[str],
) -> dict[str, dict[str, str]]:
    """
    For each username:
      - fetch their CentralAuth home wiki via meta=globaluserinfo

    Returns home_wikis
    """
    home_wikis = {}

    for username in tqdm(users, desc="Fetching home wiki", unit="user"):
        info = get_global_userinfo(site, username)
        # info = { "home": "enwiki", "id": 26378, "registration": "2008-07-24T01:18:05Z", "name": "Doc James", "editcount": 2066486 }
        home_wikis[username] = {
            "home": info.get("home", ""),
            "registration": info.get("registration", ""),
        }
        time.sleep(0.1)

    return home_wikis


class MwclientApi:
    def __init__(self, site):
        self.site = site

    def get_page_wikitext(self, page_title: str) -> str:
        return get_page_wikitext(self.site, page_title)

    def get_last_edit_timestamp(self, page_title: str):
        return get_last_edit_timestamp(self.site, page_title)

    def get_page_creator(self, page_title: str) -> None | str:
        return get_page_creator(self.site, page_title)

    def get_global_editcounts(self, users: list[str]) -> dict[str, int]:
        return get_global_editcounts(self.site, users)

    def solve_pages_redirects(self, pages: list[str]) -> dict[str, str]:
        return solve_pages_redirects(self.site, pages)

    def get_global_userinfo(self, username: str) -> dict:
        return get_global_userinfo(self.site, username)

    def get_home_wikis_and_registration(
        self,
        users: list[str],
    ) -> dict[str, dict[str, str]]:
        return get_home_wikis_and_registration(self.site, users)


__all__ = [
    "connect_to_meta",
    "MwclientApi",
]
