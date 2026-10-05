"""
Parse a wikitext table into rows, where every cell knows its header name.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any

import wikitextparser as wtp
from wikitextparser._cell import Cell

from .wtp_row_cell import HEADER_PATH_SEP, WtpCell, WtpRow

logger = logging.getLogger(__name__)


@dataclass
class WtpTableBuild:

    # ------------------------------------------------------------------
    # Building wikitext from data
    # ------------------------------------------------------------------

    @staticmethod
    def _to_path(header: str | Sequence[str]) -> tuple[str, ...]:
        if isinstance(header, str):
            parts = [p.strip() for p in header.split(HEADER_PATH_SEP)]
        else:
            parts = [str(p).strip() for p in header]
        if not parts or any(not p for p in parts):
            raise ValueError(f"Invalid header: {header!r}")
        return tuple(parts)

    @staticmethod
    def _header_lines(paths: list[tuple[str, ...]]) -> list[str]:
        depth = max(len(p) for p in paths)
        lines: list[str] = []

        def fmt(attr: str, text: str) -> str:
            return f"! {attr}| {text}" if attr else f"! {text}"

        for level in range(depth):
            cells: list[str] = []
            i = 0
            while i < len(paths):
                path = paths[i]
                if len(path) <= level:  # covered by a rowspan from above
                    i += 1
                    continue

                if len(path) == level + 1:  # leaf: never merged with neighbours
                    rowspan = depth - level
                    attr = f'rowspan="{rowspan}" ' if rowspan > 1 else ""
                    cells.append(fmt(attr, path[level]))
                    i += 1
                    continue

                j = i + 1  # group: adjacent columns sharing the same parent prefix
                while j < len(paths) and len(paths[j]) > level + 1 and paths[j][: level + 1] == path[: level + 1]:
                    j += 1
                attr = f'colspan="{j - i}" ' if j - i > 1 else ""
                cells.append(fmt(attr, path[level]))
                i = j

            if level > 0:
                lines.append("|-")
            lines.extend(cells)

        return lines

    @staticmethod
    def _fmt_value(value: Any) -> str:
        return "" if value is None else str(value).strip()

    @classmethod
    def _row_values(cls, row: Sequence[Any] | dict[str, Any], paths: list[tuple[str, ...]]) -> list[str]:
        n = len(paths)

        if isinstance(row, dict):
            values = [""] * n
            for key, value in row.items():
                parts = tuple(p.strip().lower() for p in key.split(HEADER_PATH_SEP))
                idx = next(
                    (
                        i
                        for i, p in enumerate(paths)
                        if len(p) >= len(parts) and tuple(x.lower() for x in p[-len(parts) :]) == parts
                    ),
                    None,
                )
                if idx is None:
                    raise ValueError(f"Unknown header in row: {key!r}")
                values[idx] = cls._fmt_value(value)
            return values

        row = list(row)
        if len(row) > n:
            raise ValueError(f"Row has {len(row)} values but there are only {n} columns")
        return [cls._fmt_value(v) for v in row] + [""] * (n - len(row))

    @classmethod
    def build_wikitext(
        cls,
        headers: Sequence[str | Sequence[str]],
        rows: Iterable[Sequence[Any] | dict[str, Any]],
        attrs: str = 'class="wikitable"',
        caption: str | None = None,
    ) -> str:
        """Same as `build` but returns only the wikitext string."""
        paths = [cls._to_path(h) for h in headers]
        if not paths:
            raise ValueError("headers must not be empty")

        lines = [f"{{| {attrs}".rstrip()]
        if caption:
            lines.append(f"|+ {caption}")
        lines.extend(cls._header_lines(paths))

        for row in rows:
            lines.append("|-")
            lines.extend(f"| {v}" if v else "|" for v in cls._row_values(row, paths))

        lines.append("|}")
        return "\n".join(lines)


@dataclass
class WtpTable:
    """A wikitext table as a list of WtpRow."""

    table: wtp.Table
    rows: list[WtpRow] = field(default_factory=list)
    span: bool = True

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

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

    @classmethod
    def build_wikitext(
        cls,
        headers: Sequence[str | Sequence[str]],
        rows: Iterable[Sequence[Any] | dict[str, Any]],
        attrs: str = 'class="wikitable"',
        caption: str | None = None,
    ) -> str:
        return WtpTableBuild.build_wikitext(headers, rows, attrs=attrs, caption=caption)

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

    @classmethod
    def build(
        cls,
        headers: Sequence[str | Sequence[str]],
        rows: Iterable[Sequence[Any] | dict[str, Any]],
        attrs: str = 'class="wikitable"',
        caption: str | None = None,
        span: bool = True,
    ) -> WtpTable:
        """
        Build a table from data and return it as a WtpTable.

        :param headers: one entry per column. Either a plain name ("Age") or a
            path, as ``"Parent > Child"`` or ``("Parent", "Child")``. Paths of
            different depth produce a multi-row header; colspan/rowspan are
            generated automatically.
        :param rows: each row is a list of values (in column order) or a dict
            ``{header: value}`` (header = plain name or path; matched like
            WtpRow.get, first matching column). Missing values are empty.
        :param attrs: table attributes, e.g. 'class="wikitable sortable"'.
        :param caption: optional table caption.

        Values are inserted as raw wikitext (links, templates...).
        """
        text = WtpTableBuild.build_wikitext(headers, rows, attrs=attrs, caption=caption)
        return cls.load(text, span=span)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def string(self) -> str:
        """Current wikitext of the table (reflects cell edits)."""
        return self.table.string

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
