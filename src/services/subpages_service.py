""" """

from __future__ import annotations

import logging
from collections.abc import Sequence

import wikitextparser as wtp

from ..config import Settings
from ..parsing.links import LinkExtractor
from ..wiki.category import CategoryService
from ..wiki.client import WikiClient

logger = logging.getLogger(__name__)


class SubPagesService:

    def __init__(
        self,
        wiki_client: WikiClient,
        settings: Settings,
        *,
        category: CategoryService | None = None,
    ) -> None:
        self.wiki = wiki_client
        self.settings = settings
        self.category = category or CategoryService(wiki_client.site)
        self.extractor = LinkExtractor()

    # ------------------------------------------------------------------
    # Subpage discovery
    # ------------------------------------------------------------------

    def discover_subpages(
        self,
        page_title: str,
        section_names: Sequence[str],
        full_wikitext: str | None = None,
    ) -> set[str]:
        """
        Collect application subpage names for the given sections / categories.

        Section names that start with ``Category:`` (or appear in
        ``settings.section_to_category``) are resolved via the category API;
        otherwise the page wikitext is parsed for links under that heading.
        """
        if not full_wikitext:
            full_wikitext = self.wiki.get_page_wikitext(page_title)

        found: set[str] = set()

        for section_title in section_names:
            for sub in self._subpages_for_section(full_wikitext, section_title):
                found.add(sub)

        # Fallback to default subpage parsing
        if not found:
            # Fallback: every subpage link on the page
            found = self._all_subpage_links(full_wikitext)

        logger.info("Total subpages collected: %s", len(found))
        return found

    def _subpages_for_section(
        self,
        full_wikitext: str,
        section_title: str,
    ) -> list[str]:
        # If the caller passed a full category name, use it directly
        base = self.settings.base_page

        # Direct category name
        if section_title.startswith("Category:"):
            return self._subpages_from_category(section_title)

        # Mapped section → category
        category_name = self.settings.section_to_category.get(section_title)
        if category_name:
            return self._subpages_from_category(category_name)

        # Parse section body for wikilinks (requires parsing module)
        section = self.extractor.get_section(full_wikitext, section_title)
        if section is None:
            logger.warning("Section %r not found", section_title)
            return []

        return self.extractor.extract_subpages(base, section)

    def _subpages_from_category(self, category_name: str) -> list[str]:
        """Fetch subpage names (relative to base_page) from a MediaWiki category."""
        base = self.settings.base_page
        total = self.category.count(category_name)
        members = self.category.member_titles(
            category_name,
            namespace=0,
            total_pages=total,
        )
        prefix = f"{base}/"
        subpages = [m[len(prefix) :] for m in members if m.startswith(prefix)]
        logger.debug("Category %r → %s subpages", category_name, len(subpages))
        return subpages

    def _all_subpage_links(self, full_wikitext: str) -> set[str]:
        parsed = wtp.parse(full_wikitext)
        subpages = set(self.extractor.extract_subpages(self.settings.base_page, parsed))
        logger.debug(f"Found {len(subpages)} subpages")
        return set(subpages)


__all__ = [
    "SubPagesService",
]
