"""
Unit tests for src/parsing/tables_manager.py module.
"""

import pytest
import wikitextparser as wtp

from src.parsing.tables_manager import WikiTableColumnManager


@pytest.fixture
def sample_wikitext_2() -> str:
    """Fixture providing a standard wikitext table for testing."""
    return """
{| class="wikitable sortable"
! rowspan="2" | Application
! rowspan="2" | Latest update
! rowspan="2" |User
! rowspan="2" | Country
! rowspan="2" |Extended rights
! colspan="3" | User Edits
! colspan="2" |Last 3 months edits
! rowspan="2" | Account age
! rowspan="2" | Home Wiki
! rowspan="2" | Approved
|-
!Global
!Global no WD
!WD
!Global no WD
!WD
|-
| User1
| Latest update
|User
|Country
|Extended rights
| Global
| Global no WD
| WD
| Global no WD
|WD
| Account age
|Home Wiki
|Approved
|-
|}"""


class TestWikiTableColumnManager2:
    """Tests for wtp methods."""

    def test_get_header_row(self, sample_wikitext_2):
        manager = WikiTableColumnManager()
        table = wtp.Table(sample_wikitext_2)
        rows = manager._get_header_row(table)

        assert rows is not None
        assert len(rows) == 13

    def test_get_header_row_no_span(self, sample_wikitext_2):
        manager = WikiTableColumnManager(False)
        table = wtp.Table(sample_wikitext_2)
        rows = manager._get_header_row(table)

        assert rows is not None
        assert len(rows) == 10

    def test_get_header_index(self, sample_wikitext_2):
        manager = WikiTableColumnManager()
        table = wtp.Table(sample_wikitext_2)
        rows = manager.get_header_index(table)

        assert rows is not None
        assert rows == {
            "application": 0,
            "latest update": 1,
            "user": 2,
            "country": 3,
            "extended rights": 4,
            "user edits": 7,
            "last 3 months edits": 9,
            "account age": 10,
            "home wiki": 11,
            "approved": 12,
        }

    def test_get_header_index_no_span(self, sample_wikitext_2):
        manager = WikiTableColumnManager(False)
        table = wtp.Table(sample_wikitext_2)
        rows = manager.get_header_index(table)

        assert rows is not None
        assert rows == {
            "application": 0,
            "latest update": 1,
            "user": 2,
            "country": 3,
            "extended rights": 4,
            "user edits": 5,
            "last 3 months edits": 6,
            "account age": 7,
            "home wiki": 8,
            "approved": 9,
        }
