# Services

## Goal

Domain orchestration: collect subpages, build rows, build/update tables. No CLI, no raw HTTP.

## Target file

`src/hdp/services.py`
(Optional later split: `row_builder.py` if the file grows too large.)

## Mapping from current code

| Old                              | New responsibility                            |
| -------------------------------- | --------------------------------------------- |
| `src/load_subpages.py`           | Subpage discovery (category or section)       |
| `src/v3/worker.py` → `load_rows` | Build the rows dict                           |
| `src/v3/tables_builder.py`       | `build_wikitable`                             |
| `src/v3/v3_main.py`              | “generate tables” orchestration               |
| `src/v3/v3_update.py`            | “update existing page wikitext” orchestration |

## Suggested public functions

```python
def get_subpages_for_section(site, full_wikitext, base_page, section_title) -> list[str]: ...
def get_subpages(full_wikitext, base_page) -> set[str]: ...

def load_rows(
    wiki_client,
    subpages: set[str] | list[str],
    *,
    unknown_placeholder: str = "unknown",
    load_recent_editcounts: bool = True,
    load_last_edits: bool = False,
    base_page: str = BASE_PAGE,
) -> dict[str, ApplicationRow | dict]: ...

def build_wikitable(rows, add_last_edit: bool = False) -> str: ...

def generate_tables(
    page_title: str,
    section_names: list[str],
    *,
    wiki_client=None,
    load_recent_editcounts: bool = True,
    load_last_edits: bool = False,
    unknown_placeholder: str = "unknown",
) -> str: ...

def update_page_tables(
    page_title: str,
    section_names: list[str],
    *,
    wiki_client=None,
    load_recent_editcounts: bool = True,
    load_last_edits: bool = False,
    unknown_placeholder: str = "",
) -> str: ...
```

## Internal flow for `load_rows` (keep current behaviour)

1. Derive usernames from subpage names + static redirects.
2. Resolve User: page redirects via the wiki client.
3. Batch-fetch application wikitext → extract country.
4. Global edit counts (wiki client).
5. Recent edit counts (cache layer / offline).
6. Home wiki + registration (cache layer) → age.
7. Optional last-edit timestamps (XTools).
8. Assemble one row dict per application page.

## Design rules

1. Accept clients/helpers as arguments (or obtain them via small factories) so unit tests can inject fakes.
2. Do not write files; callers (CLI) decide where output goes.
3. Reuse `parsing` and `cache` rather than reimplementing them.

## Migration steps

1. Move `load_subpages` helpers and `load_rows` first.
2. Move `build_wikitable`.
3. Wire `generate_tables` / `update_page_tables` as thin successors of `v3_main.main` and `v3_update.update`.
