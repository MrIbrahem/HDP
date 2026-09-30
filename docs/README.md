# Hardware Donation Program — Wikitable Builder

Builds wikitable reports for the Wikimedia Meta
[Hardware donation program](https://meta.wikimedia.org/wiki/Hardware_donation_program)
page. It scrapes the program's subpages via the MediaWiki API
([mwclient](https://github.com/mwclient/mwclient)), fetches per-user global edit
counts and recent (90-day) edit counts via the XTools Global Contributions API,
and emits `.wiki` files ready to be pasted/uploaded back to Meta.

## Requirements

-   Python 3.13
-   Dependencies listed in `requirements.txt`:

    ```bash
    pip install -r requirements.txt
    ```

-   A `.env` file (see `.env.example`) containing Wikimedia bot credentials:

    ```ini
    WIKIPEDIA_BOT_USERNAME=YourBotUsername
    WIKIPEDIA_BOT_PASSWORD=YourSecurePassword   # from Special:BotPasswords
    ```

## Usage

```bash
python run.py            # build table.wiki from the "Current donation requests" section
python -m update         # in-place update of the User:Mr. Ibrahem/hdp page
python -m update test    # same, but targets User:Mr. Ibrahem/test -> test.wiki
```

Generated `.wiki` files are written to `src/` and are gitignored.

-   `run.py` builds fresh wikitables from scratch (`build_wikitable`) and uses the
    **cached-only** recent-edits path (`load_recent_editcounts=False`) — no XTools
    network calls.
-   `update.py` rewrites the existing tables in a fetched live page
    (`update_wikitable_data`) and fetches fresh recent-edits data
    (`load_recent_editcounts=True`), merging new days into `edit_counts_cache.json`.

## Testing & linting

```bash
python -m pytest                                   # 15 unit tests (tests/wtp_parse/)
python -m pytest tests/wtp_parse/test_wtp_tables.py # single file
python -m pytest -k link_with_underscore            # single test
```

`pytest.ini` sets `pythonpath = . src` and `testpaths = tests`; all tests are
pure-Python wikitext parsing tests — no network, no `.env` needed.

Lint / format / typecheck config lives in `pyproject.toml` (black, isort, ruff,
mypy; all targeting py313, line length 120). No CLI extras are declared — invoke
the tools directly:

```bash
black .
isort .
ruff check .
mypy src
```

## Architecture

```
run.py / update.py
  └── src.v3.main / src.v3.update
        └── load_rows   (orchestrator)
              ├── api/mwclient_req.py    — mwclient.Site wrapper (read wikitext, redirects, global edit counts, home wiki/registration)
              ├── api/xtools.py          — raw XTools HTTP (uncached)
              ├── api/xtools_cached.py   — cached recent-edits pipeline (edit_counts_cache.json)
              ├── api/category.py        — category member listing
              ├── load_subpages.py        — section/heading → subpage link extraction
              ├── wtp_parse/              — pure wikitext parsing (wikitextparser)
              └── utils.py                — credentials, user-redirect table, age template, USER_AGENT
```

`build_wikitable` produces fresh wikitext tables; `update` instead rewrites
existing tables in fetched wikitext via `update_wikitable_data`, keyed by page
link.

### Recent-edits cache

`edit_counts_cache.json` (committed) mirrors per-user edit counts as
`{username: {date: count}, "_meta": {username: {"start":..., "end":...}}}`.
The reserved `META_KEY = "_meta"` records the date range already fetched for
each user, so subsequent runs only fetch the missing tail. `save_cache` is the
only writer and uses an atomic temp-file + `os.replace`.

## Notes

-   `src/v1.py` is the legacy implementation; `src/v3.py` is current. Edit `v3.py`
    unless told otherwise.
-   The committed `edit_counts_cache.json` will appear modified after any run that
    fetches new data — that's expected cache state, not a leak.
-   See `AGENTS.md` for contributor-facing conventions and gotchas.
