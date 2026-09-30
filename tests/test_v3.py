from unittest.mock import MagicMock

from src.services.tables_builder import build_wikitable
from src.v3.worker import load_rows


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


def test_load_rows(tmp_path):
    cache_file = tmp_path / "home_wiki_cache.json"

    mock_api = MagicMock()
    mock_api.solve_pages_redirects.return_value = {}
    mock_api.get_pages_wikitext.return_value = {"Hardware donation program/TestUser": "; Country: Egypt\n"}
    mock_api.get_global_editcounts.return_value = {"TestUser": 1000}
    mock_api.get_wikidata_editcounts.return_value = {"TestUser": 300}
    mock_api.get_global_userinfo.return_value = {
        "home": "arwiki",
        "registration": "2020-01-01T00:00:00Z",
    }

    subpages = {"TestUser"}

    # Pass custom cache path or patch get_many
    import src.v3.worker as worker_module

    old_get_home_wikis = worker_module.get_many

    def mock_get_home_wikis(api, users):
        return {u: {"home": "arwiki", "registration": "2020-01-01T00:00:00Z"} for u in users}

    worker_module.get_many = mock_get_home_wikis
    try:
        rows = load_rows(
            api=mock_api,
            subpages=subpages,
            load_recent_editcounts=False,
        )
    finally:
        worker_module.get_many = old_get_home_wikis

    row_data = rows["Hardware donation program/TestUser"]
    assert row_data["editcount_str"] == "1,000"
    assert row_data["global_without_wikidata_str"] == "700"
    assert row_data["wikidata_editcount_str"] == "300"
