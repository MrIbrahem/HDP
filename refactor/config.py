"""
Configuration, credentials, and project-wide constants for the HDP tools.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Constants (rarely overridden)
# ---------------------------------------------------------------------------

BASE_PAGE = "Hardware donation program"

DEFAULT_CACHE_DIR = Path("data")

RECENT_DAYS = 90

USER_AGENT = (
    "HDP-Bot/2.0 (https://meta.wikimedia.org/wiki/Hardware_donation_program; "
    "contact: meta.wikimedia.org user Mr. Ibrahem)"
)

# Section heading → MediaWiki category (used by subpage discovery)
SECTION_TO_CATEGORY: dict[str, str] = {
    "Draft requests": "Category:Hardware donation program drafts",
    "Open requests": "Category:Hardware donation program open requests",
    "Approved requests not yet delivered": "Category:Hardware donation program approved requests",
}

# Default category list used by generate / update CLI commands
DEFAULT_SECTION_NAMES: list[str] = [
    "Category:Hardware donation program open requests",
    "Category:Hardware donation program approved requests",
    "Category:Hardware donation program drafts",
]

# Static username redirects (lowercase key → canonical display name).
# Prefer loading from data/users_redirects.json when the file exists;
# this dict is the fallback / starter set.
DEFAULT_USERS_REDIRECTS: dict[str, str] = {
    # Add known renames here, e.g.:
    # "oldname": "NewName",
    "vinoda mamatharai": "Vinoda mamatharai",
    "cbrescia": "Felino Volador",
    "abubakar a gwanki": "Gwanki",
    "jaluj i": "Jaluj",
    "the living love": "Em-mustapha",
    "wiki ruhan": "Ruhan",
    "sardeeq": "Sardeeq",
    "muddyb 2": "Muddyb",
    "muralikrishna m": "Muralikrishna m",
    "brazal.dang": "Ballardmaize",
    "babulbaishya": "BabulB",
    "micheal kaluba": "MichealKal",
    "mp1999": "TypeInfo",
    "eugene233 2": "Eugene233",
    "premchand murmu thakur": "Nacharhopon",
    "учитель": "Валентина Кодола",
    "bhupendra shrestha": "श्रेष्ठ भूपेन्द्र",
}

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Settings:
    """Immutable runtime settings. Prefer injecting this instead of reading globals."""

    base_page: str = BASE_PAGE
    recent_days: int = RECENT_DAYS
    cache_dir: Path = DEFAULT_CACHE_DIR
    user_agent: str = USER_AGENT
    section_to_category: Mapping[str, str] = field(default_factory=lambda: dict(SECTION_TO_CATEGORY))
    users_redirects: Mapping[str, str] = field(default_factory=lambda: dict(DEFAULT_USERS_REDIRECTS))

    @property
    def home_wiki_cache_path(self) -> Path:
        return self.cache_dir / "home_wiki_cache.json"

    @property
    def edit_counts_cache_path(self) -> Path:
        return self.cache_dir / "edit_counts_cache.json"

    @property
    def users_redirects_path(self) -> Path:
        return self.cache_dir / "users_redirects.json"

    @classmethod
    def from_env(cls, env_file: str | Path | None = None) -> Settings:
        """
        Build Settings from environment / optional .env file.

        Recognised optional variables:
          HDP_CACHE_DIR, HDP_RECENT_DAYS, HDP_USER_AGENT, HDP_BASE_PAGE
        """
        if env_file is not None:
            load_dotenv(env_file)
        else:
            load_dotenv()

        cache_dir = Path(os.getenv("HDP_CACHE_DIR", str(DEFAULT_CACHE_DIR)))
        recent_days = int(os.getenv("HDP_RECENT_DAYS", str(RECENT_DAYS)))
        user_agent = os.getenv("HDP_USER_AGENT", USER_AGENT)
        base_page = os.getenv("HDP_BASE_PAGE", BASE_PAGE)

        redirects = dict(DEFAULT_USERS_REDIRECTS)
        redirects_path = cache_dir / "users_redirects.json"
        if redirects_path.is_file():
            redirects.update(_load_users_redirects(redirects_path))

        return cls(
            base_page=base_page,
            recent_days=recent_days,
            cache_dir=cache_dir,
            user_agent=user_agent,
            section_to_category=dict(SECTION_TO_CATEGORY),
            users_redirects=redirects,
        )


def _load_users_redirects(path: Path) -> dict[str, str]:
    """Load a JSON object of lowercase-name → canonical-name mappings."""
    import json

    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return {str(k).lower(): str(v) for k, v in data.items()}
    except (OSError, json.JSONDecodeError, TypeError):
        return {}


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Credentials:
    """Bot login credentials for meta.wikimedia.org."""

    username: str
    password: str

    def __bool__(self) -> bool:
        return bool(self.username and self.password)

    @classmethod
    def from_env(cls, env_file: str | Path | None = None) -> Credentials | None:
        """
        Load WIKIPEDIA_BOT_USERNAME / WIKIPEDIA_BOT_PASSWORD from the environment
        (or a .env file). Returns None if either value is missing.
        """
        if env_file is not None:
            load_dotenv(env_file)
        else:
            load_dotenv()

        username = (os.getenv("WIKIPEDIA_BOT_USERNAME") or "").strip()
        password = (os.getenv("WIKIPEDIA_BOT_PASSWORD") or "").strip()
        if not username or not password:
            return None
        return cls(username=username, password=password)


# ---------------------------------------------------------------------------
# Backwards-compatible helpers (thin wrappers used during migration)
# ---------------------------------------------------------------------------


def load_credentials(env_file: str | Path | None = None) -> tuple[str, str]:
    """
    Legacy helper matching the old ``src.utils.load_credentials`` signature.

    Returns ``(username, password)``. Either string may be empty on failure.
    Prefer ``Credentials.from_env()`` in new code.
    """
    creds = Credentials.from_env(env_file)
    if creds is None:
        return "", ""
    return creds.username, creds.password
