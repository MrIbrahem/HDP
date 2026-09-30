
# Parsing

## Goal
All wikitext parsing (links, sections, tables) lives under `src/hdp/parsing/`.

## Target layout
```text
src/hdp/parsing/
├── __init__.py
├── links.py      # sections + subpage links
└── tables.py     # table column manager + data updater
```

## Mapping from current code

| Old | New |
|-----|-----|
| `src/wtp_parse/wtp_links.py` | `parsing/links.py` |
| `src/wtp_parse/wtp_table_manager.py` | part of `parsing/tables.py` |
| `src/wtp_parse/wtp_tables.py` | part of `parsing/tables.py` |
| `extract_country` (from utils) | optional small helper here or in `links.py` |

## Suggested API

### `links.py`
```python
def get_section_by_heading(wikitext: str, heading: str) -> Section | None: ...
def extract_subpage_links(base_page: str, section) -> list[str]: ...
```
Keep behaviour identical (underscore → space, prefix stripping, dedup).

### `tables.py`
Keep the two existing concepts, preferably as classes:
- `WikiTableColumnManager` – ensure/add columns
- `WikiTableDataUpdater` – fill cells from a rows dict

Plus the convenience function:
```python
def update_wikitable_data(
    rows: dict[str, Any],
    wikitext: str,
    table_headers_to_row_key: dict[str, str],
    replace_values: bool = False,
    add_missing_headers: bool = True,
) -> str: ...
```

## Design rules
1. No network calls.
2. No knowledge of HDP domain (BASE_PAGE can be passed in; do not hard-code business rules beyond what already exists).
3. Preserve the current careful handling of colspan/rowspan and the “re-assign `table.string` after structural edits” fix.

## Migration steps
1. Move the three modules with minimal renames.
2. Re-export from `parsing/__init__.py`.
3. Update tests under `tests/wtp_parse/` to import from the new paths (or keep temporary re-exports until tests are updated).

