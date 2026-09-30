"""
On-disk caches for home-wiki data and recent edit counts.

Network access is delegated to injected ``WikiClient`` / ``XToolsClient``
instances — this module never opens HTTP connections itself beyond those calls.
"""

from __future__ import annotations

import logging
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from tqdm import tqdm

from ..config import RECENT_DAYS
from ..xtools.client import XToolsClient
from .json_cache import JsonCache

logger = logging.getLogger(__name__)

META_KEY = "_meta"

# ---------------------------------------------------------------------------
# Recent edit-count cache
# ---------------------------------------------------------------------------


class RecentEditCache:
    """
    Per-day edit counts backed by XTools, with contiguous range tracking.

    File layout::

        {
          "_meta": {"SomeUser": {"start": "2026-01-01", "end": "2026-06-24"}},
          "SomeUser": {"2026-01-03": 2, "2026-04-21": 5, ...}
        }
    """

    def __init__(
        self,
        path: str | Path,
        xtools: XToolsClient,
        recent_days: int = RECENT_DAYS,
    ):
        self._store = JsonCache(path)
        self._xtools = xtools
        self._recent_days = recent_days

    # -- public ----------------------------------------------------------

__all__ = [
    "RecentEditCache",
]
