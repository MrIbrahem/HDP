#!/usr/bin/python3
"""
Module for processing Wikitext tables and dynamically adding missing columns.
"""

import logging

import wikitextparser as wtp
from wikitextparser._cell import Cell

logger = logging.getLogger(__name__)

# ==============================================================================
# PART 1: Structural Manager (Adds Column Header and Default Cells Only)
# ==============================================================================


class WikiTableColumnManager:
    """
    Handles checking, verifying, and inserting column structures into Wikitext tables.
    """

    def load_table_cells(self, table: wtp.Table) -> list[list[Cell]] | None:
        """Safely retrieve cells from a wikitext table."""
        try:
            return table.cells()
        except Exception as exc:
            logger.error(f"Error getting table cells: {exc}")
            return None

    def get_header_index(self, table: wtp.Table) -> dict[str, int]:
        """
        return dict which maps column name (lowercase) to its index (0-based).
        Direct alternative to _build_header_index of yours.
        """
        if not table:
            logger.info("no table found")
            return {}

        all_cells: list[list[Cell]] | None = self.load_table_cells(table)

        if not all_cells:
            return {}

        index_map: dict[str, int] = {}
        for row in all_cells:
            # Skip empty rows or non-header rows
            if not row or row[0] is None or not row[0].is_header:
                continue

            # Inspect header names in the header row
            for idx, cell in enumerate(row):
                if cell:
                    index_map[cell.value.strip().lower()] = idx
            break  # Only inspect the first header row found

        return index_map

    def has_column(self, table: wtp.Table, col_name: str) -> bool:
        """
        Check if a column named `col_name` exists in the table header.
        """
        if not table:
            logger.info("no table found")
            return False

        index_map: dict[str, int] = self.get_header_index(table)
        return col_name.strip().lower() in index_map

    def add_column(
        self,
        table: wtp.Table,
        col_name: str,
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
        if not table:
            return False

        all_cells: list[list[Cell]] | None = self.load_table_cells(table)
        if not all_cells:
            return False

        count = 0
        for row in all_cells:
            if not row:
                continue

            # Filter valid cells in current row
            valid_cells = [c for c in row if c is not None]
            if not valid_cells:
                continue

            count += 1
            is_header = valid_cells[0].is_header

            # Format cell string depending on whether it is a header or data row
            if is_header:
                cell_str = f"\n! {col_name}"
            else:
                formatted_val = f" {default_value}"  # .rstrip()
                cell_str = f"\n|{formatted_val}"

            # Pick target cell to attach the new column delimiter
            target_cell = valid_cells[0] if position == "after_first" else valid_cells[-1]
            target_cell.value = target_cell.value + cell_str

        logger.info(f"Added column '{col_name}' across {count} rows.")

        # NOTE: Adding new cell delimiters (\n! or \n|) directly into the cell value
        # alters the table structure dynamically. We must re-assign 'table.string'
        # to force wikitextparser to re-parse the text and register the new cells.
        # Otherwise, the internal span tracking breaks, causing the following error
        # in wikitextparser/_table.py:261 (in cells insort_right):
        # TypeError: '<' not supported between instances of 'bytearray' and 'NoneType'

        table_str = table.string
        table.string = table_str
        return True

    # ================================
    # Main function
    # ================================

    def ensure_column_exists(
        self,
        *,
        table: wtp.Table,
        col_name: str,
        position: str = "after_first",
        default_value: str = "",
    ) -> bool:
        """Verifies column presence and injects its structure if missing."""
        if self.has_column(table, col_name):
            return False
        return self.add_column(
            table,
            col_name=col_name,
            position=position,
            default_value=default_value,
        )

    def ensure_columns_exists(
        self,
        *,
        table: wtp.Table,
        cols_name: list[str],
        position: str = "after_first",
        default_value: str = "",
    ) -> None:
        """Verifies column presence and injects its structure if missing."""
        index_map: dict[str, int] = self.get_header_index(table)

        for col_name in reversed(cols_name):
            if col_name.strip().lower() not in index_map:
                self.add_column(
                    table=table,
                    col_name=col_name,
                    position=position,
                    default_value=default_value,
                )

        return


__all__ = [
    "WikiTableColumnManager",
]
