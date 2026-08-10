#!/usr/bin/python3
"""
Module for processing Wikitext tables and dynamically adding missing columns.
"""

import logging
import wikitextparser as wtp
from wikitextparser._cell import Cell

logger = logging.getLogger(__name__)


class WikiTableColumnManager:
    """Manages checking, verifying, and inserting columns into Wikitext tables."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.parsed = wtp.parse(self.text)

    def _load_table_cells(self, table: wtp.Table) -> list[list[Cell]] | None:
        """Safely retrieve table cells."""
        try:
            return table.cells()
        except Exception as exc:
            logger.error(f"Error getting cells: {exc}")
            return None

    def has_column(self, table: wtp.Table, col_name: str) -> bool:
        """
        Check if a column named `col_name` exists in the table header.
        """
        all_cells: list[list[Cell]] | None = self._load_table_cells(table)

        if not all_cells:
            return False

        for row in all_cells:
            # Skip empty rows or non-header rows
            if not row or row[0] is None or not row[0].is_header:
                continue

            # Inspect header names in the header row
            for numb, cell in enumerate(row, start=1):
                if cell and cell.value.strip().lower() == col_name.strip().lower():
                    logger.info(f"header has {col_name}: in column {numb}")
                    return True
            break  # Only inspect the first header row found

        return False

    def add_column(
        self,
        table: wtp.Table,
        col_name: str,
        default_value: str = "",
        position: str = "end",
    ) -> bool:
        """
        Add a new column to the table with customizable cells across all rows.

        :param table: wikitextparser Table object
        :param col_name: Name of the column to add (e.g., 'Country', 'R', 'Status')
        :param default_value: Default value for data row cells (defaults to empty string)
        :param position: Insertion position:
                         - 'end': Append to the end of the table (after the last cell)
                         - 'after_first': Insert immediately after the first column
        """
        all_cells: list[list[Cell]] | None = self._load_table_cells(table)
        if not all_cells:
            return False

        count = 0
        for row in all_cells:
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
                formatted_val = f" {default_value}".rstrip()
                cell_str = f"\n|{formatted_val}"

            # Determine target cell for appending based on the desired position
            target_cell = (
                valid_cells[0] if position == "after_first" else valid_cells[-1]
            )
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
        col_name: str,
        default_value: str = "",
        position: str = "end",
        table_index: int | None = None,
    ) -> str:
        """
        Main method: Verifies column presence and adds it if missing.

        :param col_name: Column header to verify/add.
        :param default_value: Initial value for newly added data cells.
        :param position: 'end' to append at the end, or 'after_first' to insert after 1st column.
        :param table_index: Specific table index to process (processes all if None).
        """
        if not self.parsed.tables:
            logger.info("No tables found in the text.")
            return self.text

        # Target specific table or all tables
        if table_index is not None:
            if table_index < len(self.parsed.tables):
                target_tables = [self.parsed.tables[table_index]]
            else:
                logger.warning(f"Table index {table_index} out of range.")
                return self.text
        else:
            target_tables = self.parsed.tables

        modified = False
        for tbl in target_tables:
            if not self.has_column(tbl, col_name):
                logger.info(f"Column '{col_name}' missing; adding now...")
                if self.add_column(tbl, col_name, default_value, position):
                    modified = True
            else:
                logger.info(f"Column '{col_name}' already exists.")

        if modified:
            self.text = self.parsed.string

        return self.text


# ==========================================
# Convenience Function
# ==========================================

def ensure_column_in_wikitext(
    text: str,
    col_name: str,
    default_value: str = "",
    position: str = "end",
) -> str:
    """
    Helper function that accepts wikitext and column name, returning updated text.
    """
    manager = WikiTableColumnManager(
        text=text,
    )
    return manager.ensure_column_exists(col_name, default_value, position)


__all__ = [
    "WikiTableColumnManager",
    "ensure_column_in_wikitext",
]
