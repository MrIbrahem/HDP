"""
Reads the "Messaged to update application" section of
https://meta.wikimedia.org/wiki/Hardware_donation_program
and, for each linked subpage, prints:
  - last edit timestamp of that subpage
  - the global edit count of the user who created it

python -m src.main_app.dj.me1

"""

import logging
import os
import time
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


def build_wikitable(rows):
    """rows: list of (page_link, last_edit, user_link, editcount_str) tuples."""
    lines = ['{| class="wikitable sortable"', "! Page !! Last edited !! User !! Global edits"]
    for page_link, last_edit, user_link, editcount_str in rows:
        lines.append("|-")
        lines.append(f"| {page_link} || {last_edit} || {user_link} || {editcount_str}")
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


def get_last_edit_timestamp(site, page_title):
    logger.info(f"Fetching last edit timestamp of {page_title}...")
    params = {
        "prop": "revisions",
        "titles": page_title,
        "rvlimit": 1,
        "rvprop": "timestamp",
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
        return pages[0]["revisions"][0]["timestamp"]

    return None


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


def main() -> None:
    # Load credentials

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
        "Draft requests",
    ]
    full_text = ""
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

        lines = []

        data = []

        for sub in subpages:
            full_title = f"{BASE_PAGE}/{sub}"
            last_edit = get_last_edit_timestamp(site, full_title) or "unknown"
            user_name = sub.replace("(2nd Application)", "").split("/")[0].strip()
            username = users_redirects.get(user_name.lower()) or user_name  # get_page_creator(site, full_title)
            # first letter upper
            username = username[0].upper() + username[1:]
            data.append(
                {
                    "full_title": full_title,
                    "last_edit": last_edit,
                    "username": username,
                }
            )

        users = [x["username"] for x in data if x["username"]]

        editcounts = get_global_editcounts(site, users)

        rows = []
        for sub in data:
            full_title = sub["full_title"]
            last_edit = sub["last_edit"]
            username = sub["username"]
            editcount = editcounts.get(username) if username else None
            editcount_str = f"{editcount:,}" if isinstance(editcount, int) else "unknown"

            line = (
                f"*[[{full_title}]] (Last edited: {last_edit}, {username or 'unknown'} global edits: {editcount_str})"
            )
            lines.append(line)

            page_link = f"[[{full_title}]]"
            user_link = f"[[User:{username}]]" if username else "unknown"

            rows.append((page_link, last_edit, user_link, editcount_str))

        table = build_wikitable(rows)
        full_text_table += f"=== {section_title} ===\n\n{table}\n"

        output_text = "\n".join(lines) + "\n"
        full_text += f"=== {section_title} ===\n\n{output_text}\n"

    OUTPUT_FILE.write_text(full_text, encoding="utf-8")
    OUTPUT_FILE_TABLE.write_text(full_text_table, encoding="utf-8")

    logger.info(f"Saved to {OUTPUT_FILE}")
