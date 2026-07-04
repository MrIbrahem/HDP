# AGENTS.md

Bullet points only. Read before working in this repo.

## What this is

Builds wikitable reports for the Wikimedia Meta "Hardware donation program" page. Scrapes subpages via the MediaWiki API (mwclient), fetches per-user global edit counts and recent (90-day) edit counts (XTools Global Contributions API), and emits `.wiki` files to be pasted/uploaded back to Meta.

`v1.py` is legacy; `src/v3.py` is the current implementation. Always edit `v3.py` unless explicitly told otherwise.

## Run

```bash
python run.py            # builds table.wiki from "Current donation requests" section
python -m update         # updates User:Mr. Ibrahem/hdp page (live wikitext in-place update)
python -m update test    # same, but against User:Mr. Ibrahem/test -> test.wiki
```

Both entrypoints require a `.env` with `WIKIPEDIA_BOT_USERNAME` / `WIKIPEDIA_BOT_PASSWORD` (bot password from Special:BotPasswords). See `.env.example`. Both call `load_dotenv()` and `src.setup_logging()`.

`run.py` passes `load_recent_editcounts=False`; `update.py` passes `True`. This flag chooses between cached-only and cache+fetch paths in `load_rows` (see below).

## Test / lint

```bash
python -m pytest                                   # 15 tests, all in tests/wtp_parse/
python -m pytest tests/wtp_parse/test_wtp_tables.py # single file
python -m pytest -k link_with_underscore            # single test
```

pytest.ini sets `pythonpath = . src` and `testpaths = tests`, so `from src...` imports work without install. No conftest, no fixtures beyond local `@pytest.fixture`. All tests are unit tests against pure-Python wikitext parsing — no network, no `.env` needed.

Lint/format/config is defined in `pyproject.toml`: black (line 120, py313), isort (black profile), ruff (line 120, py313, `fix = true`), mypy (py313, `ignore_missing_imports = true`, `disallow_untyped_defs = false`). No `[project.scripts]`, no `pytest`/`ruff` CLI extras — invoke tools directly. There is no configured test runner script; run commands above directly.

## Architecture

Entrypoints (`run.py`, `update.py`) -> `src.v3.main` / `src.v3.update` -> `load_rows` (the orchestrator):

-   `api/mwclient_req.py` — `MwclientApi` wraps a logged-in `mwclient.Site`. Provides `get_page_wikitext`, `solve_pages_redirects`, `get_global_editcounts` (lifetime, via `list=globalusers`), `get_home_wikis_and_registration` (`meta=globaluserinfo&guiprop=merged`). Stateful (holds the `Site`).
-   `api/xtools.py` — raw XTools HTTP calls (uncached).
-   `api/xtools_cached.py` — cached recent-edits pipeline backed by `edit_counts_cache.json` (committed to the repo; `git status` shows it dirty on every run, that's expected). Cache shape: `{username: {date: count}, "_meta": {username: {"start":..., "end":...}}}`. `META_KEY = "_meta"` is reserved. Key functions:
    -   `get_recent_editcounts_cached(users, load_new=True)` — merges fetched days into cache, throttles 0.3s per network hit, `save_every=5` flushes.
    -   `get_recent_editcounts_offline(users)` — cached-only, never hits API (used when `load_recent_editcounts=False`).
    -   `save_cache` writes atomically (temp + `os.replace`).
-   `api/category.py` — `get_category_members_titles`, `get_category_count`.
-   `load_subpages.py` — section/heading -> subpage link extraction. `SECTIONS_TO_CATEGORY` maps `"Draft requests"` -> the drafts category; other sections are parsed by heading + subpage-link extraction.
-   `wtp_parse/wtp_links.py`, `wtp_parse/wtp_tables.py` — pure wikitext parsing utilities (use the `wikitextparser` library). `update_wikitable_data` does in-place row updates on existing wikitext tables keyed by page link (preserve existing cell values when `replace_values=False`).
-   `utils.py` — `users_redirects` hard-coded dict of lowercased display-name -> canonical username (handles known renames); `load_credentials`; `calculate_age` emits a `{{age in years and months|Y|M|D}}` template string. `USER_AGENT` lives here and is reused by both mwclient and XTools requests.

`build_wikitable` in `v3.py` produces fresh wikitext tables; `update` instead rewrites existing tables in fetched wikitext via `update_wikitable_data`. The `table_headers_to_row_key` mapping (`"Page" -> "page_link"`, etc.) is what aligns parsed table headers to row-data keys for in-place updates — keep it in sync with `build_wikitable`'s header order if you edit columns.

`OUTPUT_DIR` is `Path(__file__).parent` (the `src/` dir), so generated `.wiki` files (`table.wiki`, `Mr. Ibrahem_hdp.wiki`, `test.wiki`) live in `src/`. These are gitignored via `src/*.wiki` in `.gitignore`.

## Conventions / gotchas

-   Python 3.13 target. Use modern syntax matching existing files (`str | None`, `datetime.now(UTC)`).
-   Logging is configured per-project-namespace (`name="src"`); modules do `logger = logging.getLogger(__name__)` and propagate stays False. Don't add `basicConfig` or root handlers — use `src.setup_logging`.
-   Throttle 0.3s after each _uncached_ network fetch in the editcounts loop; do not throttle on cache hits. `was_cached` already gates this — preserve it if you refactor the loop.
-   `users_redirects` in `utils.py` is the source of truth for known rename redirects; `solve_users_redirects` then queries the API to catch the rest. The `Johnjoy12` debug log block in `solve_users_redirects` is intentional (left as a watchpoint) — don't remove without asking.
-   `edit_counts_cache.json` is committed and shows up modified after any run that fetches new data. Don't "clean up" these modifications unless asked; they're the cache state. `save_cache` is the only writer — don't hand-edit it.
-   When adding a column to the wikitable: update (a) `build_wikitable` header + row append, (b) `row_data` dict in `load_rows`, (c) `table_headers_to_row_key` in `update`, in that order, or the in-place update path silently drops the column.
-   No `opencode.json` exists yet. Existing skill files under `.claude/skills/` and `.claude/` are not repo-config; ignore them when reasoning about the codebase.
-   `docs/plan.md` is a stale planning doc for an older version of the feature; treat as history, not spec.
