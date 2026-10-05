"""
Username normalisation and redirect resolution.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
import re

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
        wiki_client: WikiClient,
        static_redirects: Mapping[str, str] | None = None,
    ) -> None:
        self.wiki_client = wiki_client
        self._static = {k.lower(): v for k, v in (static_redirects or {}).items()}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def normalize(self, raw_name: str) -> str:
        """
        Apply static redirects and capitalise the first letter.

        Empty input stays empty.
        """
        if not raw_name:
            return ""

        cleaned = raw_name.replace("_", " ")

        # Strip common application-page suffixes before lookup
        cleaned = re.sub(r"\(\d\w+ Application\)", "", cleaned, flags=re.I)

        cleaned = cleaned.split("/")[0].strip()
        resolved = self._static.get(cleaned.lower()) or cleaned

        # first letter upper (guard against empty username)
        if resolved:
            resolved = resolved[0].upper() + resolved[1:]
        return resolved

    def resolve_batch(self, usernames: Sequence[str]) -> dict[str, str]:
        """
        Resolve ``User:`` page redirects for a batch of usernames.

        Returns ``{original_username: canonical_username}`` for those that
        actually redirect. Usernames that are not redirects are omitted.
        """
        titles = [f"User:{u}" for u in usernames if u]
        if not titles:
            logger.debug("No usernames provided, returning empty dict")
            return {}

        live_redirects = self.wiki_client.solve_pages_redirects(titles)

        result: dict[str, str] = {}
        for src, dst in live_redirects.items():
            # src / dst look like "User:Foo"
            src_name = src.removeprefix("User:")
            dst_name = dst.removeprefix("User:")
            if src_name != dst_name:
                result[src_name] = dst_name
                if src_name == "Johnjoy12":
                    logger.info("Johnjoy12 is a redirect to %s", dst_name)

        return result

    def normalize_and_resolve(
        self,
        raw_names: Sequence[str],
    ) -> list[str]:
        """
        Full pipeline: static normalise → live redirect resolve → list of
        canonical usernames (same order as input, empties preserved).
        """
        normalized = [self.normalize(n) for n in raw_names]
        live = self.resolve_batch([n for n in normalized if n])
        return [live.get(n, n) for n in normalized]


__all__ = ["UserResolver"]
