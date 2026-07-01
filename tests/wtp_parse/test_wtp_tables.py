

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
            '! Page !! Age of account !! Home Wiki !! Approved\n'
            '|-\n'
            '| [[Hardware donation program/EYo237 ]]\n'
            '|\n'
            '|\n'
            '| zz\n'
            '|-\n'
            '|}'
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
            '! Page !! Age of account !! Home Wiki !! Approved\n'
            '|-\n'
            '| [[Hardware donation program/EYo237 ]]\n'
            '| 25\n'
            '| test\n'
            '| zz\n'
            '|-\n'
            '|}'
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
            '! Page !! Age of account !! Home Wiki !! Approved\n'
            '|-\n'
            '| Hardware donation program/EYo237\n'
            '| 25\n'
            '| test\n'
            '| zz\n'
            '|-\n'
            '|}'
        )
        assert retult.strip() == expected_wikitext
