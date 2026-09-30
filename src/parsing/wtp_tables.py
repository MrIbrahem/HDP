""" """

import logging
import re
from typing import Any

import wikitextparser as wtp
from wikitextparser._cell import Cell

from .wtp_table_manager import WikiTableColumnManager

logger = logging.getLogger(__name__)


class WikiTableDataUpdater:
    """
    Updates Wikitext table data based on a data dictionary (rows),
    with the ability to automatically add missing columns before updating.
    """

    def __init__(self, manager: WikiTableColumnManager | None = None) -> None:
        self.manager = manager or WikiTableColumnManager()

    # ==============================================================
    # Update a single table
    # ==============================================================

    def update_table(
        self,
        table: wtp.Table,
        rows: dict[str, Any],
        table_headers_to_row_key: dict[str, str],
        replace_values: bool = False,
    ) -> None:
        """
        rows keys:
            (page_link, last_update, user_link, editcount_str, recent_editcount_str, age, home_wiki)
        """
        all_rows = table.cells()
        if not all_rows:
            return

        # 1. Map header text to its column index
        header_index = self.manager.get_header_index(table)

        for row in all_rows:
            row_data = self._extract_row_data(row, rows)
            if row_data is None:
                continue

            self._update_row_cells(
                row=row,
                row_data=row_data,
                header_index=header_index,
                table_headers_to_row_key=table_headers_to_row_key,
                replace_values=replace_values,
            )

    def _extract_row_data(
        self,
        row: list[Cell],
        rows: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Extracts the row data from the `rows` dict based on the first link in the first cell."""
        if not row or row[0] is None or row[0].is_header:
            return None

        # Cell('\n| [[Hardware donation program/Ibjaja055]] ')
        first_cell: Cell = row[0]
        first_cell_value: str = first_cell.value
        match_links = re.search(r"\[\[(.*?)\]\]", first_cell_value)

        if not match_links:
            return None

        # Clean the link name to match the dictionary keys
        match_link = match_links.group(1).split("|")[0].strip().replace("_", " ")

        return rows.get(match_link)

    def _update_row_cells(
        self,
        row: list[Cell],
        row_data: dict[str, Any],
        header_index: dict[str, int],
        table_headers_to_row_key: dict[str, str],
        replace_values: bool,
    ) -> None:
        """Updates the row's cells based on the column index."""
        for header, row_key in table_headers_to_row_key.items():
            col_idx = header_index.get(header.strip().lower())
            if col_idx is None or col_idx >= len(row) or row[col_idx] is None:
                continue

            if row_key not in row_data:
                continue

            cell_value = row[col_idx].value
            is_empty = not cell_value or not cell_value.strip()
            if is_empty or replace_values:
                row[col_idx].value = f" {row_data[row_key]}"

    # ==============================================================
    # Main entry point: update all tables in a Wikitext string
    # ==============================================================

    def update_wikitable_data(
        self,
        rows: dict[str, Any],
        wikitext: str,
        table_headers_to_row_key: dict[str, str],
        replace_values: bool = False,
        add_missing_headers: bool = True,
    ) -> str:
        """rows: list of rows data."""
        parsed = wtp.parse(wikitext)
        tables = parsed.get_tables(recursive=False)

        for table in tables:
            if add_missing_headers:
                self.manager.ensure_columns_exists(
                    table=table,
                    cols_name=list(table_headers_to_row_key.keys()),
                    position="after_first",
                    default_value="",
                )

            self.update_table(
                table,
                rows,
                table_headers_to_row_key,
                replace_values=replace_values,
            )

        # Return the updated string representation of the parsed wikitext
        return parsed.string


def update_wikitable_data(
    rows: dict[str, Any],
    wikitext: str,
    table_headers_to_row_key: dict[str, str],
    replace_values: bool = False,
    add_missing_headers: bool = True,
) -> str:
    """rows: list of rows data."""
    manager = WikiTableDataUpdater()

    return manager.update_wikitable_data(
        rows=rows,
        wikitext=wikitext,
        table_headers_to_row_key=table_headers_to_row_key,
        replace_values=replace_values,
        add_missing_headers=add_missing_headers,
    )


__all__ = [
    "WikiTableDataUpdater",
    "update_wikitable_data",
]
