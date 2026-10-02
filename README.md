# HDP — Hardware Donation Program Tools

Python toolkit that builds and updates tracking tables for the
[Wikimedia Hardware Donation Program](https://meta.wikimedia.org/wiki/Hardware_donation_program)
on Meta-Wiki.

It collects open / draft / approved application subpages, enriches each row with
user stats (global edits, recent activity, home wiki, account age, country), and
either generates fresh wikitables or patches the cells of an existing page.

---

## Features

-   Discover applications from MediaWiki **categories** or page **sections**
-   Batch-fetch page wikitext, global edit counts, and CentralAuth home-wiki data
-   Recent global edit counts via the **XTools** API (with on-disk caching)
-   Country extraction from application templates
-   Generate new sortable wikitables **or** update cells in place
-   Class-based, dependency-injected design — easy to test and extend

---

## Requirements

-   Python **≥ 3.13**
-   A Meta-Wiki bot account with a [bot password](https://meta.wikimedia.org/wiki/Special:BotPasswords)

```text
requests>=2.31.0
mwclient>=0.10.1
python-dotenv>=1.0.0
wikitextparser>=2.0.0
colorlog
tqdm
```

Install:

```bash
pip install -r requirements.txt
```

---

## Configuration

Copy the example env file and fill in your bot credentials:

```bash
cp .env.example .env
```

```env
WIKIPEDIA_BOT_USERNAME=YourBotUsername
WIKIPEDIA_BOT_PASSWORD=YourSecurePassword
```

Optional overrides:

| Variable          | Default                     | Meaning                           |
| ----------------- | --------------------------- | --------------------------------- |
| `HDP_CACHE_DIR`   | `data`                      | Directory for JSON caches         |
| `HDP_RECENT_DAYS` | `90`                        | Window for “edits in last N days” |
| `HDP_USER_AGENT`  | _(built-in)_                | HTTP User-Agent for API calls     |
| `HDP_BASE_PAGE`   | `Hardware donation program` | Root page title                   |

Caches written under the cache directory:

| File                     | Contents                                    |
| ------------------------ | ------------------------------------------- |
| `home_wiki_cache.json`   | Home wiki + registration date per user      |
| `edit_counts_cache.json` | Per-day recent edit counts + range metadata |
| `users_redirects.json`   | Optional static username redirects          |

---

## Quick start

```bash
# Generate tables for the three default categories
python -m hdp generate

# Update cells on your tracking page (offline recent counts)
python -m hdp update --no-recent

# Test page
python -m hdp update --test --no-recent
```

Output is written to `data/` by default (`table.wiki` for generate,
`Mr. Ibrahem_hdp.wiki` for update).

---

## CLI reference

```text
python -m hdp [-h] [--log-level {DEBUG,INFO,WARNING,ERROR}]
              {generate,update} ...
```

### `generate`

Build section-scoped tables from categories or section headings
(replaces the old `run.py`).

| Flag           | Default                     | Description                             |
| -------------- | --------------------------- | --------------------------------------- |
| `--page`       | `Hardware donation program` | Source page title                       |
| `--sections`   | three HDP categories        | Section headings or `Category:…` names  |
| `--output`     | `data/table.wiki`           | Output path                             |
| `--no-recent`  | off                         | Use offline cache only for recent edits |
| `--last-edits` | off                         | Include “Last edit” column              |
| `--unknown`    | `unknown`                   | Placeholder for missing values          |

```bash
python -m hdp generate \
  --sections "Category:Hardware donation program open requests" \
  --output data/open.wiki \
  --log-level DEBUG
```

#### run.py

```bash
# build table.wiki from the "Current donation requests" section
python run.py
# replaced by:
python -m hdp generate
```

### `update`

Refresh table cells inside an existing wiki page
(replaces the old `update.py`).

| Flag           | Default                     | Description                         |
| -------------- | --------------------------- | ----------------------------------- |
| `--page`       | `User:Mr. Ibrahem/hdp`      | Page whose tables are updated       |
| `--test`       | off                         | Use `User:Mr. Ibrahem/test` instead |
| `--sections`   | three HDP categories        | Same as generate                    |
| `--output`     | `data/Mr. Ibrahem_hdp.wiki` | Output path                         |
| `--no-recent`  | off                         | Offline recent-edit cache           |
| `--last-edits` | off                         | Include “Last edit” column          |
| `--unknown`    | `""`                        | Placeholder (empty by default)      |

```bash
python -m hdp update --page "User:Mr. Ibrahem/hdp" --no-recent
```

#### update.py

```bash
python update.py         # in-place update of the User:Mr. Ibrahem/hdp page
# replaced by:
python -m hdp update

python update.py test    # same, but targets User:Mr. Ibrahem/test -> test.wiki
# replaced by:
python -m hdp update --test
```

---

## Package layout

```text
src/hdp/
├── __init__.py
├── __main__.py          # python -m hdp
├── cli.py               # Cli — argparse entry point
├── config.py            # Settings, Credentials, constants
├── models.py            # UserInfo, ApplicationRow (dataclasses)
├── logging_setup.py
├── cache.py             # JsonCache, HomeWikiCache, XtoolsRecentEditCache
├── services.py          # HdpService — domain orchestration
│
├── wiki/
│   ├── client.py        # WikiClient (mwclient)
│   ├── category.py      # CategoryService
│   └── users.py         # UserResolver
│
├── xtools/
│   └── client.py        # XToolsClient (HTTP only)
│
└── parsing/
    ├── links.py         # LinkExtractor
    └── tables.py        # WikiTableColumnManager, WikiTableDataUpdater
```

Supporting folders:

```text
data/          # caches + generated wikitext
tests/         # mirrored package layout
```

---

## Architecture

```text
CLI ──► HdpService
            │
            ├── WikiClient / CategoryService / UserResolver
            ├── HomeWikiCache ──► WikiClient
            ├── XtoolsRecentEditCache ──► XToolsClient
            └── LinkExtractor / WikiTableDataUpdater
```

**Design rules**

1. **Dataclasses** for pure data (`UserInfo`, `ApplicationRow`, `Settings`, `Credentials`).
2. **Classes** for I/O and behaviour (API clients, caches, parsers, service, CLI).
3. **Dependency injection** — `HdpService` receives collaborators; tests can inject fakes.
4. **No network inside pure helpers** — XTools and MediaWiki calls live only in their client classes; the cache layer calls those clients, never HTTP directly.

### Core types

```python
@dataclass(frozen=True)
class UserInfo:
    username: str
    home_wiki: str = ""
    registration: str = ""
    global_editcount: int | None = None
    recent_editcount: int | None = None
    last_edit: str | None = None

@dataclass
class ApplicationRow:
    full_title: str
    sub: str
    page_link: str = ""
    last_update: str = ""
    user_link: str = "unknown"
    country: str = ""
    editcount_str: str = "unknown"
    recent_editcount_str: str = "unknown"
    age: str = ""
    home_wiki: str = "unknown"
    last_edit: str = "unknown"
```

### Typical programmatic use

```python
from hdp import HdpService, Settings

service = HdpService.from_settings()
if service is None:
    raise SystemExit("login failed")

# Generate
text = service.generate(
    "Hardware donation program",
    section_names=[
        "Category:Hardware donation program open requests",
        "Category:Hardware donation program drafts",
    ],
)

# Or update an existing page in place
updated = service.update(
    "User:Mr. Ibrahem/hdp",
    section_names=["Category:Hardware donation program open requests"],
    load_recent_editcounts=False,
)
```

---

## Table columns

| Column                     | Source                                  |
| -------------------------- | --------------------------------------- |
| Page                       | Application subpage link                |
| Last edited to application | `{{REVISIONTIMESTAMP}}` magic word      |
| User                       | Canonical username (redirects resolved) |
| Country                    | Parsed from application wikitext        |
| Global edits               | CentralAuth / `list=globalusers`        |
| Edits in last 3 months     | XTools globalcontribs (cached)          |
| Age of account             | Derived from registration timestamp     |
| Home Wiki                  | CentralAuth `globaluserinfo` (cached)   |
| Last edit _(optional)_     | XTools most recent contribution         |
| Approved                   | Left blank for manual fill              |

---

## Caching behaviour

**Home wiki** — immutable per account. Fetched once, then always served from
`home_wiki_cache.json`.

**Recent edits** — per-day counts with a contiguous `[start, end]` range stored
in `_meta`. On later runs only the missing tail (or front) is requested from
XTools, then merged. Use `--no-recent` to read the cache without any network
calls.

Both caches write atomically (temp file + rename) and flush periodically during
long user lists so a crash does not lose progress.

---

## Testing

```bash
# Unit tests only (network disabled by default)
pytest tests/ -q

# Include live XTools / Meta API tests
pytest tests/ -m network

# Coverage report for src/
pytest tests/unit/config --cov=src/config
pytest tests/unit/cli --cov=src/cli
pytest tests/unit/cache --cov=src/cache
pytest tests/unit/wiki --cov=src/wiki
pytest tests/unit/models --cov=src/models
pytest tests/unit/parsing --cov=src/parsing
pytest tests/unit/services --cov=src/services
pytest tests/unit/xtools --cov=src/xtools

```

Markers:

| Marker        | Meaning                                        |
| ------------- | ---------------------------------------------- |
| `unit`        | Pure unit tests                                |
| `integration` | Multi-component tests                          |
| `network`     | Requires outbound HTTP (deselected by default) |

---

## License

Same as the parent project / Wikimedia tooling conventions for the bot operator.
