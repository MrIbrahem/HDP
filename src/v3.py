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

"""

import logging
import re
from pathlib import Path
from typing import Any

from .api.home_wiki_cached import get_home_wikis_cached
from .api.mwclient_req import (
    MwclientApi,
    connect_to_meta,
)
from .api.xtools_cached import get_recent_editcounts_cached, get_recent_editcounts_offline
from .load_subpages import get_subpages, get_subpages_for_section
from .utils import calculate_age, load_credentials, users_redirects
from .wtp_parse import update_wikitable_data

BASE_PAGE = "Hardware donation program"
OUTPUT_DIR = Path(__file__).parent.parent / "data"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE_TABLE = OUTPUT_DIR / "table.wiki"

# How many days back counts as "recent" for the recent-edits column.
RECENT_DAYS = 90

logger = logging.getLogger(__name__)


def extract_country(wikitext: str) -> str:
    """Extract the 'country your from' value from an application's wikitext.

    Handles patterns like:
        ; country your from:Rwanda
        ;country your from: Rwanda
        ; Country your from: Germany
    """
    pattern = r";\s*country\s+your\s+from\s*:\s*(.+)"
    match = re.search(pattern, wikitext, re.IGNORECASE)
    if match:
        country = match.group(1).strip()
        # Take only the first line (strip trailing wikitext artifacts)
        country = country.split("\n")[0].strip()
        # Remove trailing carriage return if present
        country = country.rstrip("\r").strip()
        return country
    return ""


def build_wikitable(rows) -> str:
    """rows: list of rows data."""
    lines = [
        '{| class="wikitable sortable"',
        "! Page",
        "! Last edited to application",
        "! User ",
        "! Country",
        "! Global edits",
        "! Edits in last 3 months",
        "! Age of account",
        "! Home Wiki",
        "! Approved",
    ]
    for _, row in rows.items():
        lines.append("|-")
        lines.append(f"| {row['page_link']}")
        lines.append(f"| {row['last_update']}")
        lines.append(f"| {row['user_link']}")
        lines.append(f"| {row.get('country', '')}")
        lines.append(f"| {row['editcount_str']}")
        lines.append(f"| {row['recent_editcount_str']}")
        lines.append(f"| {row['age']}")
        lines.append(f"| {row['home_wiki']}")
        lines.append("| ")

    lines.append("|}")

    return "\n".join(lines)


def solve_users_redirects(api: MwclientApi, data) -> list[dict[str, str]]:
    users = []
    for x in data:
        if not x["username"]:
            continue
        user_str = f"User:{x['username']}"
        users.append(user_str)

    users_redirects_api = api.solve_pages_redirects(users)

    new_data = []
    for x in data[:]:
        username = x["username"]
        user_str = f"User:{username}"
        if users_redirects_api.get(user_str):
            x["username"] = users_redirects_api[user_str].removeprefix("User:")

            if user_str == "User:Johnjoy12":
                logger.info(f"Johnjoy12 is a redirect to {x["username"]}")
                logger.info(x)

        new_data.append(x)

    return new_data


def load_rows(
    api: MwclientApi,
    subpages: list[str],
    unknown_placeholder: str = "unknown",
    load_recent_editcounts: bool = True,
) -> dict[str, Any]:

    data = []

    for sub in subpages:
        sub = sub.replace("_", " ")
        full_title = f"{BASE_PAGE}/{sub}"
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

    recent_editcounts = {}

    if not load_recent_editcounts:
        recent_editcounts = get_recent_editcounts_offline(users)
        logger.info(f"Loaded {len(recent_editcounts)} recent editcounts for {len(users)} users")
    else:
        recent_editcounts = get_recent_editcounts_cached(users)
        logger.info(f"Loaded {len(recent_editcounts)} recent editcounts for {len(users)} users")

    home_wikis = get_home_wikis_cached(api, users)
    logger.info(f"Loaded {len(home_wikis)} home wikis and registration for {len(users)} users")

    rows = {}
    for sub in new_data:
        editcount_str = unknown_placeholder
        age = ""
        user_link = unknown_placeholder
        home_wiki = unknown_placeholder
        recent_editcount_str = unknown_placeholder

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
            if isinstance(editcount, int):
                editcount_str = f"{editcount:,}"

            recent_editcount = recent_editcounts.get(username)
            if recent_editcount is not None:
                recent_editcount_str = f"{recent_editcount:,}"
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
            "home_wiki": home_wiki,
            "recent_editcount_str": recent_editcount_str,
        }

        rows[sub["full_title"]] = row_data

    return rows


def main(
    section_headings: list[str],
    output_file_name: str = "table.wiki",
    unknown_placeholder: str = "unknown",
    load_recent_editcounts: bool = True,
) -> None:
    # Load credentials
    username, password = load_credentials()
    if not username or not password:
        logger.error("Failed to load credentials from .env file")
        logger.error("Please create a .env file with WIKIPEDIA_BOT_USERNAME and WIKIPEDIA_BOT_PASSWORD")
        return

    # Connect to Meta Wiki
    site = connect_to_meta(username, password)
    if not site:
        logger.error("Failed to connect to Meta Wiki")
        return

    api = MwclientApi(site)

    full_wikitext = api.get_page_wikitext(BASE_PAGE)

    full_text_table = ""

    for section_title in section_headings:

        subpages = get_subpages_for_section(site, full_wikitext, BASE_PAGE, section_title=section_title)

        rows = load_rows(
            api,
            subpages,
            unknown_placeholder=unknown_placeholder,
            load_recent_editcounts=load_recent_editcounts,
        )
        table = build_wikitable(rows)

        full_text_table += f"=== {section_title} ===\n\n{table}\n"

    file = OUTPUT_DIR / output_file_name

    file.write_text(full_text_table, encoding="utf-8")

    logger.info(f"Saved to {file}")


def update(
    page_title: str,
    output_file_name: str,
    unknown_placeholder: str = "unknown",
    load_recent_editcounts: bool = True,
    section_names: list[str] | None = None,
) -> None:
    """Updates and saves the wikitable data for a specified Wikipedia page or its subpages.

    This function authenticates with Meta Wiki using credentials loaded from a .env file,
    retrieves the wikitext of the specified page, and determines the relevant subpages
    either by specific section/category names or by default parsing. It then loads the
    tabular data from these subpages, updates the wikitable within the page's wikitext,
    and saves the resulting text to a local output file.

    Args:
        page_title (str): The title of the Wikipedia page to update.
        output_file_name (str): The name of the output file where the updated wikitext will be saved.
        unknown_placeholder (str, optional): The placeholder string to use for unknown values.
            Defaults to "unknown".
        load_recent_editcounts (bool, optional): Whether to load recent edit counts for the rows.
            Defaults to True.
        section_names (list[str] | None, optional): Section headings or "Category:..." names
            to collect subpages from. If None, subpages are determined by default parsing.
            Defaults to None.
    Returns:
        None
    """
    username, password = load_credentials()
    if not username or not password:
        logger.error("Failed to load credentials from .env file")
        logger.error("Please create a .env file with WIKIPEDIA_BOT_USERNAME and WIKIPEDIA_BOT_PASSWORD")
        return

    # Load credentials from .env file
    site = connect_to_meta(username, password)
    if not site:
        logger.error("Failed to connect to Meta Wiki")
        return

    api = MwclientApi(site)

    full_wikitext = api.get_page_wikitext(page_title)
    subpages: list[str] = []

    if section_names:
        seen: set[str] = set()
        for name in section_names:
            for sp in get_subpages_for_section(site, full_wikitext, BASE_PAGE, section_title=name):
                if sp not in seen:
                    seen.add(sp)
                    subpages.append(sp)

    # Fallback to default subpage parsing
    if not subpages:
        subpages = get_subpages(full_wikitext, BASE_PAGE)

    logger.info(f"Total subpages collected: {len(subpages)}")

    rows = load_rows(
        api,
        subpages,
        unknown_placeholder=unknown_placeholder,
        load_recent_editcounts=load_recent_editcounts,
    )

    table_headers_to_row_key = {
        "Page": "page_link",
        "Last edited to application": "last_update",
        "User": "user_link",
        "Country": "country",
        "Global edits": "editcount_str",
        "Edits in last 3 months": "recent_editcount_str",
        "Age of account": "age",
        "Home Wiki": "home_wiki",
    }

    full_text_table = update_wikitable_data(
        rows,
        full_wikitext,
        table_headers_to_row_key,
        replace_values=False,
    )

    file = OUTPUT_DIR / output_file_name

    file.write_text(full_text_table, encoding="utf-8")

    logger.info(f"Saved to {file}")


__all__ = [
    "main",
    "update",
]
