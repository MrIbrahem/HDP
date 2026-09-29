# Models & Config

## Goal
Separate constants, configuration, and data models from business logic.

## Target files
- `src/hdp/config.py`
- `src/hdp/models.py`
- `src/hdp/logging_setup.py`

## What moves from the current codebase

### From `src/utils.py` (and related)
| Item | Destination |
|------|-------------|
| `USER_AGENT` | `config.py` |
| `BASE_PAGE` | `config.py` |
| `users_redirects` (dict) | `config.py` or load from `data/users_redirects.json` |
| `load_credentials()` | `config.py` |
| `calculate_age()` | `models.py` (or a small helper used by services) |
| `extract_country()` | Prefer `parsing/` (it operates on wikitext) |

### Additional constants
```python
# config.py
BASE_PAGE = "Hardware donation program"
DEFAULT_CACHE_DIR = "data"
RECENT_DAYS = 90
SECTION_TO_CATEGORY = {
    "Draft requests": "Category:Hardware donation program drafts",
    "Open requests": "Category:Hardware donation program open requests",
    "Approved requests not yet delivered": "Category:Hardware donation program approved requests",
}
```

## Suggested models (`models.py`)

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class UserInfo:
    username: str
    home_wiki: str = ""
    registration: str = ""          # ISO timestamp
    global_editcount: Optional[int] = None
    recent_editcount: Optional[int] = None
    last_edit: Optional[str] = None  # Y-m-d
    age: str = ""

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
```

## Logging
Move `setup_logging()` from `src/__init__.py` into `logging_setup.py` unchanged (or with a slightly clearer name). Keep the project logger namespace as `"hdp"` or `"src.hdp"`.

## Migration notes
1. Create the three files with the constants and dataclasses first.
2. Update imports in the old code gradually so both layouts can coexist.
3. Do not put network or parsing logic in these modules.
