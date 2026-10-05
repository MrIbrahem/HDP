"""
Application table model and MediaWiki table rendering.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .application_row import ApplicationRow

EMPTY_TABLE_HEADER = """
|-
! rowspan="2" |Application
! rowspan="2" |Latest update
! rowspan="2" |User
! rowspan="2" |Country
! rowspan="2" |Extended rights
! colspan="2" |User Edits
! colspan="2" |Last 3 months edits
! rowspan="2" |Account age
! rowspan="2" |Home Wiki
! rowspan="2" |Approved
|-
! Global no WD
! WD
! Global no WD
! WD
"""

EMPTY_TABLE_ROW = """|-
| {page_link}
| {last_update}
| {user_link}
| {country}
| {extended_rights}
| {global_without_wikidata_str}
| {wikidata_editcount_str}
| {recent_editcount_str}
| {recent_wikidata_editcount_str}
| {age}
| {home_wiki}
| {approved}
"""


@dataclass(frozen=True, slots=True)
class ApplicationColumn:
    """
    Define a single column in the application table.

    Attributes:
        header: The MediaWiki table header.
        header_alts: header alternative names.
        row_key: The key used to retrieve the value from the row data.
        optional: Whether the column can be hidden when rendering.
    """

    header: str
    row_key: str
    optional: bool = False
    header_alts: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Default table columns
# ---------------------------------------------------------------------------

DEFAULT_COLUMNS: tuple[ApplicationColumn, ...] = (
    ApplicationColumn(
        header="Application",
        row_key="page_link",
        header_alts=["Page"],
    ),
    ApplicationColumn(
        header="Latest update",
        row_key="last_update",
        header_alts=["Last edited to application"],
    ),
    ApplicationColumn(
        header="User",
        row_key="user_link",
        header_alts=[],
    ),
    ApplicationColumn(
        header="Country",
        row_key="country",
        header_alts=[],
    ),
    ApplicationColumn(
        header="Extended rights",
        row_key="extended_rights",
        header_alts=[],
    ),
    ApplicationColumn(
        header="User Edits > Global",
        row_key="global_editcount_str",
        header_alts=["Global edits without wikidata"],
    ),
    ApplicationColumn(
        header="User Edits > Global no WD",
        row_key="global_without_wikidata_str",
        header_alts=["Global edits without wikidata"],
    ),
    ApplicationColumn(
        header="User Edits > WD",
        row_key="wikidata_editcount_str",
        header_alts=["Wikidata edits"],
    ),
    ApplicationColumn(
        header="Last 3 months edits > Global no WD",
        row_key="recent_editcount_str",
        header_alts=["Edits in last 3 months"],
    ),
    ApplicationColumn(
        header="Last 3 months edits > WD",
        row_key="recent_wikidata_editcount_str",
        header_alts=["Wikidata edits in last 3 months"],
    ),
    ApplicationColumn(
        header="Account age",
        row_key="age",
        header_alts=["Age of account"],
    ),
    ApplicationColumn(
        header="Home Wiki",
        row_key="home_wiki",
        header_alts=[],
    ),
    ApplicationColumn(
        header="Approved",
        row_key="approved",
        header_alts=[],
    ),
    ApplicationColumn(
        header="Last edit",
        row_key="last_edit",
        header_alts=[],
        optional=True,
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

    def build_wikitable_template(self, add_last_edit: bool = False) -> str:
        """
        Render the applications as a MediaWiki table.
        """

        lines = [
            '{| class="wikitable sortable"',
            EMPTY_TABLE_HEADER.strip(),
        ]

        if add_last_edit:
            lines.append("! Last edit")

        template = EMPTY_TABLE_ROW
        if add_last_edit:
            template = f"{template}\n| {{last_edit}}"

        for row in self.rows:
            row_str = row.build_row_template(template)
            lines.append(row_str.strip())

        lines.append("|}")

        return "\n".join(lines)

    def as_row_dicts(self) -> dict[str, dict[str, str]]:
        """
        Convert rows to the dictionary shape expected by the table updater.
        """
        return {row.full_title: row.to_table_dict(self.unknown) for row in self.rows}

    def headers_to_row_keys(self, add_last_edit: bool = True) -> dict[str, str]:
        """
        Return a mapping between table headers and row data keys.

        The mapping is derived from ``columns`` to avoid maintaining
        duplicate column definitions.
        """
        data = {column.header: column.row_key for column in self.columns}
        if not add_last_edit:
            data.pop("Last edit", None)
        return data

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
