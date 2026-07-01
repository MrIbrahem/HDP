"""

https://meta.wikimedia.org/wiki/Category:Hardware_donation_program_open_requests

"""

import logging
from typing import Any

import wikitextparser as wtp

from .api.category import get_category_count, get_category_members_titles
from .wtp_parse import (
    extract_subpage_links,
    get_section_by_heading,
)

SECTIONS_TO_CATEGORY = {"Draft requests": "Category:Hardware donation program drafts"}

logger = logging.getLogger(__name__)


def get_subpages_for_section(
    site: Any,
    full_wikitext: str,
    base_page: str,
    section_title: str,
) -> list[str]:
    category_name = SECTIONS_TO_CATEGORY.get(section_title)
    if category_name:
        total_pages = get_category_count(site, category_name)
        members = get_category_members_titles(
            site,
            category_name,
            namespace=0,
            total_pages=total_pages,
        )
        subpages = [x.replace(f"{base_page}/", "") for x in members if x.startswith(f"{base_page}/")]
    else:
        section = get_section_by_heading(full_wikitext, section_title)
        if section is None:
            logger.warning(f"Section '{section_title}' not found, returning empty list")
            return []
        subpages = extract_subpage_links(base_page, section)

    logger.debug(f"Found {len(subpages)} subpages")
    return subpages


def get_subpages(
    full_wikitext: str,
    base_page: str,
) -> list[str]:
    parsed = wtp.parse(full_wikitext)
    subpages = extract_subpage_links(base_page, parsed)

    logger.debug(f"Found {len(subpages)} subpages")
    return subpages


__all__ = [
    "get_subpages_for_section",
    "get_subpages",
]
