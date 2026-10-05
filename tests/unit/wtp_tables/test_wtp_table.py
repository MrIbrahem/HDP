"""
Unit tests for src/wtp_tables/wtp_table.py module.
"""

import pytest
import wikitextparser as wtp

from src.wtp_tables.wtp_table import WtpCell, WtpRow, WtpTable


@pytest.fixture
def simple_wikitext() -> str:
    return """{| class="wikitable"
! Page !! Age
|-
| [[A]] || 1
|-
| [[B]] || 2
|}"""


@pytest.fixture
def lines_wikitext() -> str:
    """Every cell on its own line (the format used by the real tables)."""
    return """{| class="wikitable"
! Page
! Age
! Home Wiki
|-
| [[A]]
| 111
|
|}"""


@pytest.fixture
def complex_wikitext() -> str:
    """Multi-row header with rowspan/colspan."""
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


# ===========================================================================
# WtpTable.load — basics
# ===========================================================================


class TestLoadSimple:

    def test_load_from_string(self, simple_wikitext):
        t = WtpTable.load_text(simple_wikitext)

        assert isinstance(t, WtpTable)
        assert isinstance(t.table, wtp.Table)
        assert len(t) == 3
        assert all(isinstance(r, WtpRow) for r in t.rows)
        assert all(isinstance(c, WtpCell) for r in t.rows for c in r.cells)

    def test_load_from_wtp_table_keeps_same_object(self, simple_wikitext):
        table = wtp.Table(simple_wikitext)
        t = WtpTable.load(table)

        assert t.table is table
        assert len(t) == 3

    def test_span_is_stored(self, simple_wikitext):
        assert WtpTable.load_text(simple_wikitext).span is True
        assert WtpTable.load_text(simple_wikitext, span=False).span is False

    def test_header_and_data_rows(self, simple_wikitext):
        t = WtpTable.load_text(simple_wikitext)

        assert [r.is_header for r in t.rows] == [True, False, False]
        assert len(t.header_rows) == 1
        assert len(t.data_rows) == 2

    def test_headers(self, simple_wikitext):
        t = WtpTable.load_text(simple_wikitext)

        assert t.headers == ["Page", "Age"]

    def test_cells_get_their_header(self, simple_wikitext):
        t = WtpTable.load_text(simple_wikitext)
        row = t.data_rows[0]

        assert [c.header for c in row.cells] == ["Page", "Age"]
        assert [c.index for c in row.cells] == [0, 1]
        assert row.cells[0].value.strip() == "[[A]]"
        assert row.cells[1].value.strip() == "1"

    def test_simple_table_no_span(self, simple_wikitext):
        t = WtpTable.load_text(simple_wikitext, span=False)

        assert t.headers == ["Page", "Age"]
        assert len(t.data_rows) == 2

    def test_iteration(self, simple_wikitext):
        t = WtpTable.load_text(simple_wikitext)

        assert list(t) == t.rows


# ===========================================================================
# WtpTable.load — edge cases
# ===========================================================================


class TestLoadEdgeCases:

    def test_empty_table(self):
        t = WtpTable.load_text('{| class="wikitable"\n|}')

        assert t.rows == []
        assert t.headers == []
        assert t.header_rows == []
        assert t.data_rows == []
        assert len(t) == 0

    def test_cells_failure_returns_empty_table(self, simple_wikitext, monkeypatch):
        def boom(self, *args, **kwargs):
            raise RuntimeError("boom")

        monkeypatch.setattr(wtp.Table, "cells", boom)

        t = WtpTable.load_text(simple_wikitext)

        assert t.rows == []
        assert isinstance(t.table, wtp.Table)

    def test_table_without_header_row(self):
        text = """{| class="wikitable"
|-
| A
| B
|}"""
        t = WtpTable.load_text(text)

        assert t.header_rows == []
        assert len(t.data_rows) == 1
        assert [c.header for c in t.data_rows[0].cells] == ["", ""]


# ===========================================================================
# WtpRow
# ===========================================================================


class TestWtpRow:

    def test_get_is_case_insensitive(self, simple_wikitext):
        row = WtpTable.load_text(simple_wikitext).data_rows[0]

        assert row.get("Age") is not None
        assert row.get("age") is not None
        assert row.get("  AGE ") is not None
        assert row.get("age").value.strip() == "1"

    def test_get_missing_header_returns_none(self, simple_wikitext):
        row = WtpTable.load_text(simple_wikitext).data_rows[0]

        assert row.get("Country") is None

    def test_to_dict(self, simple_wikitext):
        row = WtpTable.load_text(simple_wikitext).data_rows[1]

        assert row.to_dict() == {"page": "[[B]]", "age": "2"}

    def test_empty_row(self):
        row = WtpRow()

        assert row.cells == []
        assert row.is_header is False
        assert row.get("x") is None
        assert row.to_dict() == {}


# ===========================================================================
# WtpCell
# ===========================================================================


class TestWtpCell:

    def test_is_empty(self, lines_wikitext):
        row = WtpTable.load_text(lines_wikitext).data_rows[0]

        assert row.get("Page").is_empty is False
        assert row.get("Age").is_empty is False
        assert row.get("Home Wiki").is_empty is True

    def test_value_setter_updates_table_string(self, lines_wikitext):
        t = WtpTable.load_text(lines_wikitext)
        cell = t.data_rows[0].get("Age")

        cell.value = " 999"

        assert cell.value == " 999"
        assert "999" in t.table.string
        assert "111" not in t.table.string

    def test_fill_empty_cell(self, lines_wikitext):
        t = WtpTable.load_text(lines_wikitext)
        cell = t.data_rows[0].get("Home Wiki")

        cell.value = " enwiki"

        assert "enwiki" in t.table.string


# ===========================================================================
# Complex table: rowspan / colspan
# ===========================================================================


class TestComplexTable:

    def test_row_counts(self, complex_wikitext):
        t = WtpTable.load_text(complex_wikitext)

        assert len(t) == 3
        assert len(t.header_rows) == 2
        assert len(t.data_rows) == 1

    def test_every_row_has_13_cells_with_span(self, complex_wikitext):
        t = WtpTable.load_text(complex_wikitext)

        assert [len(r.cells) for r in t.rows] == [13, 13, 13]

    def test_leaf_headers(self, complex_wikitext):
        t = WtpTable.load_text(complex_wikitext)

        assert t.headers == [
            "Application",
            "Latest update",
            "User",
            "Country",
            "Extended rights",
            "Global",
            "Global no WD",
            "WD",
            "Global no WD",
            "WD",
            "Account age",
            "Home Wiki",
            "Approved",
        ]

    def test_header_path_rowspan_has_no_duplicates(self, complex_wikitext):
        row = WtpTable.load_text(complex_wikitext).data_rows[0]

        assert row.cells[0].header_path == ("Application",)
        assert row.cells[11].header_path == ("Home Wiki",)

    def test_header_path_colspan_has_parent(self, complex_wikitext):
        cells = WtpTable.load_text(complex_wikitext).data_rows[0].cells

        assert cells[5].header_path == ("User Edits", "Global")
        assert cells[7].header_path == ("User Edits", "WD")
        assert cells[8].header_path == ("Last 3 months edits", "Global no WD")
        assert cells[9].header_path == ("Last 3 months edits", "WD")

    def test_data_row_values_by_header(self, complex_wikitext):
        row = WtpTable.load_text(complex_wikitext).data_rows[0]

        assert row.get("Application").value.strip() == "User1"
        assert row.get("Country").value.strip() == "Country"
        assert row.get("Home Wiki").value.strip() == "Home Wiki"
        assert row.get("Approved").value.strip() == "Approved"

    def test_duplicate_header_get_returns_first(self, complex_wikitext):
        row = WtpTable.load_text(complex_wikitext).data_rows[0]

        # "WD" appears at index 7 and 9
        assert row.get("WD").index == 7

    def test_cell_indexes_are_sequential(self, complex_wikitext):
        for row in WtpTable.load_text(complex_wikitext).rows:
            assert [c.index for c in row.cells] == list(range(13))

    def test_no_span_keeps_literal_rows(self, complex_wikitext):
        t = WtpTable.load_text(complex_wikitext, span=False)

        assert len(t) == 3
        assert [len(r.cells) for r in t.rows] == [10, 5, 13]
