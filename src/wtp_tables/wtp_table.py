"""
Parse a wikitext table into rows, where every cell knows its header name.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass, field

import wikitextparser as wtp
from wikitextparser._cell import Cell

from .wtp_row_cell import WtpRow, WtpCell

logger = logging.getLogger(__name__)


@dataclass
class WtpTable:
    """A wikitext table as a list of WtpRow."""

    table: wtp.Table
    rows: list[WtpRow] = field(default_factory=list)
    span: bool = True

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, table: wtp.Table | str, span: bool = True) -> WtpTable:
        """
        Take a wikitext table (string or wtp.Table) and build a WtpTable.

        * Header rows = the leading rows made only of header cells (`!`).
          With `span=True` rowspan/colspan cells are expanded, so every row
          has the same number of columns and each column gets a header.
        * The header of a column is the *last* header row's text for that
          column (the "leaf" header). The full chain is in `header_path`.
        * Header rows themselves are also included (is_header=True).
        """
        if isinstance(table, str):
            table = wtp.Table(table)

        try:
            grid = table.cells(span=span)
        except Exception as exc:  # wikitextparser can fail on malformed tables
            logger.error("Error getting table cells: %s", exc)
            return cls(table=table, rows=[], span=span)

        if not grid:
            return cls(table=table, rows=[], span=span)

        n_header_rows = cls._count_header_rows(grid)
        paths = cls._build_header_paths(grid[:n_header_rows], grid)

        rows: list[WtpRow] = []
        for r_idx, row in enumerate(grid):
            wtp_cells = []
            for col, cell in enumerate(row):
                if cell is None:
                    continue
                path = paths[col] if col < len(paths) else ()
                wtp_cells.append(
                    WtpCell(
                        cell=cell,
                        header=path[-1] if path else "",
                        index=col,
                        header_path=path,
                    )
                )
            rows.append(WtpRow(cells=wtp_cells, is_header=r_idx < n_header_rows))

        return cls(table=table, rows=rows, span=span)

    @staticmethod
    def _count_header_rows(grid: list[list[Cell]]) -> int:
        count = 0
        for row in grid:
            valid = [c for c in row if c is not None]
            if valid and all(c.is_header for c in valid):
                count += 1
            else:
                break
        return count

    @staticmethod
    def _build_header_paths(
        header_rows: list[list[Cell]],
        grid: list[list[Cell]],
    ) -> list[tuple[str, ...]]:
        n_cols = max((len(r) for r in grid), default=0)
        paths: list[tuple[str, ...]] = []
        for col in range(n_cols):
            path: list[str] = []
            for hrow in header_rows:
                cell = hrow[col] if col < len(hrow) else None
                if cell is None:
                    continue
                text = cell.value.strip() if cell.value else ""
                if text and (not path or path[-1] != text):  # skip rowspan repeats
                    path.append(text)
            paths.append(tuple(path))
        return paths

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def header_rows(self) -> list[WtpRow]:
        return [r for r in self.rows if r.is_header]

    @property
    def data_rows(self) -> list[WtpRow]:
        return [r for r in self.rows if not r.is_header]

    @property
    def headers(self) -> list[str]:
        """Leaf header of every column, in order."""
        if not self.rows:
            return []
        return [c.header for c in self.rows[0].cells]

    def has_header(self, header: str) -> bool:
        """True if `header` (leaf or path) matches at least one column."""
        return bool(self.rows) and bool(self.rows[0].get_all(header))

    def __iter__(self) -> Iterator[WtpRow]:
        return iter(self.rows)

    def __len__(self) -> int:
        return len(self.rows)


__all__ = [
    "WtpTable",
]
