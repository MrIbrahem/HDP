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
from pathlib import Path
from typing import Any

from .api.mwclient_req import (
    MwclientApi,
    connect_to_meta,
)

# from .api.xtools import get_recent_editcounts
from .api.xtools_cached import get_recent_editcounts_cached
from .load_subpages import get_subpages, get_subpages_for_section
from .utils import calculate_age, load_credentials, users_redirects
from .wtp_parse import update_wikitable_data

BASE_PAGE = "Hardware donation program"
OUTPUT_DIR = Path(__file__).parent
OUTPUT_FILE_TABLE = OUTPUT_DIR / "table.wiki"

# How many days back counts as "recent" for the recent-edits column.
RECENT_DAYS = 90

logger = logging.getLogger(__name__)


def build_wikitable(rows) -> str:
    """rows: list of rows data."""
    lines = [
        '{| class="wikitable sortable"',
        "! Page",
        "! Last edited to application",
        "! User ",
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
        lines.append(f"| {row['editcount_str']}")
        lines.append(f"| {row['recent_editcount_str']}")
        lines.append(f"| {row['age']}")
        lines.append(f"| {row['home_wiki']}")
        lines.append("| ")

    lines.append("|}")

    return "\n".join(lines)


def load_rows(
    api: MwclientApi,
    subpages: list[str],
    unknown_placeholder: str = "unknown",
    load_recent_editcounts: bool = True,
) -> dict[str, Any]:

    data = []

    for sub in subpages:
        full_title = f"{BASE_PAGE}/{sub}"
        user_name = sub.replace("(2nd Application)", "").split("/")[0].strip()
        username = users_redirects.get(user_name.lower()) or user_name  # api.get_page_creator(full_title)
        # first letter upper (guard against empty username)
        if username:
            username = username[0].upper() + username[1:]
        data.append(
            {
                "full_title": full_title,
                "username": username,
            }
        )

    users = [x["username"] for x in data if x["username"]]

    editcounts = api.get_global_editcounts(users)
    logger.info(f"Loaded {len(editcounts)} editcounts for {len(users)} users")

    recent_editcounts = {}
    if load_recent_editcounts:
        # recent_editcounts = get_recent_editcounts(users)
        recent_editcounts = get_recent_editcounts_cached(users)
        logger.info(f"Loaded {len(recent_editcounts)} recent editcounts for {len(users)} users")

    home_wikis = api.get_home_wikis_and_registration(users)
    logger.info(f"Loaded {len(home_wikis)} home wikis and registration for {len(users)} users")

    rows = {}
    for sub in data:
        editcount_str = unknown_placeholder
        age = ""
        user_link = unknown_placeholder
        home_wiki = unknown_placeholder
        recent_editcount_str = unknown_placeholder

        username = sub["username"]
        if username:
            user_link = f"[[User:{username}]]"

            home_data = home_wikis.get(username, {})
            if not home_data:
                logger.warning(f"Home data not found for {username}")

            home_wiki = home_data.get("home", unknown_placeholder)
            registration = home_data.get("registration", "")
            if registration:
                age = calculate_age(registration)

            logger.debug(f"User: {username}, {age=}, {home_wiki=}")

            editcount = editcounts.get(username)
            if isinstance(editcount, int):
                editcount_str = f"{editcount:,}"

            recent_editcount = recent_editcounts.get(username)
            if recent_editcount is not None:
                recent_editcount_str = f"{recent_editcount:,}"
        else:
            logger.warning(f"Username not found for {sub['full_title']}")

        row_data = {
            "age": age,
            "page_link": f"[[{sub['full_title']}]]",
            "last_update": f"{{{{#time:H:i, j F Y|{{{{REVISIONTIMESTAMP:{sub['full_title']}}}}}}}}}",
            "full_title": sub["full_title"],
            "user_link": user_link,
            "editcount_str": editcount_str,
            "home_wiki": home_wiki,
            "recent_editcount_str": recent_editcount_str,
        }

        rows[sub["full_title"]] = row_data

    return rows


def main(section_headings: list[str]) -> None:
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

    api = MwclientApi(site)

    full_wikitext = api.get_page_wikitext(BASE_PAGE)

    full_text_table = ""

    for section_title in section_headings:

        subpages = get_subpages_for_section(site, full_wikitext, BASE_PAGE, section_title=section_title)

        rows = load_rows(api, subpages)
        table = build_wikitable(rows)

        full_text_table += f"=== {section_title} ===\n\n{table}\n"

    OUTPUT_FILE_TABLE.write_text(full_text_table, encoding="utf-8")

    logger.info(f"Saved to {OUTPUT_FILE_TABLE}")


def update(
    page_title: str,
    output_file_name: str,
    unknown_placeholder: str = "unknown",
    load_recent_editcounts: bool = True,
) -> None:
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

    api = MwclientApi(site)

    full_wikitext = api.get_page_wikitext(page_title)
    subpages = get_subpages(full_wikitext, BASE_PAGE)

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
