# Wiki Client

## Goal
All MediaWiki / mwclient interaction lives under `src/hdp/wiki/`.

## Target layout
```text
src/hdp/wiki/
├── __init__.py
├── client.py      # connection + page/user API wrappers
├── category.py    # category members + counts
└── users.py       # redirects, global userinfo helpers
```

## Mapping from current code

| Old | New |
|-----|-----|
| `src/api/mwclient_req.py` → `connect_to_meta`, `get_page_wikitext`, `get_pages_wikitext`, `page_last_edit_timestamp`, `get_page_creator`, `get_global_editcounts`, `solve_pages_redirects`, `get_global_userinfo`, `get_home_wikis_and_registration`, `MwclientApi` | `wiki/client.py` (+ thin helpers in `users.py`) |
| `src/api/category.py` | `wiki/category.py` |
| Redirect / username normalization pieces from `worker.py` / `utils` | `wiki/users.py` |

## Suggested design

### `client.py`
- Keep a thin `WikiClient` class (or keep the existing `MwclientApi` name and move it).
- Constructor receives an already-logged-in `mwclient.Site` (or credentials + `connect()` factory).
- Methods stay close to the current API so migration is mechanical:
  - `get_page_wikitext(title) -> str`
  - `get_pages_wikitext(titles) -> dict[str, str]`
  - `get_global_editcounts(users) -> dict[str, int]`
  - `get_global_userinfo(username) -> dict`
  - `solve_pages_redirects(pages) -> dict[str, str]`
  - optional: last-edit timestamp / page creator if still needed

### `category.py`
- `get_category_count(site, category_name) -> int`
- `get_category_members_titles(site, category_name, namespace=..., total_pages=..., max_items=...) -> list[str]`
- Keep the existing retry/backoff and `tqdm` behaviour.

### `users.py`
- `resolve_username(raw_name, redirects_map) -> str` (capitalization + static redirects)
- `solve_user_redirects(client, usernames) -> dict[str, str]` (API-based)
- Any pure username-normalization helpers that do not need a network call.

## Design rules
1. No XTools or cache logic here.
2. Prefer dependency injection: services receive a `WikiClient` instance.
3. Keep `USER_AGENT` imported from `config`.
4. Logging stays on the module logger (`logging.getLogger(__name__)`).

## Migration steps
1. Copy `mwclient_req.py` → `client.py` and adjust imports.
2. Copy `category.py` as-is under `wiki/`.
3. Extract redirect helpers from `worker.py` into `users.py`.
4. Re-export the public API from `wiki/__init__.py` for a clean import surface.
