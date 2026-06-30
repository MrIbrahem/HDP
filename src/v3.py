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
import os
from pathlib import Path
from typing import Optional

from .api.category import get_category_members_titles
from .api.mwclient_req import (
    connect_to_meta,
    get_global_editcounts,
    get_home_wikis,
    get_page_wikitext,
)
from .api.xtools import get_recent_editcounts
from .wtp_parse import extract_subpage_links, get_section_by_heading

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
        recent_editcounts = get_recent_editcounts(users)
        home_wikis = get_home_wikis(site, users)

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
                "editcount_str": editcount_str,
                "home_wiki": home_wiki,
                "recent_editcount_str": recent_editcount_str,
            }

            rows.append(row_data)

        table = build_wikitable(rows)
        full_text_table += f"=== {section_title} ===\n\n{table}\n"

    OUTPUT_FILE_TABLE.write_text(full_text_table, encoding="utf-8")

    logger.info(f"Saved to {OUTPUT_FILE}")
