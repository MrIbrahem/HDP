"""
Reads the "Current donation requests" section of
https://meta.wikimedia.org/wiki/Hardware_donation_program#Current_donation_requests
(covering its "Open requests", "Draft requests", and
"Approved requests not yet delivered" subsections) and, for each linked
subpage, prints/tabulates:
  - last edit timestamp of that subpage
  - the user who created it, and their home wiki
  - their lifetime global edit count
  - their global edit count over the last RECENT_DAYS days (default 90)

Run this every few months (e.g. via cron) to keep the table current.

python -m src.main_app.dj.me1

"""

import logging
import os
import time
from datetime import datetime, timedelta, timezone, UTC
from pathlib import Path
from typing import Optional

import mwclient
import mwclient.errors
import requests
import wikitextparser as wtp
from mwclient.client import Site
from tqdm import tqdm

API_URL = "https://meta.wikimedia.org/w/api.php"
BASE_PAGE = "Hardware donation program"
OUTPUT_FILE = Path(__file__).parent / "file.wiki"
OUTPUT_FILE_TABLE = Path(__file__).parent / "table.wiki"

# How many days back counts as "recent" for the recent-edits column.
RECENT_DAYS = 90

logger = logging.getLogger(__name__)

# User-Agent header (required by Wikimedia)
USER_AGENT = "OWID-Commons-Categorizer/1.0 (https://github.com/MrIbrahem/OWID-categories; contact via GitHub)"

# -----------------------------------------
# wiki text parsers
# -----------------------------------------
users_redirects = {
    "vinoda mamatharai": "Vinoda mamatharai",
    "cbrescia": "Felino Volador",
    "abubakar a gwanki": "Gwanki",
    "sardeeq": "Sardeeq",
    "muralikrishna m": "Muralikrishna m",
    "brazal.dang": "Ballardmaize",
    "babulbaishya": "BabulB",
    "micheal kaluba": "MichealKal",
    "mp1999": "TypeInfo",
    "premchand murmu thakur": "Nacharhopon",
    "учитель": "Валентина Кодола",
    "bhupendra shrestha": "श्रेष्ठ भूपेन्द्र",
}


# Configuration
API_ENDPOINT = "https://commons.wikimedia.org/w/api.php"


def get_category_count(category_name: str) -> int:
    # Ensure the title has the proper prefix
    if not category_name.startswith("Category:"):
        category_name = f"Category:{category_name}"

    url = API_ENDPOINT
    params = {
        "action": "query",
        "format": "json",
        "prop": "categoryinfo",
        "titles": category_name,
        "utf8": 1,
        "formatversion": "2",
    }

    # Always include a descriptive User-Agent header per Wikipedia API guidelines
    headers = {"User-Agent": USER_AGENT}

    try:
        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as e:
        logger.error(f"Failed to fetch category info for {category_name}: {e}")
        return 0
    # { "batchcomplete": true, "query": { "pages": [ { "pageid": 718741, "ns": 14, "title": "Category:Yemen", "categoryinfo": { "size": 19, "pages": 3, "files": 0, "subcats": 16, "hidden": false } } ] } }
    # Extract the page data dynamically since the page ID string changes
    pages = data.get("query", {}).get("pages", [{}])
    if not pages:
        return 0

    info = pages[0].get("categoryinfo", {})
    # {'size': 354, 'pages': 1, 'files': 309, 'subcats': 44}
    size = info.get("size") or 0
    return size


def get_category_members_titles(
    site: Site,
    category_name: str,
    namespace: int | None = None,
    total_pages: int | None = None,
    max_items: int | None = None,
) -> list[str]:
    """
    Fetch all file titles from the OWID category using MediaWiki API with pagination.

    Returns:
        List of file titles (strings).
    """
    delay = 0.1  # seconds
    max_delay = 8.0

    total_pages = max_items or total_pages or get_category_count(category_name)
    logger.info(f"Starting to fetch files from {category_name}, total members: {total_pages}")

    params = {
        # "action": "query",
        "format": "json",
        "list": "categorymembers",
        "cmtitle": category_name,
        # "cmtype": "file",
        "cmlimit": "max",
    }

    if namespace is not None:
        if namespace == 14:
            params["cmtype"] = "subcat"
        elif namespace == 6:
            params["cmtype"] = "file"
        else:
            params["cmnamespace"] = str(namespace)

    all_files = []
    first_request = True
    cmcontinue = None

    # Initialize tqdm with the total expected items
    with tqdm(total=total_pages, desc="Fetching members", unit="item") as pbar:
        while first_request or cmcontinue is not None:
            first_request = False
            if max_items and len(all_files) >= max_items:
                break

            if cmcontinue:
                params["cmcontinue"] = cmcontinue

            try:
                data = site.get("query", **params)
                members = data.get("query", {}).get("categorymembers", [])

                # Extract titles
                new_titles = [x.get("title", "") for x in members]
                all_files.extend(new_titles)

                # Update the progress bar by the number of items fetched in this batch
                pbar.update(len(new_titles))

                logger.debug(f"Fetched category members: {len(members)} page, (total: {len(all_files)}/{total_pages})")

                if "continue" in data:
                    cmcontinue = data["continue"].get("cmcontinue")
                    time.sleep(delay)
                else:
                    break

            except mwclient.errors.APIError as e:
                if e.code == "invalidcategory":
                    logger.warning(f"Invalid category: {category_name}")
                    break

            except Exception as e:
                logger.error("API request failed %s", str(e))
                if delay >= max_delay:
                    break

                time.sleep(delay)
                delay = min(delay * 2, max_delay)
                continue

    logger.info(f"Finished fetching {len(all_files)} pages.")
    return all_files


def load_credentials() -> tuple[Optional[str], Optional[str]]:
    """
    Load credentials from .env file.

    Returns:
        Tuple of (username, password) or (None, None) if not found
    """
    username = os.getenv("WIKIPEDIA_BOT_USERNAME")
    password = os.getenv("WIKIPEDIA_BOT_PASSWORD")

    if not username or not password:
        logger.error("WIKIPEDIA_BOT_USERNAME and/or WIKIPEDIA_BOT_PASSWORD not found in .env file")
        return None, None

    return username, password


def get_section_by_heading(wikitext, heading):
    """Use wikitextparser to find a section by its heading text."""
    parsed = wtp.parse(wikitext)
    for section in parsed.get_sections(include_subsections=True):
        if section.title and section.title.strip() == heading:
            return section
    raise ValueError(f"Section '{heading}' not found")


def extract_subpage_links(section, base_page):
    """Use wikitextparser's wikilinks to pull out 'Base/Sub' page names."""
    prefix = base_page + "/"
    seen = []
    for link in section.wikilinks:
        title = link.title.strip()
        if title.startswith(prefix):
            name = title[len(prefix) :]
            if name not in seen:
                seen.append(name)
    return seen


def build_wikitable(rows) -> str:
    """rows: list of rows data."""
    lines = [
        '{| class="wikitable sortable"',
        "! Page ",
        "! Last edited to application ",
        "! User ",
        "! Global edits",
        "! Edits in last 3 months",
        "! Age of account",
        "! Home Wiki",
        "! Approved",
    ]
    for row in rows:
        lines.append("|-")
        lines.append(f"| [[{row['full_title']}]] ")
        lines.append(f"| {{{{#time:H:i, j F Y|{{{{REVISIONTIMESTAMP:{row['full_title']}}}}}}}}}")
        lines.append(f"| {row['user_link']}")
        lines.append(f"| {row['editcount_str']}")
        lines.append(f"| {row['recent_editcount_str']}")
        lines.append("| ")
        lines.append(f"| {row['home_wiki']}")
        lines.append("| ")

    lines.append("|}")

    return "\n".join(lines)


# -----------------------------------------
# API
# -----------------------------------------


def connect_to_meta(username: str, password: str) -> Optional[Site]:
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


def get_page_wikitext(site, page_title):
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
    try:
        data = site.get("query", **params)
    except Exception as e:
        logger.error("API request failed %s", str(e))

    pages = data.get("query", {}).get("pages", [])

    return pages[0]["revisions"][0]["slots"]["main"]["content"]

def get_page_creator(site, page_title):
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


def get_global_editcounts(site, users) -> dict[str, int]:
    logger.info(f"Fetching global edit count of {len(users)}...")

    params = {
        "list": "globalusers",
        "gusprop": "editcount",
        "gususers": "|".join(users),
        "formatversion": 2,
        "format": "json",
    }

    try:
        data = site.get("query", **params)
    except Exception as e:
        logger.error("API request failed %s", str(e))
        data = {}

    result = data.get("query", {}).get("globalusers", [])
    # [ { "centralid": 4327653, "name": "Mr. Ibrahem", "editcount": 2017792 }, ... ]

    logger.info(f"len of data: {len(result)}")
    return {x["name"]: x["editcount"] for x in result if x.get("editcount")}


def get_global_userinfo(username: str) -> dict:
    """
    Fetch CentralAuth global user info for a single user from meta.wikimedia.org.

    Returns the raw 'globaluserinfo' dict, which includes:
      - 'home': dbname of the user's home wiki (e.g. "enwiki"), may be empty

    Note: meta=globaluserinfo only accepts a single username at a time
    (no batching), so this is called once per user.
    """
    params = {
        "action": "query",
        "meta": "globaluserinfo",
        "guiuser": username,
        "formatversion": "2",
        "format": "json",
    }
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(API_URL, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as e:
        logger.error(f"Failed to fetch globaluserinfo for {username}: {e}")
        return {}

    return data.get("query", {}).get("globaluserinfo", {})


XTOOLS_GLOBALCONTRIBS_URL = "https://xtools.wmcloud.org/api/user/globalcontribs"


def get_recent_editcount(username: str, days: int = RECENT_DAYS) -> Optional[int]:
    """
    Count a user's edits across all Wikimedia projects in the last `days`
    days, using XTools' Global Contributions API
    (GET /api/user/globalcontribs/{username}/{namespace}/{start}/{end}/{offset}),
    which paginates via a 'continue' timestamp offset.

    Returns None if the lookup fails (e.g. XTools returns an error, or the
    user has an exceptionally high edit count and the endpoint declines to
    serve it without authentication, per XTools' own rate-limiting rules).
    """
    today = datetime.now(UTC).date()
    start = today - timedelta(days=days)
    base_url = f"{XTOOLS_GLOBALCONTRIBS_URL}/{username}/all/{start.isoformat()}/{today.isoformat()}"

    headers = {"User-Agent": USER_AGENT}
    total = 0
    offset = None
    delay = 0.5
    max_delay = 8.0
    max_pages = 50  # safety cap against runaway pagination

    for _ in range(max_pages):
        params = {"offset": offset} if offset else {}
        try:
            response = requests.get(base_url, params=params, headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as e:
            logger.error(f"XTools globalcontribs request failed for {username}: {e}")
            if total > 0:
                # We got partial data before the failure; treat as a lower bound.
                return total
            if delay >= max_delay:
                return None
            time.sleep(delay)
            delay = min(delay * 2, max_delay)
            continue

        if "error" in data or "status" in data:
            # XTools error responses follow RFC 7807 (status/title/details).
            logger.warning(f"XTools globalcontribs error for {username}: {data}")
            return None

        contribs = data.get("globalcontribs", [])
        total += len(contribs)

        offset = data.get("continue")
        if not offset:
            break

        time.sleep(0.3)
    else:
        logger.warning(f"Hit max_pages cap fetching globalcontribs for {username}")

    return total


def get_home_wikis_and_recent_editcounts(
    users: list[str],
    recent_days: int = RECENT_DAYS,
) -> tuple[dict[str, str], dict[str, int]]:
    """
    For each username:
      - fetch their CentralAuth home wiki via meta=globaluserinfo
      - fetch their last-`recent_days`-day global edit count via XTools'
        Global Contributions API

    Returns (home_wikis, recent_editcounts), both keyed by username.
    """
    home_wikis: dict[str, str] = {}
    recent_editcounts: dict[str, int] = {}

    for username in tqdm(users, desc="Fetching home wiki / recent edits", unit="user"):
        info = get_global_userinfo(username)
        home_wikis[username] = (info.get("home") or "unknown") if info else "unknown"
        time.sleep(0.1)

        recent_count = get_recent_editcount(username, days=recent_days)
        if recent_count is not None:
            recent_editcounts[username] = recent_count
        time.sleep(0.3)

    return home_wikis, recent_editcounts


def main() -> None:
    # Load credentials
    username, password = load_credentials()
    if not username or not password:
        logger.error("Failed to load credentials from .env file")
        logger.error("Please create a .env file with WIKIPEDIA_BOT_USERNAME and WIKIPEDIA_BOT_PASSWORD")
        return

    # Connect to Commons
    site = connect_to_meta(username, password)
    if not site:
        logger.error("Failed to connect to Wikimedia Commons")
        return

    full_wikitext = get_page_wikitext(site, BASE_PAGE)
    full_wikitext = full_wikitext.replace("_", " ")

    SECTION_HEADINGS = [
        # "Updated as of May 1st 2026",
        # "Messaged to update application",
        "Current donation requests",
        "Draft requests",
        "Approved requests not yet delivered",
    ]
    full_text_table = ""

    for section_title in SECTION_HEADINGS:
        section = get_section_by_heading(full_wikitext, section_title)
        subpages = extract_subpage_links(section, BASE_PAGE)
        if section_title == "Draft requests":
            members = get_category_members_titles(
                site,
                "Category:Hardware donation program drafts",
                namespace=0,
            )
            subpages = [x.replace("Hardware donation program/", "") for x in members]

        data = []

        for sub in subpages:
            full_title = f"{BASE_PAGE}/{sub}"
            user_name = sub.replace("(2nd Application)", "").split("/")[0].strip()
            username = users_redirects.get(user_name.lower()) or user_name  # get_page_creator(site, full_title)
            # first letter upper
            username = username[0].upper() + username[1:]
            data.append(
                {
                    "full_title": full_title,
                    "username": username,
                }
            )

        users = [x["username"] for x in data if x["username"]]

        editcounts = get_global_editcounts(site, users)
        home_wikis, recent_editcounts = get_home_wikis_and_recent_editcounts(users)

        rows = []
        for sub in data:
            full_title = sub["full_title"]
            username = sub["username"]
            editcount = editcounts.get(username) if username else None
            editcount_str = f"{editcount:,}" if isinstance(editcount, int) else "unknown"
            home_wiki = home_wikis.get(username, "unknown") if username else "unknown"
            recent_editcount = recent_editcounts.get(username) if username else None
            recent_editcount_str = f"{recent_editcount:,}" if isinstance(recent_editcount, int) else "unknown"

            user_link = f"[[User:{username}]]" if username else "unknown"

            row_data = {
                "full_title": full_title,
                "user_link": user_link,
                "home_wiki": home_wiki,
                "editcount_str": editcount_str,
                "recent_editcount_str": recent_editcount_str,
            }
            rows.append(row_data)

        table = build_wikitable(rows)
        full_text_table += f"=== {section_title} ===\n\n{table}\n"

    OUTPUT_FILE_TABLE.write_text(full_text_table, encoding="utf-8")

    logger.info(f"Saved to {OUTPUT_FILE}")
