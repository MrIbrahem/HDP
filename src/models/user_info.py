"""
Domain data models for the Hardware Donation Program tools.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


def format_count(value: int | None) -> str:
    """Format a numeric count with thousands separators."""
    return f"{value:,}" if value is not None else ""


def calculate_age(registration: str) -> str:
    """
    Convert a Wikimedia registration timestamp to a MediaWiki age template.

    Input example:
        "2008-07-24T01:18:05Z"

    Output example:
        "{{age in years and months|2008|07|24}}"
    """
    if not registration:
        return ""

    try:
        # Replace UTC "Z" with an explicit offset for fromisoformat().
        reg_date = datetime.fromisoformat(registration.replace("Z", "+00:00"))
    except ValueError:
        logger.error("Invalid registration date: %s", registration)
        return registration

    return f"{{{{age in years and months|{reg_date.year}|{reg_date.month:02d}|{reg_date.day:02d}}}}}"


def _as_optional_int(value: Any) -> int | None:
    """Convert a value to int, returning None when conversion fails."""
    if value is None:
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@dataclass
class UserInfo:
    """
    Mutable snapshot of a Wikimedia user's global account data.

    ``home_wiki`` and ``registration`` come from CentralAuth and are
    generally stable for a given account.
    """

    username: str
    # FIXME: Rename "refirect_username" to "redirect_username" after checking
    # all consumers, serialized data, templates, and persisted data.
    refirect_username: str = ""

    home_wiki: str = ""
    registration: str = ""

    global_editcount: int | None = None
    recent_editcount: int | None = None
    recent_wikidata_editcount: int | None = None
    wikidata_count: int | None = None

    last_edit: str | None = None

    def update_username(self, username: str) -> None:
        """Update the username while preserving the previous username."""
        self.refirect_username = self.username
        self.username = username

    def to_json(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the user."""
        data = asdict(self)

        data["user_link"] = self.user_link
        data["age"] = self.age
        data["global_without_wikidata_str"] = self.global_without_wikidata_str
        data["global_editcount_str"] = self.global_editcount_str
        data["recent_editcount_str"] = self.recent_editcount_str
        data["recent_wikidata_editcount_str"] = self.recent_wikidata_editcount_str
        data["wikidata_editcount_str"] = self.wikidata_editcount_str

        return data

    @property
    def user_link(self) -> str | None:
        """Return the MediaWiki user-link for the current username."""
        return f"[[User:{self.username}]]" if self.username else None

    @property
    def age(self) -> str:
        """Return the user's registration date as a MediaWiki age template."""
        return calculate_age(self.registration)

    @property
    def global_without_wikidata_str(self) -> str:
        """
        Return global edits excluding Wikidata edits.

        Returns an empty string when either count is unavailable.
        """
        if self.global_editcount is None or self.wikidata_count is None:
            return ""

        count = max(0, self.global_editcount - self.wikidata_count)
        return format_count(count)

    @property
    def global_editcount_str(self) -> str:
        """Return the formatted global edit count."""
        return format_count(self.global_editcount)

    @property
    def recent_editcount_str(self) -> str:
        """Return the formatted recent edit count."""
        return format_count(self.recent_editcount)

    @property
    def recent_wikidata_editcount_str(self) -> str:
        """Return the formatted recent Wikidata edit count."""
        return format_count(self.recent_wikidata_editcount)

    @property
    def wikidata_editcount_str(self) -> str:
        """Return the formatted Wikidata edit count."""
        return format_count(self.wikidata_count)

    # ------------------------------------------------------------------
    # Update helpers
    # ------------------------------------------------------------------

    def update(
        self,
        *,
        globaluser_data: Mapping[str, Any] | None = None,
        global_editcount: int | None = None,
        recent_editcount: int | None = None,
        recent_wikidata_editcount: int | None = None,
        wikidata_count: int | None = None,
        last_edit: str | None = None,
    ) -> UserInfo:
        """
        Update available user data and return this instance.

        Only values explicitly supplied or available in ``globaluser_data``
        are used to update the corresponding fields.
        """
        data = globaluser_data or {}

        home_wiki = str(data.get("home") or "")
        if home_wiki:
            self.home_wiki = home_wiki

        registration = str(data.get("registration") or "")
        if registration:
            self.registration = registration

        # NOTE: Use "is None" instead of "or" so that a valid count of 0
        # is not accidentally ignored.
        if global_editcount is None:
            global_editcount = data.get("editcount")

        if global_editcount is not None:
            parsed_global_editcount = _as_optional_int(global_editcount)
            if parsed_global_editcount is not None:
                self.global_editcount = parsed_global_editcount

        if recent_editcount is not None:
            self.recent_editcount = recent_editcount

        if recent_wikidata_editcount is not None:
            self.recent_wikidata_editcount = recent_wikidata_editcount

        if wikidata_count is not None:
            self.wikidata_count = wikidata_count

        if last_edit is not None:
            self.last_edit = last_edit

        return self

    # TODO: Consider whether "update()" should return None instead of self.
    # Returning self is retained for backward compatibility and possible
    # method chaining.

    # ------------------------------------------------------------------
    # Table / export helpers
    # ------------------------------------------------------------------

    def to_table_dict(self, unknown: str = "unknown") -> dict[str, str]:
        """
        Return values expected by ``WikiTableDataUpdater`` and
        ``ApplicationTable.build_wikitable``.
        """
        return {
            "global_editcount_str": self.global_editcount_str or unknown,
            "recent_editcount_str": self.recent_editcount_str or unknown,
            "recent_wikidata_editcount_str": (self.recent_wikidata_editcount_str or unknown),
            "wikidata_editcount_str": self.wikidata_editcount_str or unknown,
            "global_without_wikidata_str": self.global_without_wikidata_str,
            "user_link": self.user_link or unknown,
            "age": self.age,
            "home_wiki": self.home_wiki or unknown,
            "last_edit": self.last_edit or unknown,
        }


__all__ = [
    "UserInfo",
    "calculate_age",
    "format_count",
]
