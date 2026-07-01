from src.wtp_parse.wtp_links import extract_subpage_links, get_section_by_heading


def test_get_section_by_heading():
    wikitext = "== Section 1 ==\nBody 1\n== Section 2 ==\nBody 2"
    section = get_section_by_heading(wikitext, "Section 1")
    assert section is not None
    assert section.title.strip() == "Section 1"
    assert "Body 1" in section.string


def test_extract_subpage_links():
    from unittest.mock import MagicMock

    section = MagicMock()
    link1 = MagicMock()
    link1.title = "Base/Sub1"
    link2 = MagicMock()
    link2.title = "Base/Sub2"
    link3 = MagicMock()
    link3.title = "Other/Sub3"
    section.wikilinks = [link1, link2, link3]

    subpages = extract_subpage_links("Base", section)
    assert subpages == ["Sub1", "Sub2"]


def test_extract_subpage_links_underscores():
    from unittest.mock import MagicMock

    section = MagicMock()
    link1 = MagicMock()
    link1.title = "Base/Sub_With_Underscore"
    section.wikilinks = [link1]

    subpages = extract_subpage_links("Base", section)
    assert subpages == ["Sub With Underscore"]
