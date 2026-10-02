"""
Application table model and MediaWiki table rendering.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .application_row import ApplicationRow


@dataclass(frozen=True, slots=True)
class ApplicationColumn:
    """
    Define a single column in the application table.

    Attributes:
        header: The MediaWiki table header.
        row_key: The key used to retrieve the value from the row data.
        optional: Whether the column can be hidden when rendering.
    """

    header: str
    row_key: str
    optional: bool = False


# ---------------------------------------------------------------------------
# Default table columns
# ---------------------------------------------------------------------------

DEFAULT_COLUMNS: tuple[ApplicationColumn, ...] = (
    ApplicationColumn(
        header="Page",
        row_key="page_link",
    ),
    ApplicationColumn(
        header="Last edited to application",
        row_key="last_update",
    ),
    ApplicationColumn(
        header="User",
        row_key="user_link",
    ),
    ApplicationColumn(
        header="Country",
        row_key="country",
    ),
    ApplicationColumn(
        header="Global edits without wikidata",
        row_key="global_without_wikidata_str",
    ),
    ApplicationColumn(
        header="Wikidata edits",
        row_key="wikidata_editcount_str",
    ),
    ApplicationColumn(
        header="Edits in last 3 months",
        row_key="recent_editcount_str",
    ),
    ApplicationColumn(
        header="Wikidata edits in last 3 months",
        row_key="recent_wikidata_editcount_str",
    ),
    ApplicationColumn(
        header="Age of account",
        row_key="age",
    ),
    ApplicationColumn(
        header="Home Wiki",
        row_key="home_wiki",
    ),
    ApplicationColumn(
        header="Last edit",
        row_key="last_edit",
        optional=True,
    ),
    ApplicationColumn(
        header="Approved",
        row_key="approved",
    ),
)


@dataclass
class ApplicationTable:
    """
    Represent a collection of applications as a MediaWiki table.

    Attributes:
        rows: Application rows to render.
        columns: Columns used by the table.
        unknown: Fallback value used when row data is unavailable.
    """

    rows: list[ApplicationRow]
    columns: list[ApplicationColumn] = field(default_factory=lambda: list(DEFAULT_COLUMNS))
    unknown: str = ""

    def build_wikitable(self, add_last_edit: bool = False) -> str:
        """
        Render the applications as a MediaWiki table.
        """
        columns = self._get_visible_columns(add_last_edit)

        lines = ['{| class="wikitable sortable"']

        lines.extend(f"! {column.header}" for column in columns)

        for row in self.rows:
            lines.extend(row.build_row(add_last_edit))

        lines.append("|}")

        return "\n".join(lines)

    def as_row_dicts(self) -> dict[str, dict[str, str]]:
        """
        Convert rows to the dictionary shape expected by the table updater.
        """
        return {row.full_title: row.to_table_dict(self.unknown) for row in self.rows}

    @property
    def headers_to_row_keys(self) -> dict[str, str]:
        """
        Return a mapping between table headers and row data keys.

        The mapping is derived from ``columns`` to avoid maintaining
        duplicate column definitions.
        """
        return {column.header: column.row_key for column in self.columns}

    def _get_visible_columns(
        self,
        add_last_edit: bool,
    ) -> list[ApplicationColumn]:
        """
        Return columns that should be included in the rendered table.
        """
        return [column for column in self.columns if not column.optional or add_last_edit]

    @classmethod
    def load(
        cls,
        rows: list[ApplicationRow] | None = None,
        columns: list[ApplicationColumn] | None = None,
        unknown: str = "",
    ) -> ApplicationTable:
        """
        Create an ApplicationTable from optional rows and columns.
        """
        return cls(
            rows=rows or [],
            columns=columns if columns is not None else list(DEFAULT_COLUMNS),
            unknown=unknown,
        )


__all__ = [
    "ApplicationColumn",
    "ApplicationTable",
    "DEFAULT_COLUMNS",
]
