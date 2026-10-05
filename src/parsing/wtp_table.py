"""
Parse a wikitext table into rows, where every cell knows its header name.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass, field

import wikitextparser as wtp
from wikitextparser._cell import Cell

logger = logging.getLogger(__name__)


@dataclass
class WtpCell:
    """A table cell together with the header (column name) it belongs to."""

    cell: Cell
    header: str  # leaf header text, e.g. "Global"
    index: int  # 0-based column index in the (span-expanded) grid
    header_path: tuple[str, ...] = ()  # e.g. ("User Edits", "Global")

    @property
    def value(self) -> str:
        return self.cell.value

    @value.setter
    def value(self, new_value: str) -> None:
        self.cell.value = new_value

    @property
    def is_empty(self) -> bool:
        return not self.cell.value or not self.cell.value.strip()


@dataclass
class WtpRow:
    """One table row: a list of WtpCell."""

    cells: list[WtpCell] = field(default_factory=list)
    is_header: bool = False

    def get(self, header: str) -> WtpCell | None:
        """Return the first cell whose header equals `header` (case-insensitive)."""
        target = header.strip().lower()
        for c in self.cells:
            if c.header.strip().lower() == target:
                return c
        return None

    def to_dict(self) -> dict[str, str]:
        """header (lowercase) -> stripped cell value."""
        return {c.header.strip().lower(): c.value.strip() for c in self.cells}


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
    def load_text(cls, text: str, span: bool = True) -> WtpTable:
        table = wtp.Table(text)
        return cls.load(table, span=span)

    @classmethod
    def load(cls, table: wtp.Table, span: bool = True) -> WtpTable:
        """
        Take a wikitext table (string or wtp.Table) and build a WtpTable.

        * Header rows = the leading rows made only of header cells (`!`).
          With `span=True` rowspan/colspan cells are expanded, so every row
          has the same number of columns and each column gets a header.
        * The header of a column is the *last* header row's text for that
          column (the "leaf" header). The full chain is in `header_path`.
        * Header rows themselves are also included (is_header=True).
        """
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

    def __iter__(self) -> Iterator[WtpRow]:
        return iter(self.rows)

    def __len__(self) -> int:
        return len(self.rows)


__all__ = [
    "WtpCell",
    "WtpRow",
    "WtpTable",
]
