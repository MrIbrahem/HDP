"""
Section lookup and subpage-link extraction from wikitext.
"""

from __future__ import annotations

import logging
from typing import Any

import wikitextparser as wtp

logger = logging.getLogger(__name__)


class LinkExtractor:
    """Extract sections and subpage wikilinks from MediaWiki wikitext."""

    def get_section(
        self,
        wikitext: str,
        heading: str,
    ) -> Any | None:
        """
        Return the first section whose title matches ``heading`` exactly
        (after stripping), or ``None``.
        """
        parsed = wtp.parse(wikitext)
        for section in parsed.get_sections(include_subsections=True):
            if section.title and section.title.strip() == heading:
                return section
        logger.warning("Section %r not found", heading)
        return None

    def extract_subpages(
        self,
        base_page: str,
        section: wtp.WikiText | wtp.Section,
    ) -> list[str]:
        """
        Collect unique subpage names linked as ``BasePage/Sub`` inside
        ``section`` (a wikitextparser Section or any object with ``.wikilinks``).
        """
        prefix = base_page + "/"
        seen: list[str] = []
        for link in section.wikilinks:
            title = (link.title or "").strip().replace("_", " ")
            if title.startswith(prefix):
                name = title[len(prefix) :]
                if name and name not in seen:
                    seen.append(name)
        return seen


__all__ = [
    "LinkExtractor",
]
