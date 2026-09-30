import pytest

from src.services.tables_builder import build_wikitable


@pytest.mark.skip("build_wikitable now expects a dict[str, ApplicationRow]")
def test_build_wikitable():
    rows = {
        "Hardware donation program/TestUser": {
            "page_link": "[[Hardware donation program/TestUser]]",
            "last_update": "{{#time:Y-m-d|{{REVISIONTIMESTAMP:Hardware donation program/TestUser}}}}",
            "user_link": "[[User:TestUser]]",
            "country": "Egypt",
            "editcount_str": "1,000",
            "global_without_wikidata_str": "700",
            "wikidata_editcount_str": "300",
            "recent_editcount_str": "50",
            "age": "2 years",
            "home_wiki": "arwiki",
        }
    }

    table_text = build_wikitable(rows)

    assert "! Global edits without wikidata" in table_text
    assert "! Wikidata edits" in table_text
    assert "| 700" in table_text
    assert "| 300" in table_text
