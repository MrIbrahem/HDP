import pytest

from src.wtp_parse.wtp_tables_header import (
    WikiTableColumnManager,
    ensure_column_in_wikitext,
)

@pytest.fixture
def sample_wikitext():
    """Fixture providing a standard wikitext table for testing."""
    return """{| class="wikitable"
! Page title
! Author
|-
| Main Page || Admin
|-
| Help || User1
|}"""


@pytest.fixture
def wikitext_without_tables():
    """Fixture providing plain text with no tables."""
    return "This is just a regular text without any wikitext tables."


class TestWikiTableColumnManager:
    """Tests for WikiTableColumnManager class methods."""

    def test_has_column_returns_true_when_exists(self, sample_wikitext):
        manager = WikiTableColumnManager(sample_wikitext)
        table = manager.parsed.tables[0]

        assert manager.has_column(table, "Author") is True
        assert manager.has_column(table, "author") is True  # Case-insensitive check

    def test_has_column_returns_false_when_missing(self, sample_wikitext):
        manager = WikiTableColumnManager(sample_wikitext)
        table = manager.parsed.tables[0]

        assert manager.has_column(table, "Country") is False

    def test_add_column_at_end(self, sample_wikitext):
        manager = WikiTableColumnManager(sample_wikitext)
        table = manager.parsed.tables[0]

        success = manager.add_column(
            table, col_name="Country", default_value="Yemen", position="end"
        )

        assert success is True
        result = manager.parsed.string
        assert "! Country" in result
        assert "| Yemen" in result

    def test_add_column_after_first(self, sample_wikitext):
        manager = WikiTableColumnManager(sample_wikitext)
        table = manager.parsed.tables[0]

        success = manager.add_column(
            table, col_name="Status", default_value="Active", position="after_first"
        )

        assert success is True
        result = manager.parsed.string
        assert "! Status" in result
        assert "| Active" in result

    def test_ensure_column_exists_adds_missing_column(self, sample_wikitext):
        manager = WikiTableColumnManager(sample_wikitext)
        result = manager.ensure_column_exists("Country", default_value="Unknown")

        assert "! Country" in result
        assert "| Unknown" in result

    def test_ensure_column_exists_does_not_duplicate_existing(self, sample_wikitext):
        manager = WikiTableColumnManager(sample_wikitext)
        result = manager.ensure_column_exists("Author")

        # Column already exists, text should remain unchanged
        assert result == sample_wikitext

    def test_ensure_column_exists_handles_no_tables(self, wikitext_without_tables):
        manager = WikiTableColumnManager(wikitext_without_tables)
        result = manager.ensure_column_exists("Country")

        assert result == wikitext_without_tables


INPUT_TABLE = """{| class="wikitable"
! Page title !! Author
|-
| Main Page || Admin
|-
| Help || User1
|}"""

EXPECTED_TABLE = """{| class="wikitable"
! Page title !! Author
! Views
|-
| Main Page || Admin
| 0
|-
| Help || User1
| 0
|}"""

class TestConvenienceFunction:
    """Tests for the helper function ensure_column_in_wikitext."""

    def test_ensure_column_in_wikitext_helper(self):
        result = ensure_column_in_wikitext(
            text=INPUT_TABLE,
            col_name="Views",
            default_value="0",
            position="end",
        )

        assert "! Views" in result
        assert "| 0" in result
        assert result == EXPECTED_TABLE

    def test_add_values(self):
        input_table = """{| class="wikitable"
! Page title !! Author
! Views
|-
| Main Page || Admin
|
|-
| Help || User1
|
|}"""

        expected_table = """{| class="wikitable"
! Page title !! Author
! Views
|-
| Main Page || Admin
|
|-
| Help || User1
|
|}
"""

        result = ensure_column_in_wikitext(
            text=input_table,
            col_name="Views",
            default_value="0",
            position="end",
        )

        assert "! Views" in result
        assert result.strip() == expected_table.strip()
