"""
Configuration, credentials, and project-wide constants for the HDP tools.
"""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


TQDM_DISABLE = not sys.stderr.isatty()

# ---------------------------------------------------------------------------
# Header ↔ row-key mapping used when updating existing wikitables
# ---------------------------------------------------------------------------

TABLE_HEADERS_TO_ROW_KEY: dict[str, str] = {
    "Page": "page_link",
    "Last edited to application": "last_update",
    "User": "user_link",
    "Country": "country",
    "Global edits": "global_editcount_str",
    "Global edits without wikidata": "global_without_wikidata_str",
    "Wikidata edits": "wikidata_editcount_str",
    "Edits in last 3 months": "recent_editcount_str",
    "Age of account": "age",
    "Home Wiki": "home_wiki",
    "Last edit": "last_edit",
}

# ---------------------------------------------------------------------------
# Constants (rarely overridden)
# ---------------------------------------------------------------------------

XTOOLS_GLOBALCONTRIBS_URL = "https://xtools.wmcloud.org/api/user/globalcontribs"

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

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

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

    def write_to_cache_dir(self, path: str, text: str) -> None:
        out = self.cache_dir / path
        out.parent.mkdir(parents=True, exist_ok=True)

        out.write_text(text, encoding="utf-8")
        logger.info("Saved to %s", out.resolve())


def _load_users_redirects(path: Path) -> dict[str, str]:
    """Load a JSON object of lowercase-name → canonical-name mappings."""
    import json

    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            logger.warning("users_redirects.json is not a JSON object, type: %s", type(data))
            return {}
        return {str(k).lower(): str(v) for k, v in data.items()}
    except (OSError, json.JSONDecodeError, TypeError):
        logger.warning("Failed to load users redirects from %s", path)
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

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

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


__all__ = [
    "TQDM_DISABLE",
    "Credentials",
    "Settings",
    "TABLE_HEADERS_TO_ROW_KEY",
    "DEFAULT_USERS_REDIRECTS",
]
