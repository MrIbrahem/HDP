"""
On-disk caches for home-wiki data and recent edit counts.

Network access is delegated to injected ``WikiClient`` / ``XToolsClient``
instances — this module never opens HTTP connections itself beyond those calls.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_CACHE_PATH = "data/home_wiki_cache.json"

# ---------------------------------------------------------------------------
# Shared JSON store
# ---------------------------------------------------------------------------


class JsonCache:
    """Atomic load / save of a JSON object."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self, default: dict | None = None) -> dict:
        """
        Load the cache file, returning an empty dict if it doesn't exist.
        """
        if not self.path.exists():
            return {} if default is None else dict(default)

        try:
            with self.path.open(encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else ({} if default is None else dict(default))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Could not read %s (%s); starting fresh", self.path, e)
            return {} if default is None else dict(default)

    def save(self, data: dict) -> None:
        """
        Write the cache atomically (write to temp file, then rename).
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True, ensure_ascii=False)
        os.replace(tmp, self.path)


def load_cache(cache_path: str = DEFAULT_CACHE_PATH) -> dict:
    """Load the cache file, returning an empty dict if it doesn't exist."""
    return JsonCache(cache_path).load()


def save_cache(cache: dict, cache_path: str = DEFAULT_CACHE_PATH) -> None:
    """Write the cache atomically (write to temp file, then rename)."""
    return JsonCache(cache_path).save(cache)


__all__ = [
    "JsonCache",
    "load_cache",
    "save_cache",
]
