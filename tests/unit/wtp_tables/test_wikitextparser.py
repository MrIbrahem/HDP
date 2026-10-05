"""
Unit tests for wikitextparser library.
"""

import pytest
import wikitextparser as wtp
from wikitextparser._cell import Cell


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


class TestWTP:
    """Tests for wtp methods."""

    def test_cells(self, sample_wikitext_2):
        table = wtp.Table(sample_wikitext_2)
        cell1 = table.cells(row=0, column=5, span=True)

        assert cell1 is not None
        assert cell1.string == '\n! colspan="3" | User Edits'

        cell2 = table.cells(row=1, column=5, span=True)
        assert cell2 is not None
        assert cell2.string == "\n!Global"

    def test_table_data(self, sample_wikitext_2):
        table = wtp.Table(sample_wikitext_2)
        data = table.data(span=False)

        assert data is not None
        assert len(data) == 3

    def test_table_cells(self, sample_wikitext_2):
        table = wtp.Table(sample_wikitext_2)
        cells_no_span = table.cells(span=False)

        assert cells_no_span is not None
        assert len(cells_no_span) == 3
        assert len(cells_no_span[1]) == 5

        cells_with_span = table.cells(span=True)

        assert cells_with_span is not None
        assert len(cells_with_span[1]) == 13

    def test_load_table_cells(self, sample_wikitext_2):
        table = wtp.Table(sample_wikitext_2)
        cells = table.cells(span=True)

        assert cells is not None
        assert len(cells) == 3

        cells_0 = [
            Cell('\n! rowspan="2" | Application'),
            Cell('\n! rowspan="2" | Latest update'),
            Cell('\n! rowspan="2" |User'),
            Cell('\n! rowspan="2" | Country'),
            Cell('\n! rowspan="2" |Extended rights'),
            Cell('\n! colspan="3" | User Edits'),
            Cell('\n! colspan="3" | User Edits'),
            Cell('\n! colspan="3" | User Edits'),
            Cell('\n! colspan="2" |Last 3 months edits'),
            Cell('\n! colspan="2" |Last 3 months edits'),
            Cell('\n! rowspan="2" | Account age'),
            Cell('\n! rowspan="2" | Home Wiki'),
            Cell('\n! rowspan="2" | Approved'),
        ]
        assert [x.string for x in cells[0]] == [x.string for x in cells_0]
        assert cells[0][0].is_header is True

        cells_1 = [
            Cell('\n! rowspan="2" | Application'),
            Cell('\n! rowspan="2" | Latest update'),
            Cell('\n! rowspan="2" |User'),
            Cell('\n! rowspan="2" | Country'),
            Cell('\n! rowspan="2" |Extended rights'),
            Cell("\n!Global"),
            Cell("\n!Global no WD"),
            Cell("\n!WD"),
            Cell("\n!Global no WD"),
            Cell("\n!WD"),
            Cell('\n! rowspan="2" | Account age'),
            Cell('\n! rowspan="2" | Home Wiki'),
            Cell('\n! rowspan="2" | Approved'),
        ]

        assert [x.string for x in cells[1]] == [x.string for x in cells_1]
        cells_2 = [
            Cell("\n| User1"),
            Cell("\n| Latest update"),
            Cell("\n|User"),
            Cell("\n|Country"),
            Cell("\n|Extended rights"),
            Cell("\n| Global"),
            Cell("\n| Global no WD"),
            Cell("\n| WD"),
            Cell("\n| Global no WD"),
            Cell("\n|WD"),
            Cell("\n| Account age"),
            Cell("\n|Home Wiki"),
            Cell("\n|Approved"),
        ]

        assert [x.string for x in cells[2]] == [x.string for x in cells_2]

    def test_load_table_cells_no_span(self, sample_wikitext_2):
        table = wtp.Table(sample_wikitext_2)
        cells = table.cells(span=False)

        assert cells is not None
        assert len(cells) == 3

        cells_0 = [
            Cell('\n! rowspan="2" | Application'),
            Cell('\n! rowspan="2" | Latest update'),
            Cell('\n! rowspan="2" |User'),
            Cell('\n! rowspan="2" | Country'),
            Cell('\n! rowspan="2" |Extended rights'),
            Cell('\n! colspan="3" | User Edits'),
            # Cell('\n! colspan="3" | User Edits'),
            # Cell('\n! colspan="3" | User Edits'),
            # Cell('\n! colspan="2" |Last 3 months edits'),
            Cell('\n! colspan="2" |Last 3 months edits'),
            Cell('\n! rowspan="2" | Account age'),
            Cell('\n! rowspan="2" | Home Wiki'),
            Cell('\n! rowspan="2" | Approved'),
        ]
        assert [x.string for x in cells[0]] == [x.string for x in cells_0]
        assert cells[0][0].is_header is True

        cells_1 = [
            Cell("\n!Global"),
            Cell("\n!Global no WD"),
            Cell("\n!WD"),
            Cell("\n!Global no WD"),
            Cell("\n!WD"),
        ]

        assert [x.string for x in cells[1]] == [x.string for x in cells_1]
