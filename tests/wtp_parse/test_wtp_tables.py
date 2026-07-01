import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.wtp_parse.wtp_tables import (
    update_wikitable_data,
)


rows = {
    "Hardware donation program/EYo237": {
        "page_link": "Hardware donation program/EYo237",
        "age": "25",
        "home_wiki": "test",
        "approved": "",
    }
}

wikitext = """
{| class="wikitable sortable"
! Page !! Age of account !! Home Wiki !! Approved
|-
| [[Hardware donation program/EYo237 ]]
|
|
| zz
|-
"""

table_headers_to_row_key = {
    "Page": "page_link",
    "Age of account": "age",
    "Home Wiki": "home_wiki",
}

def test_update_wikitable_data() -> None:
    retult = update_wikitable_data(
        rows,
        wikitext,
        table_headers_to_row_key,
    )
    expected_wikitext = (
        '{| class="wikitable sortable"\n'
        '! Page !! Age of account !! Home Wiki !! Approved\n'
        '|-\n'
        '| [[Hardware donation program/EYo237 ]]\n'
        '| 25\n'
        '| test\n'
        '| zz\n'
        '|-'
    )
    assert retult.strip() == expected_wikitext

def test_update_wikitable_data_replace_values() -> None:
    retult = update_wikitable_data(
        rows,
        wikitext,
        table_headers_to_row_key,
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
        '|-'
    )
    assert retult.strip() == expected_wikitext
