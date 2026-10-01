"""
"""

from __future__ import annotations
from dataclasses import dataclass

from .application_row import ApplicationRow

# ---------------------------------------------------------------------------
# ApplicationTable
# ---------------------------------------------------------------------------


@dataclass
class ApplicationTable:
    rows: list[ApplicationRow]

    def build_wikitable(
        self,
        add_last_edit: bool = False,
    ) -> str:
        """
        Render a fresh MediaWiki table from rows.
        """
        hr_heads = [
            "Page",
            "Last edited to application",
            "User",
            "Country",
            # "Global edits",
            "Global edits without wikidata",
            "Wikidata edits",
            "Edits in last 3 months",
            "Age of account",
            "Home Wiki",
            "Last edit" if add_last_edit else "",
            "Approved",
        ]

        lines = ['{| class="wikitable sortable"']

        lines.extend(f"! {x}" for x in hr_heads if x)

        for row in self.rows:
            lines.extend(row.build_row(add_last_edit))

        lines.append("|}")

        return "\n".join(lines)

    def as_row_dicts(self) -> dict[str, dict[str, str]]:
        """
        Convert rows to the dict shape the table updater expects
        """
        # Convert rows to the dict shape the table updater expects
        return {row.full_title: row.to_table_dict() for row in self.rows}

    @classmethod
    def load(
        cls,
        rows: list[ApplicationRow] | None = None,
    ) -> ApplicationTable:
        return cls(rows=rows or [])

__all__ = [
    "ApplicationTable",
]
