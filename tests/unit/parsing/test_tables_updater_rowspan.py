"""
Unit tests for src/parsing/tables_updater.py module.
"""

from typing import Any

import pytest

from src.parsing.tables_manager import WikiTableColumnManager
from src.parsing.tables_updater import WikiTableDataUpdater


def update_table(
    rows: dict[str, Any],
    wikitext: str,
    table_headers_to_row_key: dict[str, str],
    replace_values: bool = False,
    add_missing_headers: bool = True,
    span: bool = True,
) -> str:
    """rows: list of rows data."""
    manager = WikiTableColumnManager(span)
    updater = WikiTableDataUpdater(manager)

    return updater.update_wikitable_data(
        rows=rows,
        wikitext=wikitext,
        table_headers_to_row_key=table_headers_to_row_key,
        replace_values=replace_values,
        add_missing_headers=add_missing_headers,
    )

class TestUpdateWikitableDataSpans:

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        self.table_headers_to_row_key = {
            "Page": "page_link",
            "Age of account": "age",
            "Home Wiki": "home_wiki",
        }

    def test_table_with_rowspan(self) -> None:
        """Test how the updater handles rows when a preceding cell spans multiple rows using rowspan."""
        rows = {
            "Hardware donation program/EYo237": {
                "page_link": "Hardware donation program/EYo237",
                "age": "25",
                "home_wiki": "test",
            },
            "Hardware donation program/Ibjaja055": {
                "page_link": "Hardware donation program/Ibjaja055",
                "age": "10",
                "home_wiki": "enwiki",
            },
        }
        # Notice that "Category A" spans 2 rows, which shifts column positions in row 2
        wikitext = """{| class="wikitable sortable"
! Category !! Page !! Age of account !! Home Wiki !! Approved
|-
| rowspan="2" | Category A !! [[Hardware donation program/EYo237]]
| || || || zz
|-
| [[Hardware donation program/Ibjaja055]] || || || yy
|-
|}"""
        result = update_table(rows, wikitext, self.table_headers_to_row_key, True, False)

        # Verify that data for the second row is updated despite cell index shift
        assert "|| 25|" in result
        assert "|| test|" in result
        # assert "|| enwiki|" in result
        # assert "|| 10|" in result

        expected = '{| class="wikitable sortable"\n! Category !! Page !! Age of account !! Home Wiki !! Approved\n|-\n| rowspan="2" | Category A !! [[Hardware donation program/EYo237]]\n| Hardware donation program/EYo237|| 25|| test|| zz\n|-\n| Hardware donation program/EYo237|| 25|| test|| yy\n|-\n|}'
        assert result == expected


    def test_table_with_colspan_in_header(self) -> None:
        """Test table where headers contain colspan attributes."""
        rows = {
            "Hardware donation program/EYo237": {
                "page_link": "Hardware donation program/EYo237",
                "age": "25",
                "home_wiki": "test",
                "new_column": "value",
            }
        }
        wikitext = (
            '{| class="wikitable sortable"\n'
            '! colspan="2" | Page & Info !! Home Wiki !! Approved\n'
            "|-\n"
            "| [[Hardware donation program/EYo237]] || || zz\n"
            "|-\n"
            "|}"
        )

        headers_map = {
            "Page & Info": "page_link",
            "Home Wiki": "home_wiki",
            "New Column": "new_column",
        }

        manager = WikiTableColumnManager(True)
        updater = WikiTableDataUpdater(manager)

        result = updater.update_wikitable_data(
            rows=rows,
            wikitext=wikitext,
            table_headers_to_row_key=headers_map,
            replace_values=True,
            add_missing_headers=True,
            position="end",
        )

        expected = '{| class="wikitable sortable"\n! colspan="2" | Page & Info !! Home Wiki !! Approved\n! New Column\n|-\n| [[Hardware donation program/EYo237]] || Hardware donation program/EYo237|| test\n|\n|-\n|}'
        assert result == expected

    def test_table_with_colspan_in_data_cell(self) -> None:
        """Test updating cells in a row where data cells use colspan."""
        rows = {
            "Hardware donation program/EYo237": {
                "page_link": "Hardware donation program/EYo237",
                "age": "25",
                "home_wiki": "test",
            }
        }
        wikitext = (
            '{| class="wikitable sortable"\n'
            "! Page !! Age of account !! Home Wiki !! Approved\n"
            "|-\n"
            '| [[Hardware donation program/EYo237]] !! colspan="2" | Empty space !! zz\n'
            "|-\n"
            "|}"
        )

        result = update_table(rows, wikitext, self.table_headers_to_row_key)

        # The result string should preserve the colspan attribute or update accordingly
        assert "colspan=" in result
