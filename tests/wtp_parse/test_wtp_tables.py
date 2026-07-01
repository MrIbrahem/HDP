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
! Page
! Age of account
! Home Wiki
! Approved
|-
| [[Hardware donation program/Ibjaja055]]
|
|
|
|-
| [[Hardware donation program/test]]
|
|
|
|-
| [[Hardware donation program/EYo237 ]]
| !
|
| zz
|-
"""

expected_wikitext = """
{| class="wikitable sortable"
! Page
! Age of account
! Home Wiki
! Approved
|-
| [[Hardware donation program/Ibjaja055]]
|
|
|
|-
| [[Hardware donation program/test]]
|
|
|
|-
| [[Hardware donation program/EYo237 ]]
| !
| 25
| test
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
    assert retult == expected_wikitext

if __name__ == "__main__":
    test_update_wikitable_data()
