
# HDP Refactoring Plan

This document outlines the high-level plan to restructure the Hardware Donation Program (HDP) tools into a cleaner, more maintainable layout.

The goal is a **lightweight** architecture suitable for the current project size:
- Clear separation of concerns
- Prefer classes where they add real value
- Minimal number of files/folders
- Easy incremental migration from the existing codebase

---

## Target Structure

```text
src/hdp/
├── __init__.py
├── __main__.py
├── config.py
├── logging_setup.py
├── models.py
├── cache.py
├── services.py
├── cli.py
│
├── wiki/
│   ├── __init__.py
│   ├── client.py
│   ├── category.py
│   └── users.py
│
├── xtools/
│   ├── __init__.py
│   └── client.py
│
└── parsing/
    ├── __init__.py
    ├── links.py
    └── tables.py
```

Supporting folders:
```text
data/                  # caches + users_redirects.json
tests/                 # mirrored structure
refactor/              # this planning folder
```

---

## High-Level Migration Phases

### Phase 1 – Foundation
- Create the new package layout (`src/hdp/`)
- Add `config.py`, `logging_setup.py`, and `models.py`
- Move constants (`BASE_PAGE`, `USER_AGENT`, etc.)

### Phase 2 – Infrastructure
- Migrate MediaWiki-related code → `wiki/`
- Migrate XTools-related code → `xtools/`
- Unify caching logic → `cache.py`

### Phase 3 – Parsing & Domain Logic
- Move wikitext parsing → `parsing/`
- Centralize row building and table generation → `services.py`

### Phase 4 – Entry Points
- Replace `run.py` and `update.py` with a single CLI (`cli.py`)
- Support `python -m hdp generate` and `python -m hdp update`

### Phase 5 – Cleanup & Tests
- Remove old `v1.py`, duplicated helpers, and legacy paths
- Update tests to match the new layout
- Final documentation pass

---

## Module Plans

Detailed refactoring plans for each area:

| Module | Plan Document |
|--------|---------------|
| Models & Config | [models/README.md](../../src/models/README.md) |
| Wiki Client | [wiki/README.md](../../src/wiki/README.md) |
| XTools | [xtools/README.md](../../src/xtools/README.md) |
| Cache | [cache/README.md](../../src/cache/README.md) |
| Parsing | [parsing/README.md](../../src/parsing/README.md) |
| Services | [services/README.md](../../src/services/README.md) |
| CLI | [cli/README.md](../../src/cli/README.md) |

---

## Mapping: Old → New (Quick Reference)

| Old Location | New Location |
|--------------|--------------|
| `src/utils.py` | `config.py` + `models.py` + `cache.py` / `wiki/users.py` |
| `src/api/mwclient_req.py` | `wiki/client.py` + `wiki/users.py` |
| `src/api/category.py` | `wiki/category.py` |
| `src/api/home_wiki_cached.py` | `cache.py` |
| `src/api/xtools*.py` | `xtools/client.py` + `cache.py` |
| `src/load_subpages.py` | `services.py` + `parsing/links.py` |
| `src/v3/worker.py` | `services.py` |
| `src/v3/tables_builder.py` | `services.py` |
| `src/v3/v3_main.py` + `v3_update.py` | `services.py` + `cli.py` |
| `src/wtp_parse/*` | `parsing/links.py` + `parsing/tables.py` |
| `run.py` / `update.py` | `cli.py` |

---

## Design Principles

1. **Keep it small** – Avoid deep nesting and unnecessary abstraction layers.
2. **Classes where useful** – Use classes for clients, services, and stateful components. Plain functions are fine for simple helpers.
3. **Single responsibility** – Each module should have one clear reason to change.
4. **Incremental** – Old and new code can coexist during migration.
5. **Testable** – Prefer dependency injection (pass clients into services).

---

## Next Steps

1. Review and adjust the individual module plans in the subfolders.
2. Start with Phase 1 (config + models).
3. Open small PRs per phase or per module.

