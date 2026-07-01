"""

https://meta.wikimedia.org/wiki/Category:Hardware_donation_program_open_requests

"""

from typing import Any

import wikitextparser as wtp

from .api.category import get_category_members_titles
from .wtp_parse import (
    extract_subpage_links,
    get_section_by_heading,
)


def get_subpages(
    site: Any,
    full_wikitext: str,
    base_page: str,
    section_title: str | None = None,
) -> list[str]:
    if section_title:
        if section_title == "Draft requests":
            members = get_category_members_titles(
                site,
                "Category:Hardware donation program drafts",
                namespace=0,
            )
            subpages = [x.replace("Hardware donation program/", "") for x in members]
        else:
            section = get_section_by_heading(full_wikitext, section_title)
            subpages = extract_subpage_links(base_page, section)
        return subpages

    parsed = wtp.parse(full_wikitext)
    subpages = extract_subpage_links(base_page, parsed)

    return subpages


__all__ = [
    "get_subpages",
]
