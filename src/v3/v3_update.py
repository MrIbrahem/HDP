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

from ..config import BASE_PAGE, load_credentials
from ..models import TABLE_HEADERS_TO_ROW_KEY
from ..parsing import update_wikitable_data
from ..services.subpages_service import _subpages_for_section, get_subpages
from ..wiki.client import WikiClient
from .worker import load_rows

logger = logging.getLogger(__name__)


def get_api() -> None | WikiClient:
    username, password = load_credentials()
    if not username or not password:
        logger.error("Failed to load credentials from .env file")
        logger.error("Please create a .env file with WIKIPEDIA_BOT_USERNAME and WIKIPEDIA_BOT_PASSWORD")
        return None

    # Connect to Meta Wiki
    api = WikiClient.connect_by_user(username, password)
    if not api:
        logger.error("Failed to connect to Meta Wiki")
        return None

    return api


def update(
    page_title: str,
    section_names: list[str],
    unknown_placeholder: str = "unknown",
    load_recent_editcounts: bool = True,
    load_last_edits: bool = False,
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
            _subpages = _subpages_for_section(api._site, full_wikitext, BASE_PAGE, section_title=section_title)
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
        load_last_edits=load_last_edits,
        base_page=BASE_PAGE,
    )

    if load_last_edits:
        TABLE_HEADERS_TO_ROW_KEY["Last edit"] = "last_edit"

    page_updated_text = update_wikitable_data(
        rows,
        full_wikitext,
        TABLE_HEADERS_TO_ROW_KEY,
        replace_values=False,
    )
    return page_updated_text


__all__ = [
    "update",
]
