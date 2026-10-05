"""
Fill wikitext tables from a `rows` dict, built on top of WtpTable.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import wikitextparser as wtp

from .wtp_manager import WtpTableManager
from .wtp_table import HEADER_PATH_SEP, WtpRow, WtpTable

logger = logging.getLogger(__name__)


class WtpTableUpdater:
    """
    Update wikitext tables from a data dictionary.

    Cells are found by header name (leaf header, case-insensitive), so tables
    with multi-row headers (rowspan/colspan) are supported.
    """

    def __init__(self, manager: WtpTableManager | None = None) -> None:
        self.manager = manager or WtpTableManager()

    # ==============================================================
    # Row matching
    # ==============================================================

    @staticmethod
    def _extract_row_data(
        row: WtpRow,
        rows: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Find the row's data in `rows` using the first cell ([[link]] or plain text).
        """
        if not row.cells or row.is_header or row.cells[0].cell.is_header:
            return None

        first_value = row.cells[0].value
        match = re.search(r"\[\[(.*?)\]\]", first_value)
        text = match.group(1).split("|")[0] if match else first_value

        key = text.strip().replace("_", " ")
        return rows.get(key) if key else None

    # ==============================================================
    # Update a single table
    # ==============================================================

    def update_table(
        self,
        table: wtp.Table,
        rows: dict[str, Any],
        table_headers_to_row_key: dict[str, str],
        replace_values: bool = False,
    ) -> WtpTable:
        wtp_table = WtpTable.load(table)

        if wtp_table.rows:
            for header in table_headers_to_row_key:
                if len(wtp_table.rows[0].get_all(header)) > 1:
                    logger.warning(
                        "Header %r is ambiguous (%s columns); using the first. Use a path such as 'Parent %s %s'.",
                        header,
                        len(wtp_table.rows[0].get_all(header)),
                        HEADER_PATH_SEP,
                        header,
                    )

        for row in wtp_table.data_rows:
            row_data = self._extract_row_data(row, rows)
            if row_data is None:
                continue

            self._update_row_cells(
                row=row,
                row_data=row_data,
                table_headers_to_row_key=table_headers_to_row_key,
                replace_values=replace_values,
            )

        return wtp_table

    def _update_row_cells(
        self,
        row: WtpRow,
        row_data: dict[str, Any],
        table_headers_to_row_key: dict[str, str],
        replace_values: bool,
    ) -> None:
        """Updates the row's cells."""
        for header, row_key in table_headers_to_row_key.items():
            cell = row.get(header)
            if cell is None or row_key not in row_data:
                continue

            new_value = str(row_data[row_key] if row_data[row_key] is not None else "").strip()
            if not new_value and not replace_values:
                continue

            if cell.is_empty or replace_values:
                cell.value = f" {new_value}" if new_value else ""

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
        position: str = "after_first",
    ) -> str:
        """rows: list of rows data."""
        parsed = wtp.parse(wikitext)
        tables = parsed.get_tables(recursive=False)

        for table in tables:
            if add_missing_headers:
                self.manager.ensure_columns_exists(
                    table=table,
                    cols_name=list(table_headers_to_row_key.keys()),
                    position=position,
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


__all__ = [
    "WtpTableUpdater",
]
