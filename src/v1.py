"""
Reads the "Messaged to update application" section of
https://meta.wikimedia.org/wiki/Hardware_donation_program
and, for each linked subpage, prints:
  - last edit timestamp of that subpage
  - the global edit count of the user who created it

"""

import logging
from pathlib import Path

from .api.mwclient_req import (
    MwclientApi,
    connect_to_meta,
)
from .load_subpages import get_subpages_for_section
from .utils import load_credentials, users_redirects

BASE_PAGE = "Hardware donation program"
OUTPUT_FILE_TABLE = Path(__file__).parent / "table.wiki"

logger = logging.getLogger(__name__)


def build_wikitable(rows) -> str:
    """rows: list of rows data."""
    lines = [
        '{| class="wikitable sortable"',
        "! Page",
        "! Last edited to application",
        "! User ",
        "! Global edits",
    ]
    for row in rows:
        lines.append("|-")
        lines.append(f"| [[{row['full_title']}]] ")
        lines.append(f"| {{{{#time:H:i, j F Y|{{{{REVISIONTIMESTAMP:{row['full_title']}}}}}}}}}")
        lines.append(f"| {row['user_link']}")
        lines.append(f"| {row['editcount_str']}")

    lines.append("|}")

    return "\n".join(lines)


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
        subpages = get_subpages_for_section(site, full_wikitext, BASE_PAGE, section_title)

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

        rows = []
        for sub in data:
            username = sub["username"]
            editcount = editcounts.get(username) if username else None
            editcount_str = f"{editcount:,}" if isinstance(editcount, int) else "unknown"

            user_link = f"[[User:{username}]]" if username else "unknown"

            row_data = {
                "full_title": sub["full_title"],
                "user_link": user_link,
                "editcount_str": editcount_str,
            }

            rows.append(row_data)

        table = build_wikitable(rows)
        full_text_table += f"=== {section_title} ===\n\n{table}\n"

    OUTPUT_FILE_TABLE.write_text(full_text_table, encoding="utf-8")

    logger.info(f"Saved to {OUTPUT_FILE_TABLE}")
