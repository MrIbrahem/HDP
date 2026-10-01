```
tests/
├── conftest.py
├── test_v3.py
│
└── unit/
    ├── cache/
    │   ├── test_json_cache.py
    │   ├── test_home_wiki_cache.py
    │   └── test_recent_edit_cache.py
    │
    ├── models/
    │   ├── test_extract_country.py
    │   ├── test_user_info.py
    │   └── test_application_row.py
    │
    ├── parsing/
    │   ├── test_links.py
    │   ├── test_tables_manager.py
    │   └── test_tables_updater.py
    │
    ├── services/
    │   ├── test_subpages_service.py
    │   ├── test_tables_builder.py
    │   └── test_hdp_service.py
    │
    ├── wiki/
    │   ├── test_category.py
    │   ├── test_client.py
    │   ├── test_users.py
    │   └── test_wikidata_editcounts.py
    │
    ├── xtools/
    │   └── test_xtools_client.py
    │
    ├── test_cli.py
    ├── test_config.py
    └── test_logging_setup.py
```
