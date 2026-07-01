import pytest

from src.wtp_parse.wtp_tables import (
    update_wikitable_data,
)


class TestUpdate:

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        self.rows = {
            "Hardware donation program/EYo237": {
                "page_link": "Hardware donation program/EYo237",
                "age": "25",
                "home_wiki": "test",
                "approved": "",
            }
        }

        self.wikitext = (
            '{| class="wikitable sortable"\n'
            "! Page !! Age of account !! Home Wiki !! Approved\n"
            "|-\n"
            "| [[Hardware donation program/EYo237 ]]\n"
            "|\n"
            "|\n"
            "| zz\n"
            "|-\n"
            "|}"
        )

        self.table_headers_to_row_key = {
            "Page": "page_link",
            "Age of account": "age",
            "Home Wiki": "home_wiki",
        }

    def test_update_wikitable_data(self) -> None:
        retult = update_wikitable_data(
            self.rows,
            self.wikitext,
            self.table_headers_to_row_key,
        )
        expected_wikitext = (
            '{| class="wikitable sortable"\n'
            "! Page !! Age of account !! Home Wiki !! Approved\n"
            "|-\n"
            "| [[Hardware donation program/EYo237 ]]\n"
            "| 25\n"
            "| test\n"
            "| zz\n"
            "|-\n"
            "|}"
        )
        assert retult.strip() == expected_wikitext

    def test_update_wikitable_data_replace_values(self) -> None:
        retult = update_wikitable_data(
            self.rows,
            self.wikitext,
            self.table_headers_to_row_key,
            replace_values=True,
        )
        expected_wikitext = (
            '{| class="wikitable sortable"\n'
            "! Page !! Age of account !! Home Wiki !! Approved\n"
            "|-\n"
            "| Hardware donation program/EYo237\n"
            "| 25\n"
            "| test\n"
            "| zz\n"
            "|-\n"
            "|}"
        )
        assert retult.strip() == expected_wikitext


class TestUpdateWikitableDataEdgeCases:

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        self.table_headers_to_row_key = {
            "Page": "page_link",
            "Age of account": "age",
            "Home Wiki": "home_wiki",
        }

    def test_link_with_display_text_is_matched(self) -> None:
        """A link like [[Page|display text]] should be matched using the part before |."""
        rows = {
            "Hardware donation program/EYo237": {
                "page_link": "Hardware donation program/EYo237",
                "age": "25",
                "home_wiki": "test",
            }
        }
        wikitext = (
            '{| class="wikitable sortable"\n'
            "! Page !! Age of account !! Home Wiki !! Approved\n"
            "|-\n"
            "| [[Hardware donation program/EYo237|EYo237]]\n"
            "|\n"
            "|\n"
            "| zz\n"
            "|-\n"
            "|}"
        )
        result = update_wikitable_data(rows, wikitext, self.table_headers_to_row_key)
        expected = (
            '{| class="wikitable sortable"\n'
            "! Page !! Age of account !! Home Wiki !! Approved\n"
            "|-\n"
            "| [[Hardware donation program/EYo237|EYo237]]\n"
            "| 25\n"
            "| test\n"
            "| zz\n"
            "|-\n"
            "|}"
        )
        assert result.strip() == expected

    def test_link_with_underscore_is_matched(self) -> None:
        """Links containing underscores (_) should be treated as spaces."""
        rows = {
            "Hardware donation program/E Yo237": {
                "page_link": "Hardware donation program/E Yo237",
                "age": "30",
                "home_wiki": "arwiki",
            }
        }
        wikitext = (
            '{| class="wikitable sortable"\n'
            "! Page !! Age of account !! Home Wiki !! Approved\n"
            "|-\n"
            "| [[Hardware_donation_program/E_Yo237]]\n"
            "|\n"
            "|\n"
            "| zz\n"
            "|-\n"
            "|}"
        )
        result = update_wikitable_data(rows, wikitext, self.table_headers_to_row_key)
        assert "| 30\n" in result
        assert "| arwiki\n" in result

    def test_row_not_in_rows_dict_is_left_unchanged(self) -> None:
        """A row with no matching entry in `rows` should be left unchanged, without errors."""
        rows = {
            "Hardware donation program/EYo237": {
                "page_link": "Hardware donation program/EYo237",
                "age": "25",
                "home_wiki": "test",
            }
        }
        wikitext = (
            '{| class="wikitable sortable"\n'
            "! Page !! Age of account !! Home Wiki !! Approved\n"
            "|-\n"
            "| [[Hardware donation program/Unknown]]\n"
            "|\n"
            "|\n"
            "| zz\n"
            "|-\n"
            "|}"
        )
        result = update_wikitable_data(rows, wikitext, self.table_headers_to_row_key)
        # Nothing changed because the link is not present in `rows`
        assert result.strip() == wikitext.strip()

    def test_existing_value_not_overwritten_when_replace_values_false(self) -> None:
        """An already-filled cell should not be overwritten when replace_values=False."""
        rows = {
            "Hardware donation program/EYo237": {
                "page_link": "Hardware donation program/EYo237",
                "age": "25",
                "home_wiki": "test",
            }
        }
        wikitext = (
            '{| class="wikitable sortable"\n'
            "! Page !! Age of account !! Home Wiki !! Approved\n"
            "|-\n"
            "| [[Hardware donation program/EYo237]]\n"
            "| 99\n"
            "|\n"
            "| zz\n"
            "|-\n"
            "|}"
        )
        result = update_wikitable_data(rows, wikitext, self.table_headers_to_row_key)
        # Age of account already has a value (99), so it should not be overwritten
        assert "| 99\n" in result
        # Home Wiki was empty, so it should be filled in
        assert "| test\n" in result

    def test_existing_value_overwritten_when_replace_values_true(self) -> None:
        """A cell's value should always be overwritten when replace_values=True."""
        rows = {
            "Hardware donation program/EYo237": {
                "page_link": "Hardware donation program/EYo237",
                "age": "25",
                "home_wiki": "test",
            }
        }
        wikitext = (
            '{| class="wikitable sortable"\n'
            "! Page !! Age of account !! Home Wiki !! Approved\n"
            "|-\n"
            "| [[Hardware donation program/EYo237]]\n"
            "| 99\n"
            "|\n"
            "| zz\n"
            "|-\n"
            "|}"
        )
        result = update_wikitable_data(rows, wikitext, self.table_headers_to_row_key, replace_values=True)
        assert "| 25\n" in result
        assert "| 99\n" not in result

    def test_row_key_not_present_in_row_data_is_skipped(self) -> None:
        """If the requested row_key is missing from the row data, the cell is left unchanged."""
        rows = {
            "Hardware donation program/EYo237": {
                "page_link": "Hardware donation program/EYo237",
                "age": "25",
                # home_wiki is missing here
            }
        }
        wikitext = (
            '{| class="wikitable sortable"\n'
            "! Page !! Age of account !! Home Wiki !! Approved\n"
            "|-\n"
            "| [[Hardware donation program/EYo237]]\n"
            "|\n"
            "|\n"
            "| zz\n"
            "|-\n"
            "|}"
        )
        result = update_wikitable_data(rows, wikitext, self.table_headers_to_row_key)
        assert "| 25\n" in result
        # Home Wiki column remains empty since home_wiki is missing from the data
        assert result.count("|\n") >= 1

    def test_multiple_data_rows_updated_independently(self) -> None:
        """Multiple data rows in the same table should each be updated correctly and independently."""
        rows = {
            "Hardware donation program/EYo237": {
                "page_link": "Hardware donation program/EYo237",
                "age": "25",
                "home_wiki": "test",
            },
            "Hardware donation program/Ibjaja055": {
                "page_link": "Hardware donation program/Ibjaja055",
                "age": "10",
                "home_wiki": "enwiki",
            },
        }
        wikitext = (
            '{| class="wikitable sortable"\n'
            "! Page !! Age of account !! Home Wiki !! Approved\n"
            "|-\n"
            "| [[Hardware donation program/Ibjaja055]]\n"
            "|\n"
            "|\n"
            "|\n"
            "|-\n"
            "| [[Hardware donation program/EYo237]]\n"
            "|\n"
            "|\n"
            "| zz\n"
            "|-\n"
            "|}"
        )
        result = update_wikitable_data(rows, wikitext, self.table_headers_to_row_key)
        assert "| 10\n" in result
        assert "| enwiki\n" in result
        assert "| 25\n" in result
        assert "| test\n" in result

    def test_multiple_tables_are_all_updated(self) -> None:
        """All tables in the wikitext should be updated, not just the first one."""
        rows = {
            "Hardware donation program/EYo237": {
                "page_link": "Hardware donation program/EYo237",
                "age": "25",
                "home_wiki": "test",
            }
        }
        wikitext = (
            '{| class="wikitable sortable"\n'
            "! Page !! Age of account !! Home Wiki !! Approved\n"
            "|-\n"
            "| [[Hardware donation program/EYo237]]\n"
            "|\n"
            "|\n"
            "| zz\n"
            "|-\n"
            "|}\n"
            "\n"
            '{| class="wikitable sortable"\n'
            "! Page !! Age of account !! Home Wiki !! Approved\n"
            "|-\n"
            "| [[Hardware donation program/EYo237]]\n"
            "|\n"
            "|\n"
            "| zz\n"
            "|-\n"
            "|}"
        )
        result = update_wikitable_data(rows, wikitext, self.table_headers_to_row_key)
        assert result.count("| 25\n") == 2
        assert result.count("| test\n") == 2

    def test_no_matching_link_pattern_is_skipped_without_error(self) -> None:
        """A row without a [[...]] link in its first cell should be skipped without raising an error."""
        rows = {
            "Hardware donation program/EYo237": {
                "page_link": "Hardware donation program/EYo237",
                "age": "25",
                "home_wiki": "test",
            }
        }
        wikitext = (
            '{| class="wikitable sortable"\n'
            "! Page !! Age of account !! Home Wiki !! Approved\n"
            "|-\n"
            "| Just plain text, no link\n"
            "|\n"
            "|\n"
            "| zz\n"
            "|-\n"
            "|}"
        )
        # Should not raise any exception
        result = update_wikitable_data(rows, wikitext, self.table_headers_to_row_key)
        assert "Just plain text, no link" in result

    def test_unknown_header_in_mapping_is_ignored(self) -> None:
        """If a header in table_headers_to_row_key doesn't actually exist in the table, it is safely ignored."""
        rows = {
            "Hardware donation program/EYo237": {
                "page_link": "Hardware donation program/EYo237",
                "age": "25",
                "home_wiki": "test",
                "nonexistent_field": "should_not_appear",
            }
        }
        headers_with_bad_entry = {
            **self.table_headers_to_row_key,
            "Nonexistent Header": "nonexistent_field",
        }
        wikitext = (
            '{| class="wikitable sortable"\n'
            "! Page !! Age of account !! Home Wiki !! Approved\n"
            "|-\n"
            "| [[Hardware donation program/EYo237]]\n"
            "|\n"
            "|\n"
            "| zz\n"
            "|-\n"
            "|}"
        )
        result = update_wikitable_data(rows, wikitext, headers_with_bad_entry)
        assert "should_not_appear" not in result
        assert "| 25\n" in result
