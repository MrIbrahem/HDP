

# Class & Dataclass Adoption Plan

## Design principles (aligned with your preference)

1. **Dataclasses** for pure data (immutable or lightly mutable records).
2. **Classes** for anything with behaviour, state, or external I/O (API clients, caches, parsers, services).
3. Prefer **dependency injection**: services receive client/cache instances instead of creating them internally.
4. Keep the package small — one class per clear responsibility; no deep hierarchies.

---

## 1. Models (`src/hdp/models.py`) — dataclasses only

Use `@dataclass` for all domain records. No methods beyond simple derived properties if needed.

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass(frozen=True)
class UserInfo:
    username: str
    home_wiki: str = ""
    registration: str = ""          # ISO timestamp
    global_editcount: Optional[int] = None
    recent_editcount: Optional[int] = None
    last_edit: Optional[str] = None  # Y-m-d

    @property
    def age(self) -> str:
        # thin wrapper around calculate_age(registration)
        ...

@dataclass
class ApplicationRow:
    full_title: str
    sub: str
    page_link: str
    last_update: str
    user_link: str
    country: str = ""
    editcount_str: str = "unknown"
    recent_editcount_str: str = "unknown"
    age: str = ""
    home_wiki: str = "unknown"
    last_edit: str = "unknown"

    def to_table_cells(self) -> dict[str, str]:
        """Map to the keys expected by the table updater."""
        return {
            "page_link": self.page_link,
            "last_update": self.last_update,
            "user_link": self.user_link,
            "country": self.country,
            "editcount_str": self.editcount_str,
            "recent_editcount_str": self.recent_editcount_str,
            "age": self.age,
            "home_wiki": self.home_wiki,
            "last_edit": self.last_edit,
        }
```

**Why dataclass:** these are data carriers. Freezing `UserInfo` is useful because home wiki / registration never change.

---

## 2. Config (`src/hdp/config.py`) — thin class + constants

```python
@dataclass(frozen=True)
class Settings:
    base_page: str = "Hardware donation program"
    recent_days: int = 90
    cache_dir: str = "data"
    user_agent: str = "HDP-Bot/1.0 ..."
    section_to_category: dict[str, str] = field(default_factory=lambda: {...})

    @classmethod
    def from_env(cls) -> "Settings":
        # optional overrides from env / .env
        ...

class Credentials:
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password

    @classmethod
    def from_env(cls) -> "Credentials | None":
        # load_credentials() logic
        ...
```

Keep module-level constants only if they are truly global and never need injection. Prefer passing a `Settings` instance.

---

## 3. Wiki (`src/hdp/wiki/`)

### `client.py` — main class (already exists as `MwclientApi`)

```python
class WikiClient:
    def __init__(self, site: Site):
        self._site = site

    @classmethod
    def connect(cls, credentials: Credentials, user_agent: str) -> "WikiClient | None":
        # connect_to_meta + login
        ...

    def get_page_wikitext(self, title: str) -> str: ...
    def get_pages_wikitext(self, titles: list[str]) -> dict[str, str]: ...
    def get_global_editcounts(self, users: list[str]) -> dict[str, int]: ...
    def get_global_userinfo(self, username: str) -> dict: ...
    def solve_pages_redirects(self, pages: list[str]) -> dict[str, str]: ...
    # keep other methods as needed
```

### `category.py` — class or plain functions

Prefer a small class so it can hold the site and share retry logic:

```python
class CategoryService:
    def __init__(self, site: Site):
        self._site = site

    def count(self, category_name: str) -> int: ...
    def member_titles(self, category_name: str, namespace=None, ...) -> list[str]: ...
```

### `users.py` — class for username resolution

```python
class UserResolver:
    def __init__(self, wiki: WikiClient, static_redirects: dict[str, str]):
        self._wiki = wiki
        self._static = static_redirects

    def normalize(self, raw_name: str) -> str:
        # static redirect + capitalization

    def resolve_batch(self, usernames: list[str]) -> dict[str, str]:
        # API redirects for User: pages
```

---

## 4. XTools (`src/hdp/xtools/client.py`) — client class

```python
class XToolsClient:
    def __init__(self, user_agent: str, timeout: int = 15):
        self._headers = {"User-Agent": user_agent}
        self._timeout = timeout

    def recent_editcount_by_day(self, username: str, start: str, end: str) -> dict[str, int]: ...
    def recent_editcount(self, username: str, start: str, end: str) -> int | None: ...
    def last_edit_timestamp(self, username: str) -> str | None: ...
    def last_edit_timestamps(self, users: list[str]) -> dict[str, str]: ...
```

No caching inside this class. Pure HTTP adapter.

---

## 5. Cache (`src/hdp/cache.py`) — specialized cache classes

```python
class JsonCache:
    """Shared atomic load/save."""
    def __init__(self, path: str):
        self.path = path

    def load(self) -> dict: ...
    def save(self, data: dict) -> None: ...

class HomeWikiCache:
    def __init__(self, path: str, wiki: WikiClient):
        self._store = JsonCache(path)
        self._wiki = wiki

    def get_many(self, users: list[str], save_every: int = 5) -> dict[str, UserInfo]: ...

class XtoolsRecentEditCache:
    def __init__(self, path: str, xtools: XToolsClient, recent_days: int = 90):
        self._store = JsonCache(path)
        self._xtools = xtools
        self._recent_days = recent_days

    def get_many(self, users: list[str], *, offline: bool = False, set_zero: bool = False) -> dict[str, int]: ...
```

This keeps the existing cache file formats while making the “who talks to the network” dependency explicit.

---

## 6. Parsing (`src/hdp/parsing/`)

Already class-based — keep and tighten:

```python
# links.py
class LinkExtractor:
    def get_section(self, wikitext: str, heading: str) -> Section | None: ...
    def extract_subpages(self, base_page: str, section) -> list[str]: ...

# tables.py (existing classes, lightly cleaned)
class WikiTableColumnManager:
    ...

class WikiTableDataUpdater:
    def __init__(self, manager: WikiTableColumnManager | None = None):
        self.manager = manager or WikiTableColumnManager()

    def update(self, rows: dict[str, ApplicationRow], wikitext: str, ...) -> str: ...
```

Optional: a thin `TableBuilder` class that only builds a new table string from rows (current `build_wikitable`).

---

## 7. Services (`src/hdp/services.py`) — orchestrator class

This is the main place where classes pay off.

```python
class HdpService:
    def __init__(
        self,
        wiki: WikiClient,
        category: CategoryService,
        users: UserResolver,
        home_cache: HomeWikiCache,
        recent_cache: XtoolsRecentEditCache,
        xtools: XToolsClient,
        settings: Settings,
        link_extractor: LinkExtractor | None = None,
        table_updater: WikiTableDataUpdater | None = None,
    ):
        ...

    def discover_subpages(self, page_title: str, section_names: list[str]) -> set[str]: ...
    def load_rows(
        self,
        subpages: set[str],
        *,
        load_recent: bool = True,
        load_last_edits: bool = False,
        unknown: str = "unknown",
    ) -> dict[str, ApplicationRow]: ...
    def build_wikitable(self, rows: dict[str, ApplicationRow], *, add_last_edit: bool = False) -> str: ...
    def generate(self, page_title: str, section_names: list[str], **opts) -> str: ...
    def update(self, page_title: str, section_names: list[str], **opts) -> str: ...
```

`load_rows` stays the heart of the service (same steps as current `worker.load_rows`), but now every external dependency is an injected object.

---

## 8. CLI (`src/hdp/cli.py`) — thin class or functions

Either is fine. A small class keeps argument handling and wiring together:

```python
class Cli:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings.from_env()

    def run(self, argv: list[str] | None = None) -> int:
        # argparse + dispatch to generate / update
        ...

    def _build_service(self) -> HdpService:
        # wire WikiClient, caches, etc. once
        ...
```

`__main__.py` simply does `raise SystemExit(Cli().run())`.

---

## Recommended class map (quick reference)

| Responsibility              | Type        | Module              |
|----------------------------|-------------|---------------------|
| Settings / credentials     | dataclass + class | `config.py`    |
| UserInfo, ApplicationRow   | dataclass   | `models.py`         |
| Wiki API                   | class       | `wiki/client.py`    |
| Categories                 | class       | `wiki/category.py`  |
| Username resolution        | class       | `wiki/users.py`     |
| XTools HTTP                | class       | `xtools/client.py`  |
| JSON cache store           | class       | `cache.py`          |
| Home-wiki cache            | class       | `cache.py`          |
| Recent-edits cache         | class       | `cache.py`          |
| Link / section extraction  | class       | `parsing/links.py`  |
| Table structure + update   | class       | `parsing/tables.py` |
| Domain orchestration       | class       | `services.py`       |
| CLI entry                  | class (opt) | `cli.py`            |

---

## Migration order (class-first)

1. **Phase 1** — `config.py` + `models.py` + `logging_setup.py`
   Introduce `Settings`, `Credentials`, `UserInfo`, `ApplicationRow`.

2. **Phase 2** — Wrap existing clients
   - Rename/move `MwclientApi` → `WikiClient`
   - Add `XToolsClient`
   - Add `CategoryService` and `UserResolver`

3. **Phase 3** — Cache classes
   Extract `HomeWikiCache` and `XtoolsRecentEditCache` on top of the current JSON logic.

4. **Phase 4** — Parsing classes (already mostly done)
   Clean imports and accept `ApplicationRow` where useful.

5. **Phase 5** — `HdpService`
   Move `load_rows` / generate / update into the service; inject all clients.

6. **Phase 6** — CLI + delete old entry points

---

## What stays as plain functions

- Pure helpers with no state: `calculate_age`, `extract_country`, ISO date helpers, simple string normalization.
- Small module-level factories if a full class would be overkill (e.g. `load_dates()`).

Everything that talks to the network, the filesystem, or orchestrates multiple steps becomes a class.

---

