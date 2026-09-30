
# Cache

## Goal
One place for all on-disk caches (home wiki, recent edit counts, and any future caches).

## Target file
`src/hdp/cache.py`

## Mapping from current code

| Old | Responsibility that moves here |
|-----|--------------------------------|
| `src/api/home_wiki_cached.py` | Load/save + “fetch only missing users” |
| `src/api/xtools_cached.py` (cache layer) | Load/save, `_meta` range tracking, merge of new days |

## Suggested surface

```python
# Paths (override via config / env if needed)
HOME_WIKI_CACHE = "data/home_wiki_cache.json"
EDIT_COUNTS_CACHE = "data/edit_counts_cache.json"

def load_json_cache(path: str, default: dict | None = None) -> dict: ...
def save_json_cache(cache: dict, path: str) -> None: ...  # atomic write

# Home wiki
def get_home_wikis_cached(api, users: list[str], cache_path=..., save_every=5) -> dict[str, dict]: ...

# Recent edits (XTools-backed)
def get_recent_editcounts_cached(users, recent_days=90, cache_path=..., save_every=5, set_zero=False) -> dict[str, int]: ...
def get_recent_editcounts_offline(users, recent_days=90, cache_path=..., set_zero=False) -> dict[str, int]: ...
```

## Internal design
- Keep the existing cache file layouts so current `data/*.json` files keep working:
  - Home wiki: `{ username: { "home", "registration" } }`
  - Edit counts: `{ "_meta": { user: {start, end} }, username: { "YYYY-MM-DD": count } }`
- Atomic save (write `.tmp` then `os.replace`) stays mandatory.
- Network functions are *injected* or imported from `wiki` / `xtools`; the cache module must not open HTTP connections itself beyond calling those helpers.

## Migration steps
1. Create `cache.py` with shared load/save helpers.
2. Port home-wiki cached logic first (simpler).
3. Port XTools range-merge logic second.
4. Point services at the new functions; leave thin shims in the old modules until the old tree is deleted.
