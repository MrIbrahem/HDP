""" """

from __future__ import annotations

from dataclasses import dataclass

from .application_row import ApplicationRow

# ---------------------------------------------------------------------------
# Header ↔ row-key mapping used when updating existing wikitables
# ---------------------------------------------------------------------------

TABLE_HEADERS_TO_ROW_KEY: dict[str, str] = {
    "Page": "page_link",
    "Last edited to application": "last_update",
    "User": "user_link",
    "Country": "country",
    "Global edits": "global_editcount_str",
    "Global edits without wikidata": "global_without_wikidata_str",
    "Wikidata edits": "wikidata_editcount_str",
    "Edits in last 3 months": "recent_editcount_str",
    "Wikidata edits in last 3 months": "recent_wikidata_editcount_str",
    "Age of account": "age",
    "Home Wiki": "home_wiki",
    "Last edit": "last_edit",
}

# ---------------------------------------------------------------------------
# ApplicationTable
# ---------------------------------------------------------------------------


@dataclass
class ApplicationTable:
    rows: list[ApplicationRow]
    unknown: str = ""

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
            "Wikidata edits in last 3 months",
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
        return {row.full_title: row.to_table_dict(self.unknown) for row in self.rows}

    @classmethod
    def load(
        cls,
        rows: list[ApplicationRow] | None = None,
        unknown: str = "",
    ) -> ApplicationTable:
        return cls(rows=rows or [], unknown=unknown)


__all__ = [
    "ApplicationTable",
    "TABLE_HEADERS_TO_ROW_KEY",
]
