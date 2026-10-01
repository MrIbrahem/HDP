"""
Unit tests for src/parsing/links.py module.

Classes to test: LinkExtractor

TODO: write tests
"""

from unittest.mock import MagicMock

from src.parsing.links import LinkExtractor

class TestGetSection:
    """ Test the get_section method of the LinkExtractor class. """
    def test_get_section_by_heading(self):
        wikitext = "== Section 1 ==\nBody 1\n== Section 2 ==\nBody 2"
        section = LinkExtractor().get_section(wikitext, "Section 1")
        assert section is not None
        assert section.title.strip() == "Section 1"
        assert "Body 1" in section.string

class TestExtractSubPages:
    """ Test the extract_subpages method of the LinkExtractor class. """

    def test_extract_subpage_links(self):

        section = MagicMock()
        link1 = MagicMock()
        link1.title = "Base/Sub1"
        link2 = MagicMock()
        link2.title = "Base/Sub2"
        link3 = MagicMock()
        link3.title = "Other/Sub3"
        section.wikilinks = [link1, link2, link3]

        subpages = LinkExtractor().extract_subpages("Base", section)
        assert subpages == ["Sub1", "Sub2"]


    def test_extract_subpage_links_underscores(self):

        section = MagicMock()
        link1 = MagicMock()
        link1.title = "Base/Sub_With_Underscore"
        section.wikilinks = [link1]

        subpages = LinkExtractor().extract_subpages("Base", section)
        assert subpages == ["Sub With Underscore"]
