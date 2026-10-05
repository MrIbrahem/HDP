"""
Fill wikitext tables from a `rows` dict, built on top of WtpTable.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import wikitextparser as wtp

from .wtp_table import WtpRow, WtpTable

logger = logging.getLogger(__name__)


class WtpTableUpdater:
    """
    Update wikitext tables from a data dictionary.

    Cells are found by header name (leaf header, case-insensitive), so tables
    with multi-row headers (rowspan/colspan) are supported.
    """

    # ==============================================================
    # Row matching
    # ==============================================================

    @staticmethod
    def _extract_row_data(row: WtpRow, rows: dict[str, Any]) -> dict[str, Any] | None:
        """Find the row's data in `rows` using the first cell ([[link]] or plain text)."""
        if not row.cells or row.is_header or row.cells[0].cell.is_header:
            return None

        first_value = row.cells[0].value
        match = re.search(r"\[\[(.*?)\]\]", first_value)
        text = match.group(1).split("|")[0] if match else first_value

        key = text.strip().replace("_", " ")
        return rows.get(key) if key else None

    # ==============================================================
    # Adding missing columns
    # ==============================================================

    @staticmethod
    def _missing_headers(wtp_table: WtpTable, wanted: list[str]) -> list[str]:
        existing = {h.strip().lower() for h in wtp_table.headers}
        return [h for h in wanted if h.strip().lower() not in existing]

    @staticmethod
    def add_columns_at_end(table: wtp.Table, col_names: list[str]) -> None:
        """
        Append columns at the end of the table.

        Uses the literal cell grid (span=False). With a multi-row header the
        new header cell is written once, in the first header row, with
        ``rowspan=<number of header rows>``; other header rows are untouched.
        """
        if not col_names:
            return

        grid = table.cells(span=False)
        if not grid:
            return

        n_header_rows = WtpTable._count_header_rows(grid)

        for r_idx, row in enumerate(grid):
            valid = [c for c in row if c is not None]
            if not valid:
                continue

            if r_idx < n_header_rows:
                if r_idx > 0:
                    continue  # covered by rowspan from the first header row
                if n_header_rows > 1:
                    new_cells = "".join(f'\n! rowspan="{n_header_rows}" | {name}' for name in col_names)
                else:
                    new_cells = "".join(f"\n! {name}" for name in col_names)
            else:
                new_cells = "\n|" * len(col_names)

            valid[-1].value = valid[-1].value + new_cells

        # Re-parse so wikitextparser registers the new cells
        table_str = table.string
        table.string = table_str

    # ==============================================================
    # Update a single table
    # ==============================================================

    def update_table(
        self,
        table: wtp.Table,
        rows: dict[str, Any],
        table_headers_to_row_key: dict[str, str],
        replace_values: bool = False,
        add_missing_headers: bool = True,
    ) -> WtpTable:
        wtp_table = WtpTable.load(table)

        if add_missing_headers and wtp_table.rows:
            missing = self._missing_headers(wtp_table, list(table_headers_to_row_key))
            if missing:
                self.add_columns_at_end(table, missing)
                wtp_table = WtpTable.load(table)

        for row in wtp_table.data_rows:
            row_data = self._extract_row_data(row, rows)
            if row_data is None:
                continue

            for header, row_key in table_headers_to_row_key.items():
                cell = row.get(header)
                if cell is None or row_key not in row_data:
                    continue

                new_value = str(row_data[row_key] if row_data[row_key] is not None else "").strip()
                if not new_value and not replace_values:
                    continue

                if cell.is_empty or replace_values:
                    cell.value = f" {new_value}" if new_value else ""

        return wtp_table

    # ==============================================================
    # Main entry point
    # ==============================================================

    def update_wikitable_data(
        self,
        rows: dict[str, Any],
        wikitext: str,
        table_headers_to_row_key: dict[str, str],
        replace_values: bool = False,
        add_missing_headers: bool = True,
    ) -> str:
        parsed = wtp.parse(wikitext)

        for table in parsed.get_tables(recursive=False):
            self.update_table(
                table,
                rows,
                table_headers_to_row_key,
                replace_values=replace_values,
                add_missing_headers=add_missing_headers,
            )

        return parsed.string


__all__ = ["WtpTableUpdater"]
