```
repo/
├── hdp/
│   └── __main__.py
├── src/
│   ├── cache/
│   │   ├── __init__.py
│   │   ├── home_wiki_cache.py
│   │   ├── json_cache.py
│   │   └── recent_edit_cache.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── application_row.py
│   │   └── user_info.py
│   ├── parsing/
│   │   ├── __init__.py
│   │   ├── links.py
│   │   ├── tables_manager.py
│   │   └── tables_updater.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── hdp_service.py
│   │   ├── subpages_service.py
│   │   └── tables_builder.py
│   ├── wiki/
│   │   ├── __init__.py
│   │   ├── category.py
│   │   ├── client.py
│   │   └── users.py
│   ├── xtools/
│   │   ├── __init__.py
│   │   └── client.py
│   ├── __init__.py
│   ├── cli.py
│   ├── config.py
│   └── logging_setup.py
├── tests/
│   ├── cache/
│   │   ├── test_home_wiki_cache.py
│   │   ├── test_json_cache.py
│   │   └── test_xtools_cached.py
│   ├── models/
│   │   └── test_extract_country.py
│   ├── parsing/
│   │   ├── test_links.py
│   │   ├── test_tables_manager.py
│   │   └── test_tables_updater.py
│   ├── utils/
│   ├── wiki/
│   │   └── test_wikidata_editcounts.py
│   ├── conftest.py
│   └── test_v3.py
├── AGENTS.md
├── pyproject.toml
├── pytest.ini
├── README.md
└── requirements.txt

```