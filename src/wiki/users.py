"""
Username normalisation and redirect resolution.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping

from .client import WikiClient

logger = logging.getLogger(__name__)


class UserResolver:
    """
    Resolve raw application subpage names to canonical usernames.

    Combines a static redirect map (from config / JSON) with live
    ``User:`` page redirect lookups on the wiki.
    """

    def __init__(
        self,
        wiki: WikiClient,
        static_redirects: Mapping[str, str] | None = None,
    ):
        self._wiki = wiki
        self._static = {k.lower(): v for k, v in (static_redirects or {}).items()}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------


__all__ = ["UserResolver"]
