"""
Configuration, and project-wide constants for the HDP tools.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from .credentials import Credentials

from .constants import (
    BASE_PAGE,
    DEFAULT_USERS_REDIRECTS,
    RECENT_DAYS,
    SECTION_TO_CATEGORY,
    USER_AGENT,
)

logger = logging.getLogger(__name__)

TQDM_DISABLE = not sys.stderr.isatty()

DEFAULT_CACHE_DIR = Path("data")

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


def _load_users_redirects(path: Path) -> dict[str, str]:
    """Load a JSON object of lowercase-name → canonical-name mappings."""

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


@dataclass(frozen=True)
class Settings:
    """Immutable runtime settings. Prefer injecting this instead of reading globals."""

    credentials: Credentials
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

    def write_to_cache_dir(self, path: str, text: str) -> None:
        out = self.cache_dir / path
        out.parent.mkdir(parents=True, exist_ok=True)

        out.write_text(text, encoding="utf-8")
        logger.info("Saved to %s", out.resolve())

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, cache_dir: Path | None = None) -> Settings:
        return cls(
            credentials=Credentials.load(),
            cache_dir=cache_dir,
        )

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

        credentials = Credentials.load()

        cache_dir = Path(os.getenv("HDP_CACHE_DIR", str(DEFAULT_CACHE_DIR)))
        recent_days = int(os.getenv("HDP_RECENT_DAYS", str(RECENT_DAYS)))
        user_agent = os.getenv("HDP_USER_AGENT", USER_AGENT)
        base_page = os.getenv("HDP_BASE_PAGE", BASE_PAGE)

        redirects = dict(DEFAULT_USERS_REDIRECTS)

        redirects_path = cache_dir / "users_redirects.json"
        if redirects_path.is_file():
            redirects.update(_load_users_redirects(redirects_path))

        return cls(
            credentials=credentials,
            base_page=base_page,
            recent_days=recent_days,
            cache_dir=cache_dir,
            user_agent=user_agent,
            section_to_category=dict(SECTION_TO_CATEGORY),
            users_redirects=redirects,
        )


__all__ = [
    "TQDM_DISABLE",
    "Settings",
]
