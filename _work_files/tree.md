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
│   │   ├── application_table.py
│   │   └── user_info.py
│   ├── parsing/
│   │   ├── __init__.py
│   │   ├── links.py
│   │   ├── tables_builder.py
│   │   ├── tables_manager.py
│   │   └── tables_updater.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── hdp_service.py
│   │   └── subpages_service.py
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
│   ├── unit/
│   │   ├── cache/
│   │   │   ├── test_home_wiki_cache.py
│   │   │   ├── test_json_cache.py
│   │   │   └── test_recent_edit_cache.py
│   │   ├── models/
│   │   │   ├── test_application_row.py
│   │   │   ├── test_extract_country.py
│   │   │   └── test_user_info.py
│   │   ├── parsing/
│   │   │   ├── test_links.py
│   │   │   ├── test_tables_builder.py
│   │   │   ├── test_tables_manager.py
│   │   │   └── test_tables_updater.py
│   │   ├── services/
│   │   │   ├── test_hdp_service.py
│   │   │   └── test_subpages_service.py
│   │   ├── wiki/
│   │   │   ├── test_category.py
│   │   │   ├── test_client.py
│   │   │   └── test_users.py
│   │   ├── xtools/
│   │   │   └── test_xtools_client.py
│   │   ├── test_cli.py
│   │   ├── test_config.py
│   │   └── test_logging_setup.py
│   ├── conftest.py
│   └── README.md
├── AGENTS.md
├── pyproject.toml
├── pytest.ini
├── README.md
└── requirements.txt

```