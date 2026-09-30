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

from ..config import load_credentials
from ..services.hdp_service import HdpService
from ..wiki.client import WikiClient

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



def main(
    page_title: str,
    section_names: list[str],
    unknown_placeholder: str = "unknown",
    load_recent_editcounts: bool = True,
    load_last_edits: bool = False,
) -> str:
    api = get_api()

    if not api:
        logger.error("Failed to connect to Meta Wiki")
        return ""

    return HdpService(api).generate(
        page_title,
        section_names,
        load_recent_editcounts=load_recent_editcounts,
        load_last_edits=load_last_edits,
        unknown=unknown_placeholder,
    )

__all__ = [
    "main",
]
