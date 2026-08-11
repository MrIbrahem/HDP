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
from ..load_subpages import get_subpages, get_subpages_for_section
from ..utils import load_credentials
from ..wtp_parse import update_wikitable_data
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


def update(
    page_title: str,
    section_names: list[str],
    unknown_placeholder: str = "unknown",
    load_recent_editcounts: bool = True,
) -> str:
    """
    Updates and saves the wikitable data for a specified Wikipedia page or its subpages.

    This function authenticates with Meta Wiki using credentials loaded from a .env file,
    retrieves the wikitext of the specified page, and determines the relevant subpages
    either by specific section/category names or by default parsing. It then loads the
    tabular data from these subpages, updates the wikitable within the page's wikitext,
    and saves the resulting text to a local output file.
    """
    api = get_api()

    if not api:
        logger.error("Failed to connect to Meta Wiki")
        return ""

    full_wikitext = api.get_page_wikitext(page_title)
    all_subpages: set[str] = set()

    if section_names:
        for section_title in section_names:
            _subpages = get_subpages_for_section(api.site, full_wikitext, BASE_PAGE, section_title=section_title)
            for sp in _subpages:
                all_subpages.add(sp)

    # Fallback to default subpage parsing
    if not all_subpages:
        all_subpages = get_subpages(full_wikitext, BASE_PAGE)

    logger.info(f"Total subpages collected: {len(all_subpages)}")

    rows = load_rows(
        api,
        all_subpages,
        unknown_placeholder=unknown_placeholder,
        load_recent_editcounts=load_recent_editcounts,
        base_page=BASE_PAGE,
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

    page_updated_text = update_wikitable_data(
        rows,
        full_wikitext,
        table_headers_to_row_key,
        replace_values=False,
    )
    return page_updated_text


__all__ = [
    "update",
]
