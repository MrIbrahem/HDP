"""
Unit tests for src/wtp_tables/wtp_updater.py module.
"""

import pytest

from src.wtp_tables.wtp_table import WtpTable
from src.wtp_tables.wtp_updater import WtpTableUpdater

HEADERS_TO_KEY = {
    "Application": "page_link",
    "Latest update": "last_update",
    "User": "user_link",
    "Country": "country",
    "Global edits without wikidata": "global_without_wikidata_str",
    "Wikidata edits": "wikidata_editcount_str",
    "Edits in last 3 months": "recent_editcount_str",
    "Wikidata edits in last 3 months": "recent_wikidata_editcount_str",
    "Account age": "age",
    "Home Wiki": "home_wiki",
    "Last edit": "last_edit",
    "Approved": "approved",
}

USERS_ROWS = {
    "Hardware donation program/EYo237": {
        "page_link": "Hardware donation program/EYo237",
        "last_update": "25",
        "user_link": "test",
        "country": "",
        "global_without_wikidata_str": "1",
        "wikidata_editcount_str": "100",
        "recent_editcount_str": "500",
        "recent_wikidata_editcount_str": "200",
        "age": "1",
        "home_wiki": "enwiki",
        "last_edit": "2023-01-01",
        "approved": "Yes",
    }
}


def make_table(link: str = "[[Hardware donation program/EYo237]]", age: str = "") -> str:
    """Two-row header table whose leaf headers match HEADERS_TO_KEY."""
    return (
        '{| class="wikitable sortable"\n'
        '! rowspan="2" | Application\n'
        '! rowspan="2" | Latest update\n'
        '! rowspan="2" | User\n'
        '! rowspan="2" | Country\n'
        '! colspan="2" | Global edits\n'
        '! colspan="2" | Last 3 months edits\n'
        '! rowspan="2" | Account age\n'
        '! rowspan="2" | Home Wiki\n'
        '! rowspan="2" | Last edit\n'
        '! rowspan="2" | Approved\n'
        "|-\n"
        "! Global edits without wikidata\n"
        "! Wikidata edits\n"
        "! Edits in last 3 months\n"
        "! Wikidata edits in last 3 months\n"
        "|-\n"
        f"| {link}\n"
        "|\n"  # Latest update
        "|\n"  # User
        "|\n"  # Country
        "|\n"  # Global edits without wikidata
        "|\n"  # Wikidata edits
        "|\n"  # Edits in last 3 months
        "|\n"  # Wikidata edits in last 3 months
        f"|{' ' + age if age else ''}\n"  # Account age
        "|\n"  # Home Wiki
        "|\n"  # Last edit
        "|\n"  # Approved
        "|-\n"
        "|}"
    )


COMPLEX_WIKITEXT = """
{| class="wikitable sortable"
! rowspan="2" | Application
! rowspan="2" | Latest update
! rowspan="2" |User
! rowspan="2" | Country
! rowspan="2" |Extended rights
! colspan="3" | User Edits
! colspan="2" |Last 3 months edits
! rowspan="2" | Account age
! rowspan="2" | Home Wiki
! rowspan="2" | Approved
|-
!Global
!Global no WD
!WD
!Global no wd
!WD
|-
| User1
| Latest update
|User
|Country
|Extended rights
| Global
| Global no WD
| WD
| Global no wd
|WD
| Account age
|Home Wiki
|Approved
|-
|}"""


@pytest.fixture
def updater() -> WtpTableUpdater:
    return WtpTableUpdater()


def run(updater: WtpTableUpdater, wikitext, **kwargs) -> str:
    return updater.update_wikitable_data(
        rows=USERS_ROWS,
        wikitext=wikitext,
        table_headers_to_row_key=HEADERS_TO_KEY,
        **kwargs,
    )


class TestUpdateMatchingHeaders:

    def test_fills_empty_cells(self, updater):
        result = run(updater, make_table())
        data = WtpTable.load(result).data_rows[0].to_dict()

        assert data["latest update"] == "25"
        assert data["user"] == "test"
        assert data["global edits without wikidata"] == "1"
        assert data["wikidata edits"] == "100"
        assert data["edits in last 3 months"] == "500"
        assert data["wikidata edits in last 3 months"] == "200"
        assert data["account age"] == "1"
        assert data["home wiki"] == "enwiki"
        assert data["last edit"] == "2023-01-01"
        assert data["approved"] == "Yes"

    def test_empty_value_is_not_written(self, updater):
        result = run(updater, make_table())
        data = WtpTable.load(result).data_rows[0].to_dict()

        assert data["country"] == ""

    def test_application_cell_is_kept(self, updater):
        result = run(updater, make_table())
        data = WtpTable.load(result).data_rows[0].to_dict()

        assert data["application"] == "[[Hardware donation program/EYo237]]"

    def test_no_columns_added_when_all_headers_exist(self, updater):
        result = run(updater, make_table())
        table = WtpTable.load(result)

        assert len(table.headers) == 12

    def test_existing_value_not_overwritten(self, updater):
        result = run(updater, make_table(age="99"))
        data = WtpTable.load(result).data_rows[0].to_dict()

        assert data["account age"] == "99"
        assert data["home wiki"] == "enwiki"

    def test_existing_value_overwritten_with_replace_values(self, updater):
        result = run(updater, make_table(age="99"), replace_values=True)
        data = WtpTable.load(result).data_rows[0].to_dict()

        assert data["account age"] == "1"


class TestRowMatching:

    def test_unknown_row_left_unchanged(self, updater):
        wikitext = make_table(link="[[Hardware donation program/Unknown]]")
        result = run(updater, wikitext, add_missing_headers=False)

        assert result.strip() == wikitext.strip()

    def test_link_with_display_text(self, updater):
        wikitext = make_table(link="[[Hardware donation program/EYo237|EYo237]]")
        data = WtpTable.load(run(updater, wikitext)).data_rows[0].to_dict()

        assert data["home wiki"] == "enwiki"

    def test_link_with_underscores(self, updater):
        wikitext = make_table(link="[[Hardware_donation_program/EYo237]]")
        data = WtpTable.load(run(updater, wikitext)).data_rows[0].to_dict()

        assert data["home wiki"] == "enwiki"

    def test_plain_text_first_cell_is_matched(self, updater):
        wikitext = make_table(link="Hardware donation program/EYo237")
        data = WtpTable.load(run(updater, wikitext)).data_rows[0].to_dict()

        assert data["home wiki"] == "enwiki"

    def test_multiple_tables_are_updated(self, updater):
        wikitext = make_table() + "\n\n" + make_table()
        result = run(updater, wikitext)

        assert result.count("enwiki") == 2


class TestAddMissingHeaders:

    def test_missing_columns_are_added_at_end(self, updater):
        result = run(updater, COMPLEX_WIKITEXT)
        table = WtpTable.load(result)

        for name in (
            "Global edits without wikidata",
            "Wikidata edits",
            "Edits in last 3 months",
            "Wikidata edits in last 3 months",
            "Last edit",
        ):
            assert name in table.headers

        # 13 original columns + 5 new ones, on every row
        assert [len(r.cells) for r in table.rows] == [18, 18, 18]

    def test_new_header_uses_rowspan_once(self, updater):
        result = run(updater, COMPLEX_WIKITEXT)

        assert result.count('rowspan="2" | Last edit') == 1

    def test_missing_columns_not_added_when_disabled(self, updater):
        result = run(updater, COMPLEX_WIKITEXT, add_missing_headers=False)

        assert "Last edit" not in result

    def test_existing_columns_are_not_duplicated(self, updater):
        result = run(updater, COMPLEX_WIKITEXT)
        headers = [h.lower() for h in WtpTable.load(result).headers]

        assert headers.count("home wiki") == 1
        assert headers.count("approved") == 1


# ===========================================================================
# Duplicate leaf headers (second header row repeats names) -> use header paths
# ===========================================================================


def make_complex_empty() -> str:
    """Same structure as COMPLEX_WIKITEXT, but with an empty data row."""
    head = COMPLEX_WIKITEXT.split("|-\n| User1")[0]
    return head + "|-\n| User1\n" + "|\n" * 12 + "|-\n|}"


PATH_HEADERS_TO_KEY = {
    "Application": "page_link",
    "User Edits > Global no WD": "global_without_wikidata_str",
    "User Edits > WD": "wikidata_editcount_str",
    "Last 3 months edits > Global no WD": "recent_editcount_str",
    "Last 3 months edits > WD": "recent_wikidata_editcount_str",
    "Home Wiki": "home_wiki",
}

PATH_ROWS = {"User1": USERS_ROWS["Hardware donation program/EYo237"]}


class TestHeaderPaths:

    def run_paths(self, updater, headers=None, **kwargs) -> str:
        return updater.update_wikitable_data(
            rows=PATH_ROWS,
            wikitext=make_complex_empty(),
            table_headers_to_row_key=headers or PATH_HEADERS_TO_KEY,
            **kwargs,
        )

    def test_each_duplicate_column_gets_its_own_value(self, updater):
        result = self.run_paths(updater)
        cells = WtpTable.load(result).data_rows[0].cells

        assert cells[6].value.strip() == "1"  # User Edits > Global no WD
        assert cells[7].value.strip() == "100"  # User Edits > WD
        assert cells[8].value.strip() == "500"  # Last 3 months edits > Global no WD
        assert cells[9].value.strip() == "200"  # Last 3 months edits > WD
        assert cells[11].value.strip() == "enwiki"

    def test_untouched_columns_stay_empty(self, updater):
        result = self.run_paths(updater)
        cells = WtpTable.load(result).data_rows[0].cells

        assert cells[5].is_empty  # "Global" is not in the mapping

    def test_no_columns_added_when_paths_exist(self, updater):
        result = self.run_paths(updater)

        assert [len(r.cells) for r in WtpTable.load(result).rows] == [13, 13, 13]

    def test_missing_path_header_is_skipped_not_added(self, updater):
        headers = {**PATH_HEADERS_TO_KEY, "User Edits > Nope": "age"}
        result = self.run_paths(updater, headers=headers)

        assert "Nope" not in result
        assert [len(r.cells) for r in WtpTable.load(result).rows] == [13, 13, 13]

    def test_plain_ambiguous_header_fills_first_match_only(self, updater):
        result = self.run_paths(updater, headers={"WD": "wikidata_editcount_str"})
        cells = WtpTable.load(result).data_rows[0].cells

        assert cells[7].value.strip() == "100"
        assert cells[9].is_empty
