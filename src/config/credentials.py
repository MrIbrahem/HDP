"""
Credentials for the HDP tools.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

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
    def load(cls) -> Credentials | None:
        username = (os.getenv("WIKIPEDIA_BOT_USERNAME") or "").strip()
        password = (os.getenv("WIKIPEDIA_BOT_PASSWORD") or "").strip()
        if not username or not password:
            return None
        return cls(username=username, password=password)

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

        return cls.load()


__all__ = [
    "Credentials",
]
