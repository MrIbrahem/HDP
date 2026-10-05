"""
Fill wikitext tables from a `rows` dict, built on top of WtpTable.
"""

from __future__ import annotations

import logging

import wikitextparser as wtp
from wikitextparser._cell import Cell

from .wtp_row_cell import HEADER_PATH_SEP
from .wtp_table import WtpTable

logger = logging.getLogger(__name__)


class WtpTableManager:

    def __init__(self, span: bool = True) -> None:
        """
        ``span=False`` is required for structural edits so the literal cell
        grid is used (not the colspan/rowspan-flattened view).
        """
        self.span = span

    def load_table_cells(self, table: wtp.Table) -> list[list[Cell]] | None:
        """
        Safely retrieve cells from a wikitext table.
        """
        try:
            return table.cells(span=self.span)
        except Exception as exc:
            logger.error("Error getting table cells: %s", exc)
            return None

    def has_header(self, table: wtp.Table, col_name: str) -> bool:
        """
        Check if a column named `col_name` exists in the table header.
        """
        if not table:
            logger.info("no table found")
            return False

        wtp_table = WtpTable.load(table)
        return wtp_table.has_header(col_name)

    def add_columns(
        self,
        table: wtp.Table,
        col_names: list[str],
        position: str = "after_first",
        default_value: str = "",
    ) -> bool:
        """
        Append columns at the end of the table.

        Uses the literal cell grid (span=False). With a multi-row header the
        new header cell is written once, in the first header row, with
        ``rowspan=<number of header rows>``; other header rows are untouched.
        """
        if position == "":
            position = "after_first"

        if not table or not col_names:
            return False

        # grid = table.cells(span=False)
        grid = self.load_table_cells(table)
        if not grid:
            return False

        n_header_rows = WtpTable._count_header_rows(grid)

        for r_idx, row in enumerate(grid):
            if not row:
                continue

            # Filter valid cells in current row
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
                formatted_val = f" {default_value}" if default_value else ""
                new_cells = f"\n|{formatted_val}" * len(col_names)

            # Pick target cell to attach the new column delimiter
            target = valid[0] if position == "after_first" else valid[-1]
            target.value = target.value + new_cells

        logger.info("Added column %r across %s rows", col_names, len(grid))

        # NOTE: Adding new cell delimiters (\n! or \n|) directly into the cell value
        # alters the table structure dynamically. We must re-assign 'table.string'
        # to force wikitextparser to re-parse the text and register the new cells.
        # Otherwise, the internal span tracking breaks, causing the following error
        # in wikitextparser/_table.py:261 (in cells insort_right):
        # TypeError: '<' not supported between instances of 'bytearray' and 'NoneType'

        table_str = table.string
        table.string = table_str
        return True

    def add_column(
        self,
        table: wtp.Table,
        col_name: str,
        position: str = "after_first",
        default_value: str = "",
    ) -> bool:
        return self.add_columns(
            table=table,
            col_names=[col_name],
            position=position,
            default_value=default_value,
        )

    # ==============================================================
    # Adding missing columns
    # ==============================================================

    @staticmethod
    def _missing_headers(wtp_table: WtpTable, wanted: list[str]) -> list[str]:
        """
        Headers to add. A path header ("A > B") cannot be created (we cannot
        invent the parent group), so it is only warned about and skipped.
        """
        missing = []
        for header in wanted:
            if wtp_table.has_header(header):
                continue
            if HEADER_PATH_SEP in header:
                logger.warning("Header path %r not found in table; skipped", header)
                continue

            missing.append(header)
        return missing

    def ensure_columns_exists(
        self,
        *,
        table: wtp.Table,
        cols_name: list[str],
        position: str = "after_first",
        default_value: str = "",
    ) -> None:
        """
        Verifies column presence and injects its structure if missing.
        """
        wtp_table = WtpTable.load(table)

        if wtp_table.rows:
            missing = self._missing_headers(wtp_table, cols_name)
            if missing:
                self.add_columns(
                    table,
                    missing,
                    position,
                    default_value,
                )


__all__ = [
    "WtpTableManager",
]
