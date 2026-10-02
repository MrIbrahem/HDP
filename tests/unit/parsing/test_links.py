"""
Unit tests for src/parsing/links.py module.
"""

import wikitextparser as wtp
from src.parsing.links import LinkExtractor


class TestGetSection:
    """Test the get_section method of the LinkExtractor class."""

    def test_get_section_by_heading(self):
        wikitext = "== Section 1 ==\nBody 1\n== Section 2 ==\nBody 2"
        section = LinkExtractor().get_section(wikitext, "Section 1")
        assert section is not None
        assert section.title.strip() == "Section 1"
        assert "Body 1" in section.string


    def test_get_section_no_sections(self):
        wikitext = "wiki texts without sections"
        section = LinkExtractor().get_section(wikitext, "Section 1")
        assert section is None

class TestExtractSubPages:
    """Test the extract_subpages method of the LinkExtractor class."""

    def test_extract_subpage_basic(self):
        wiki_text = """
            * [[Hardware donation program/IqbalHossain]]
            * [[Hardware donation program/J ansari/3]]
            * [[Hardware donation program/Jagmit Singh Brar]]
            * [[Hardware donation program/Jaluj I]]
            * [[Hardware donation program/Jbuket]]
            * [[Hardware donation program/JerryAkpan5001]]
            * [[Hardware donation program/Johnjoy12]]
            * [[Hardware donation program/Honeydear]]
            * [[Hardware donation program/HYL56]]
            * [[Hardware donation program/Mr._Ibrahem]]
        """
        subpages = LinkExtractor().extract_subpages("Hardware donation program", wtp.WikiText(wiki_text))
        assert len(subpages) == 10
        assert "Mr. Ibrahem" in subpages

    def test_extract_subpage_links(self):
        # Use plain wikitext instead of MagicMock to simulate multiple links
        wiki_text = """
            * [[Base/Sub1]]
            * [[Base/Sub2]]
            * [[Other/Sub3]]
        """
        subpages = LinkExtractor().extract_subpages("Base", wtp.WikiText(wiki_text))
        assert subpages == ["Sub1", "Sub2"]

    def test_extract_subpage_links_underscores(self):
        # Verify that underscores are correctly replaced with spaces using plain wikitext
        wiki_text = """
            * [[Base/Sub_With_Underscore]]
        """
        subpages = LinkExtractor().extract_subpages("Base", wtp.WikiText(wiki_text))
        assert subpages == ["Sub With Underscore"]
