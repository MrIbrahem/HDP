"""
Wikitext table column management and data updates.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import wikitextparser as wtp
from wikitextparser._cell import Cell

logger = logging.getLogger(__name__)


# ===========================================================================
# Structural manager — add missing columns
# ===========================================================================


class WikiTableColumnManager:
    """Check, verify, and insert column structures into wikitext tables."""

    def load_table_cells(
        self,
        table: wtp.Table,
        span: bool = True,
    ) -> list[list[Cell]] | None:
        """
        Safely retrieve cells.

        ``span=False`` is required for structural edits so the literal cell
        grid is used (not the colspan/rowspan-flattened view).
        """
        try:
            return table.cells(span=span)
        except Exception as exc:
            logger.error("Error getting table cells: %s", exc)
            return None

    def _get_header_row(self, table: wtp.Table) -> list[Cell]:
        all_cells = self.load_table_cells(table)
        if not all_cells:
            return []
        for row in all_cells:
            if not row or row[0] is None or not row[0].is_header:
                continue
            return [c for c in row if c is not None]
        return []

    def has_column(self, table: wtp.Table, col_name: str) -> bool:
        if not table:
            return False
        target = col_name.strip().lower()
        for idx, cell in enumerate(self._get_header_row(table), start=1):
            if cell.value.strip().lower() == target:
                logger.info("Header has %r in column %s", col_name, idx)
                return True
        return False

    def get_header_index(self, table: wtp.Table) -> dict[str, int]:
        """Map header text (lowercase, stripped) → 0-based column index."""
        header_row = self._get_header_row(table)
        return {cell.value.strip().lower(): idx for idx, cell in enumerate(header_row)}

    def add_column(
        self,
        table: wtp.Table,
        col_name: str,
        position: str = "after_first",
        default_value: str = "",
    ) -> bool:
        """
        Inject a column header and default cells across all rows.

        ``position``: ``"after_first"`` or ``"end"``.
        """
        if not table:
            return False

        all_cells = self.load_table_cells(table)
        if not all_cells:
            return False

        count = 0
        for row in all_cells:
            if not row:
                continue
            valid = [c for c in row if c is not None]
            if not valid:
                continue

            count += 1
            is_header = valid[0].is_header
            if is_header:
                cell_str = f"\n! {col_name}"
            else:
                cell_str = f"\n| {default_value}"

            target = valid[0] if position == "after_first" else valid[-1]
            target.value = target.value + cell_str

        logger.info("Added column %r across %s rows", col_name, count)

        # Force re-parse so internal span tracking stays valid
        table.string = table.string
        return True

    def ensure_column_exists(
        self,
        *,
        table: wtp.Table,
        col_name: str,
        position: str = "after_first",
        default_value: str = "",
    ) -> bool:
        """Return True if the column was added, False if it already existed."""
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
        # Reverse so insertion order after_first preserves intended sequence
        for col_name in reversed(cols_name):
            if not self.has_column(table, col_name):
                self.add_column(
                    table=table,
                    col_name=col_name,
                    position=position,
                    default_value=default_value,
                )


# ===========================================================================
# Data updater — fill cells from a rows dict
# ===========================================================================


class WikiTableDataUpdater:
    """
    Update wikitext table cells from a ``{page_title: row_data}`` mapping.
    """

    def __init__(self, manager: WikiTableColumnManager | None = None) -> None:
        self.manager = manager or WikiTableColumnManager()

    def update_table(
        self,
        table: wtp.Table,
        rows: dict[str, Any],
        table_headers_to_row_key: dict[str, str],
        replace_values: bool = False,
    ) -> None:
        all_rows = table.cells()
        if not all_rows:
            return

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
        if not row or row[0] is None or row[0].is_header:
            return None

        first_value = row[0].value
        match = re.search(r"\[\[(.*?)\]\]", first_value)
        if not match:
            return None

        link = match.group(1).split("|")[0].strip().replace("_", " ")
        return rows.get(link)

    def _update_row_cells(
        self,
        row: list[Cell],
        row_data: dict[str, Any],
        header_index: dict[str, int],
        table_headers_to_row_key: dict[str, str],
        replace_values: bool,
    ) -> None:
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

    def update_wikitable_data(
        self,
        rows: dict[str, Any],
        wikitext: str,
        table_headers_to_row_key: dict[str, str],
        replace_values: bool = False,
        add_missing_headers: bool = True,
    ) -> str:
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

        return parsed.string


# ---------------------------------------------------------------------------
# Module-level convenience (matches old public API)
# ---------------------------------------------------------------------------


def update_wikitable_data(
    rows: dict[str, Any],
    wikitext: str,
    table_headers_to_row_key: dict[str, str],
    replace_values: bool = False,
    add_missing_headers: bool = True,
) -> str:
    return WikiTableDataUpdater().update_wikitable_data(
        rows=rows,
        wikitext=wikitext,
        table_headers_to_row_key=table_headers_to_row_key,
        replace_values=replace_values,
        add_missing_headers=add_missing_headers,
    )


__all__ = [
    "WikiTableColumnManager",
    "WikiTableDataUpdater",
    "update_wikitable_data",
]
