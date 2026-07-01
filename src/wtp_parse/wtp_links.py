""" """

import logging
from typing import Any

import wikitextparser as wtp

logger = logging.getLogger(__name__)


def get_section_by_heading(wikitext, heading):
    """Use wikitextparser to find a section by its heading text."""
    parsed = wtp.parse(wikitext)
    for section in parsed.get_sections(include_subsections=True):
        if section.title and section.title.strip() == heading:
            return section
    raise ValueError(f"Section '{heading}' not found")


def extract_subpage_links(
    base_page: str,
    section: Any,
) -> list[str]:
    """Use wikitextparser's wikilinks to pull out 'Base/Sub' page names."""
    prefix = base_page + "/"
    seen = []
    for link in section.wikilinks:
        title = link.title.strip()
        title = title.replace("_", " ")

        if title.startswith(prefix):
            name = title[len(prefix) :]
            if name not in seen:
                seen.append(name)
    return seen

__all__ = [
    "get_section_by_heading",
    "extract_subpage_links",
]
