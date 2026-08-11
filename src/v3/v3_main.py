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

from ..api.mwclient_req import (
    MwclientApi,
    connect_to_meta,
)
from ..load_subpages import get_subpages_for_section
from ..utils import load_credentials
from .tables_builder import build_wikitable
from .worker import load_rows

BASE_PAGE = "Hardware donation program"

logger = logging.getLogger(__name__)


def get_api() -> None | MwclientApi:
    username, password = load_credentials()
    if not username or not password:
        logger.error("Failed to load credentials from .env file")
        logger.error("Please create a .env file with WIKIPEDIA_BOT_USERNAME and WIKIPEDIA_BOT_PASSWORD")
        return None

    # Connect to Meta Wiki
    site = connect_to_meta(username, password)
    if not site:
        logger.error("Failed to connect to Meta Wiki")
        return None

    api = MwclientApi(site)
    return api


def main(
    page_title: str,
    section_names: list[str],
    unknown_placeholder: str = "unknown",
    load_recent_editcounts: bool = True,
    load_last_edits: bool = False,
) -> str:
    """ """
    api = get_api()

    if not api:
        logger.error("Failed to connect to Meta Wiki")
        return ""

    full_wikitext = api.get_page_wikitext(page_title)

    new_page_text = ""

    if section_names:
        for section_title in section_names:
            subpages = get_subpages_for_section(api.site, full_wikitext, BASE_PAGE, section_title=section_title)

            logger.info(f"Total subpages collected: {len(subpages)}")

            rows = load_rows(
                api,
                subpages,
                unknown_placeholder=unknown_placeholder,
                load_recent_editcounts=load_recent_editcounts,
                load_last_edits=load_last_edits,
                base_page=BASE_PAGE,
            )
            table = build_wikitable(rows, add_last_edit=load_last_edits)

            new_page_text += f"=== {section_title} ===\n\n{table}\n"

    return new_page_text


__all__ = [
    "main",
]
