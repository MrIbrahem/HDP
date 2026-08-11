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

from ..api.mwclient_req import (
    MwclientApi,
    connect_to_meta,
)
from ..load_subpages import get_subpages_for_section
from ..utils import load_credentials
from . import build_wikitable, load_rows

BASE_PAGE = "Hardware donation program"
OUTPUT_DIR = Path(__file__).parent.parent / "data"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)


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
            base_page=BASE_PAGE,
        )
        table = build_wikitable(rows)

        full_text_table += f"=== {section_title} ===\n\n{table}\n"

    file = OUTPUT_DIR / output_file_name

    file.write_text(full_text_table, encoding="utf-8")

    logger.info(f"Saved to {file}")


__all__ = [
    "main",
]
