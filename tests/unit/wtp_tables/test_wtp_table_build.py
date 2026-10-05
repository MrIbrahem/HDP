"""
Unit tests for src/wtp_tables/wtp_table.py module.
"""

import pytest

from src.wtp_tables.wtp_table import WtpTable

# ===========================================================================
# WtpTable.build
# ===========================================================================


class TestBuild:

    def test_flat_headers_exact_text(self):
        text = WtpTable.build_wikitext(["Page", "Age"], [["[[A]]", 1], ["[[B]]", 2]])

        assert text == """{| class="wikitable"\n! Page\n! Age\n|-\n| [[A]]\n| 1\n|-\n| [[B]]\n| 2\n|}"""

    def test_build_returns_loaded_table(self):
        t = WtpTable.build(["Page", "Age"], [["[[A]]", 1], ["[[B]]", 2]])

        assert isinstance(t, WtpTable)
        assert t.headers == ["Page", "Age"]
        assert len(t.data_rows) == 2
        assert t.data_rows[1].to_dict() == {"page": "[[B]]", "age": "2"}

    def test_string_property_matches_built_text(self):
        text = WtpTable.build_wikitext(["Page"], [["A"]])
        t = WtpTable.load(text)

        assert t.string == text

    def test_dict_rows(self):
        t = WtpTable.build(["Page", "Age", "Home Wiki"], [{"age": 5, "Page": "A"}])

        assert t.data_rows[0].to_dict() == {"page": "A", "age": "5", "home wiki": ""}

    def test_none_and_missing_values_are_empty(self):
        text = WtpTable.build_wikitext(["A", "B", "C"], [["x", None]])

        assert text.endswith("|-\n| x\n|\n|\n|}")

    def test_attrs_and_caption(self):
        text = WtpTable.build_wikitext(["A"], [], attrs='class="wikitable sortable"', caption="My table")

        assert text == '{| class="wikitable sortable"\n|+ My table\n! A\n|}'

    def test_header_only_table(self):
        t = WtpTable.build(["A", "B"], [])

        assert t.headers == ["A", "B"]
        assert t.data_rows == []

    def test_multi_row_header_exact_text(self):
        text = WtpTable.build_wikitext(
            ["Application", "User Edits > Global", "User Edits > WD", "Home Wiki"],
            [["A", 1, 2, "enwiki"]],
        )

        assert text == (
            '{| class="wikitable"\n'
            '! rowspan="2" | Application\n'
            '! colspan="2" | User Edits\n'
            '! rowspan="2" | Home Wiki\n'
            "|-\n"
            "! Global\n"
            "! WD\n"
            "|-\n"
            "| A\n"
            "| 1\n"
            "| 2\n"
            "| enwiki\n"
            "|}"
        )

    def test_multi_row_header_round_trip(self):
        t = WtpTable.build(
            ["Application", "User Edits > Global", "User Edits > WD", "Home Wiki"],
            [["A", 1, 2, "enwiki"]],
        )
        row = t.data_rows[0]

        assert t.headers == ["Application", "Global", "WD", "Home Wiki"]
        assert row.cells[1].header_path == ("User Edits", "Global")
        assert row.get("User Edits > WD").value.strip() == "2"
        assert row.get("Home Wiki").value.strip() == "enwiki"

    def test_tuple_headers(self):
        t = WtpTable.build([("Group", "X"), ("Group", "Y")], [[1, 2]])

        assert t.headers == ["X", "Y"]
        assert t.data_rows[0].get("Group > Y").value.strip() == "2"

    def test_duplicate_leaf_names_under_different_parents(self):
        t = WtpTable.build(
            ["User Edits > WD", "Last 3 months edits > WD"],
            [{"User Edits > WD": 1, "Last 3 months edits > WD": 2}],
        )
        row = t.data_rows[0]

        assert row.get("User Edits > WD").value.strip() == "1"
        assert row.get("Last 3 months edits > WD").value.strip() == "2"

    def test_adjacent_identical_leaf_headers_are_not_merged(self):
        text = WtpTable.build_wikitext(["WD", "WD"], [])

        assert text.count("! WD") == 2
        assert "colspan" not in text

    def test_three_level_header(self):
        t = WtpTable.build(["A > B > C", "A > B > D", "A > E", "F"], [[1, 2, 3, 4]])
        row = t.data_rows[0]

        assert t.headers == ["C", "D", "E", "F"]
        assert row.cells[0].header_path == ("A", "B", "C")
        assert row.cells[2].header_path == ("A", "E")
        assert [c.value.strip() for c in row.cells] == ["1", "2", "3", "4"]

    def test_unknown_dict_key_raises(self):
        with pytest.raises(ValueError):
            WtpTable.build(["A"], [{"Nope": 1}])

    def test_too_many_values_raises(self):
        with pytest.raises(ValueError):
            WtpTable.build(["A"], [[1, 2]])

    def test_empty_headers_raises(self):
        with pytest.raises(ValueError):
            WtpTable.build([], [])

    def test_blank_header_part_raises(self):
        with pytest.raises(ValueError):
            WtpTable.build(["A > "], [])
