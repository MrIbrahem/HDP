""" """

from __future__ import annotations

import logging
from collections.abc import Sequence

from ..config import Settings
from ..wiki.category import CategoryService
from ..wiki.client import WikiClient

logger = logging.getLogger(__name__)


class SubPages:

    def __init__(
        self,
        wiki: WikiClient,
        settings: Settings,
        *,
        category: CategoryService | None = None,
    ) -> None:
        self.wiki = wiki
        self.settings = settings
        self.category = category or CategoryService(wiki.site)

    # ------------------------------------------------------------------
    # Subpage discovery
    # ------------------------------------------------------------------

    def discover_subpages(
        self,
        page_title: str,
        section_names: Sequence[str],
    ) -> set[str]:
        """
        Collect application subpage names for the given sections / categories.

        Section names that start with ``Category:`` (or appear in
        ``settings.section_to_category``) are resolved via the category API;
        otherwise the page wikitext is parsed for links under that heading.
        """
        full_wikitext = self.wiki.get_page_wikitext(page_title)
        found: set[str] = set()

        for section_title in section_names:
            for sub in self._subpages_for_section(full_wikitext, section_title):
                found.add(sub)

        if not found:
            # Fallback: every subpage link on the page
            found = self._all_subpage_links(full_wikitext)

        logger.info("Total subpages collected: %s", len(found))
        return found

    def _subpages_for_section(self, full_wikitext: str, section_title: str) -> list[str]:
        base = self.settings.base_page

        # Direct category name
        if section_title.startswith("Category:"):
            return self._subpages_from_category(section_title)

        # Mapped section → category
        category_name = self.settings.section_to_category.get(section_title)
        if category_name:
            return self._subpages_from_category(category_name)

        # Parse section body for wikilinks (requires parsing module)
        try:
            from ..parsing.links import LinkExtractor

            extractor = LinkExtractor()
            section = extractor.get_section(full_wikitext, section_title)
            if section is None:
                logger.warning("Section %r not found", section_title)
                return []
            return extractor.extract_subpages(base, section)
        except ImportError:
            logger.warning(
                "parsing.links not available; cannot parse section %r",
                section_title,
            )
            return []

    def _subpages_from_category(self, category_name: str) -> list[str]:
        base = self.settings.base_page
        total = self.category.count(category_name)
        members = self.category.member_titles(category_name, namespace=0, total_pages=total)
        prefix = f"{base}/"
        subpages = [m[len(prefix) :] for m in members if m.startswith(prefix)]
        logger.debug("Category %r → %s subpages", category_name, len(subpages))
        return subpages

    def _all_subpage_links(self, full_wikitext: str) -> set[str]:
        try:
            import wikitextparser as wtp

            from ..parsing.links import LinkExtractor

            parsed = wtp.parse(full_wikitext)
            return set(LinkExtractor().extract_subpages(self.settings.base_page, parsed))
        except ImportError:
            return set()


__all__ = [
    "SubPages",
]
