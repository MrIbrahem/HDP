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

    def normalize(self, raw_name: str) -> str:
        """
        Apply static redirects and capitalise the first letter.

        Empty input stays empty.
        """
        if not raw_name:
            return ""

        raw_name = raw_name.replace("_", " ")
        # Strip common application-page suffixes before lookup
        cleaned = raw_name.replace("(2nd Application)", "").split("/")[0].strip()
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
            return {}

        live_redirects = self._wiki.solve_pages_redirects(usernames)

        new_data = []
        for x in usernames:
            username = x["username"]
            user_str = f"User:{username}"
            if live_redirects.get(user_str):
                x["username"] = live_redirects[user_str].removeprefix("User:")

                if user_str == "User:Johnjoy12":
                    logger.info(f"Johnjoy12 is a redirect to {x['username']}")
                    logger.info(x)

            new_data.append(x)

__all__ = ["UserResolver"]
