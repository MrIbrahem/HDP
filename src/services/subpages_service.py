""" """

from __future__ import annotations

import logging
from typing import Any

import wikitextparser as wtp

from ..config import SECTION_TO_CATEGORY
from ..parsing import (
    extract_subpage_links,
    get_section_by_heading,
)
from ..wiki.category import CategoryService

logger = logging.getLogger(__name__)


def _subpages_from_category(
    site: Any,
    category_name: str,
    base_page: str,
) -> list[str]:
    """Fetch subpage names (relative to base_page) from a MediaWiki category."""
    if not category_name.startswith("Category:"):
        category_name = f"Category:{category_name}"

    service = CategoryService(site)

    total_pages = service.count(category_name)

    members = service.member_titles(
        category_name,
        namespace=0,
        total_pages=total_pages,
    )
    prefix = f"{base_page}/"
    subpages = [x[len(prefix) :] for x in members if x.startswith(prefix)]
    logger.debug(f"Category '{category_name}': {len(subpages)} subpages")
    return subpages


def _subpages_for_section(
    site: Any,
    full_wikitext: str,
    base_page: str,
    section_title: str,
) -> list[str]:
    # If the caller passed a full category name, use it directly
    if section_title.startswith("Category:"):
        return _subpages_from_category(site, section_title, base_page)

    category_name = SECTION_TO_CATEGORY.get(section_title)
    if category_name:
        subpages = _subpages_from_category(site, category_name, base_page)
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
) -> set[str]:
    parsed = wtp.parse(full_wikitext)
    subpages = extract_subpage_links(base_page, parsed)

    logger.debug(f"Found {len(subpages)} subpages")
    return set(subpages)


__all__ = [
    "_subpages_for_section",
    "get_subpages",
]
