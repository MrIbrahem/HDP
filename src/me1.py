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
from pathlib import Path
from typing import Optional

import mwclient
import mwclient.errors
from mwclient.client import Site

from .api.category import get_category_members_titles
from .wtp_parse import get_section_by_heading, extract_subpage_links

from .api.mwclient_req import (
    get_page_wikitext,
    get_last_edit_timestamp,
    get_global_editcounts,
)
BASE_PAGE = "Hardware donation program"
OUTPUT_FILE = Path(__file__).parent / "file.wiki"
OUTPUT_FILE_TABLE = Path(__file__).parent / "table.wiki"

logger = logging.getLogger(__name__)

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





def build_wikitable(rows):
    """rows: list of (page_link, last_edit, user_link, editcount_str) tuples."""
    lines = [
        '{| class="wikitable sortable"',
        "! Page",
        "! Last edited to application",
        "! User ",
        "! Global edits ",
    ]
    for row in rows:
        lines.append("|-")
        lines.append(f"| [[{row['full_title']}]] ")
        lines.append(f"| {row['last_edit']}")
        lines.append(f"| {row['user_link']}")
        lines.append(f"| {row['editcount_str']}")
    lines.append("|}")
    return "\n".join(lines)


# -----------------------------------------
# API
# -----------------------------------------

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
            last_edit = get_last_edit_timestamp(site, full_title) or "unknown"
            user_name = sub.replace("(2nd Application)", "").split("/")[0].strip()
            username = users_redirects.get(user_name.lower()) or user_name  # get_page_creator(sitesite,, full_title)
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

            user_link = f"[[User:{username}]]" if username else "unknown"
            row_data = {
                "full_title": full_title,
                "last_edit": last_edit,
                "user_link": user_link,
                "editcount_str": editcount_str,

            }
            rows.append(row_data)

        table = build_wikitable(rows)
        full_text_table += f"=== {section_title} ===\n\n{table}\n"

    OUTPUT_FILE_TABLE.write_text(full_text_table, encoding="utf-8")

    logger.info(f"Saved to {OUTPUT_FILE}")
