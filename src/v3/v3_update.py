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
from ..load_subpages import get_subpages, get_subpages_for_section
from ..utils import load_credentials
from ..wtp_parse import update_wikitable_data
from . import load_rows

BASE_PAGE = "Hardware donation program"
OUTPUT_DIR = Path(__file__).parent.parent / "data"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# How many days back counts as "recent" for the recent-edits column.
RECENT_DAYS = 90

logger = logging.getLogger(__name__)


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
    "update",
]
