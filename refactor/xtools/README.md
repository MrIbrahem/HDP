# XTools

## Goal
All XTools HTTP calls live under `src/hdp/xtools/`. Caching stays in the shared cache layer.

## Target layout
```text
src/hdp/xtools/
├── __init__.py
└── client.py
```

## Mapping from current code

| Old | New |
|-----|-----|
| `src/api/xtools.py` | Core request functions in `client.py` |
| `src/api/xtools_cached.py` (network part only) | Same; caching moves to `cache.py` |

## Public API (suggested)

```python
# client.py
def get_recent_editcount_by_day(username: str, start: str, end: str) -> dict[str, int]:
    """Raw per-day counts from XTools globalcontribs. Empty dict on failure / missing user."""

def get_recent_editcount(username: str, start: str, end: str) -> int | None:
    """Sum of per-day counts, or None if no data."""

def get_last_edit_timestamp(username: str) -> str | None:
    """Most recent contribution date (Y-m-d) or None."""

def get_last_edit_timestamps(users: list[str]) -> dict[str, str]:
    ...
```

Keep:
- `RECENT_DAYS` default (or import from `config`)
- User-Agent header from `config`
- Existing backoff / max_pages safety
- Detection of “user does not exist” responses

## What does *not* belong here
- JSON file load/save
- `_meta` bookkeeping
- “only fetch the missing tail” logic  

Those belong in `cache.py`. The XTools client should remain a pure network adapter.

## Migration steps
1. Move the non-cached request helpers from both `xtools.py` and `xtools_cached.py` into `client.py`.
2. Have the cache layer call these pure functions.
3. Update services to depend on either the raw client or the cached wrappers, never both mixed in one place.
