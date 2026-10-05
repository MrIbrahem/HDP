"""
Parse a wikitext table into rows, where every cell knows its header name.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from wikitextparser._cell import Cell

logger = logging.getLogger(__name__)

# Separator used to address a header by its path, e.g. "User Edits > WD"
HEADER_PATH_SEP = ">"


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

    def get_all(self, header: str) -> list[WtpCell]:
        """
        All cells matching `header` (case-insensitive).

        `header` is either a plain leaf header ("WD") or a path using
        ``HEADER_PATH_SEP`` ("Last 3 months edits > WD"). A path matches when
        it equals the *end* of the cell's header_path.
        """
        parts = tuple(p.strip().lower() for p in header.split(HEADER_PATH_SEP))
        found = []
        for c in self.cells:
            path = tuple(h.strip().lower() for h in c.header_path) or (c.header.strip().lower(),)
            if len(path) >= len(parts) and path[-len(parts) :] == parts:
                found.append(c)
        return found

    def get(self, header: str) -> WtpCell | None:
        """First cell matching `header` (see get_all), or None."""
        found = self.get_all(header)
        return found[0] if found else None

    def to_dict(self) -> dict[str, str]:
        """header (lowercase) -> stripped cell value."""
        return {c.header.strip().lower(): c.value.strip() for c in self.cells}

__all__ = [
    "HEADER_PATH_SEP",
    "WtpCell",
    "WtpRow",
]
