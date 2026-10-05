"""
Module for processing Wikitext tables and dynamically adding missing columns.
"""

from __future__ import annotations

import logging

import wikitextparser as wtp
from wikitextparser._cell import Cell

logger = logging.getLogger(__name__)


# ===========================================================================
# PART 1: Structural Manager (Adds Column Header and Default Cells Only)
# ===========================================================================


class WikiTableColumnManager:
    """
    Check, verify, and insert column structures into wikitext tables.
    """

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

    def _get_header_row(self, table: wtp.Table) -> list[Cell]:
        """Returns the first header row's non-None cells, or [] if none found."""
        all_cells = self.load_table_cells(table)
        if not all_cells:
            return []

        for row in all_cells:
            # Skip empty rows or non-header rows
            if not row or row[0] is None or not row[0].is_header:
                continue
            return [c for c in row if c is not None]

        return []

    def _get_header_row_new(self, table: wtp.Table) -> list[Cell]:
        """Returns the first header row's non-None cells, or [] if none found."""
        if self.span:
            return self._get_header_row(table)

        all_cells = self.load_table_cells(table)
        if not all_cells:
            return []

        rows = []
        for row in all_cells:
            # Skip empty rows or non-header rows
            if not row or row[0] is None or not row[0].is_header:
                continue
            rows.extend([c for c in row if c is not None])

        return rows

    def has_header(self, table: wtp.Table, col_name: str) -> bool:
        """
        Check if a column named `col_name` exists in the table header.
        """
        if not table:
            logger.info("no table found")
            return False

        header_row = self._get_header_row(table)
        target = col_name.strip().lower()

        for idx, cell in enumerate(header_row, start=1):
            if cell.value.strip().lower() == target:
                logger.debug("Header has %r in column %s", col_name, idx)
                return True
        return False

    def get_header_index(self, table: wtp.Table) -> dict[str, int]:
        """Map header text (lowercase, stripped) → 0-based column index."""
        header_row = self._get_header_row(table)
        return {cell.value.strip().lower(): idx for idx, cell in enumerate(header_row)}

    def add_columns(
        self,
        table: wtp.Table,
        col_names: list[str],
        position: str = "after_first",
        default_value: str = "",
    ) -> bool:
        """
        Inject a column header and empty/default cells across all rows.

        :param table: wikitextparser Table instance.
        :param col_name: Column title (e.g. 'R', 'Country').
        :param position: 'after_first' to insert after 1st column, or 'end' for last.
        :param default_value: Default cell content for data rows.
        """
        if position == "":
            position = "after_first"

        if not table or not col_names:
            return False

        # grid = table.cells(span=False)
        grid = self.load_table_cells(table)
        if not grid:
            return False

        for _r_idx, row in enumerate(grid):
            if not row:
                continue

            # Filter valid cells in current row
            valid = [c for c in row if c is not None]
            if not valid:
                continue

            # Format cell string depending on whether it is a header or data row
            if valid[0].is_header:
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

    def _missing_headers(self, table: wtp.Table, wanted: list[str]) -> list[str]:
        """ """
        missing = []
        for header in wanted:
            if self.has_header(table, header):
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
        # Reverse so insertion order after_first preserves intended sequence
        missing = self._missing_headers(table, cols_name)
        if missing:
            self.add_columns(
                table,
                missing,
                position,
                default_value,
            )


__all__ = [
    "WikiTableColumnManager",
]
