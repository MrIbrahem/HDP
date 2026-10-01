"""
"""

from __future__ import annotations
from dataclasses import dataclass

@dataclass
class TableRow:
    data: list[str]

    def build(self) -> list[str]:
        """
        Render a fresh MediaWiki table row from row data.
        """
        raise NotImplementedError

@dataclass
class TableObject:
    rows: list[TableRow]
    heads: list[str]

    def build(self) -> str:
        """
        Render a fresh MediaWiki table from rows.
        """
        lines = ['{| class="wikitable sortable"']

        lines.extend(f"! {x}" for x in self.heads if x)

        for row in self.rows:
            lines.extend(row.build())

        lines.append("|}")

        return "\n".join(lines)

    @classmethod
    def load(
        cls,
        rows: list[TableRow] | None = None,
        heads: list[str] | None = None
    ) -> TableObject:
        return cls(
            rows=rows or [],
            heads=heads or []
        )


__all__ = [
    "TableRow",
    "TableObject",
]
