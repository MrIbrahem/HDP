"""
Domain data models for the Hardware Donation Program tools.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


def calculate_age_new(registration: str) -> str:
    """
    Turn a CentralAuth registration timestamp into a human-readable age string.

    Accepts values such as ``"2008-07-24T01:18:05Z"`` or ``"2008-07-24"``.
    Returns ``""`` when the input cannot be parsed.
    """
    if not registration:
        return ""

    raw = registration.strip()
    # Normalise trailing Z / missing time component
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    if "T" not in raw:
        raw = raw + "T00:00:00+00:00"

    try:
        registered = datetime.fromisoformat(raw)
    except ValueError:
        return ""

    if registered.tzinfo is None:
        registered = registered.replace(tzinfo=UTC)

    now = datetime.now(UTC)
    if registered > now:
        return ""

    delta = now - registered
    years = delta.days // 365
    months = (delta.days % 365) // 30

    if years >= 1:
        if months > 0:
            return f"{years}y {months}m"
        return f"{years}y"
    if months >= 1:
        days = delta.days % 30
        if days > 0:
            return f"{months}m {days}d"
        return f"{months}m"
    return f"{delta.days}d"


def calculate_age(registration: str) -> str:
    """
    Input example:
        registration: "2008-07-24T01:18:05Z"
    Returns example:
        {{age in years and months |2008|07|24}}
    """
    if not registration:
        return ""

    try:
        # Parse the ISO 8601 string into a datetime object
        # Replacing 'Z' with '+00:00' to ensure compatibility with fromisoformat
        reg_date = datetime.fromisoformat(registration.replace("Z", "+00:00"))

        # Extract year, month, and day with zero-padding for month and day
        year = reg_date.year
        month = f"{reg_date.month:02d}"
        day = f"{reg_date.day:02d}"

        # Return the formatted template string
        return f"{{{{age in years and months|{year}|{month}|{day}}}}}"

    except Exception as e:
        logger.error(f"Error formatting age template: {e}")

        # Fallback template format in case of an error
        return registration


def _as_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# UserInfo
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class UserInfo:
    """
    Immutable snapshot of a Wikimedia user's global account data.

    ``home_wiki`` and ``registration`` come from CentralAuth and never change
    for a given account, which is why this model is frozen and suitable for
    long-lived caching.
    """

    username: str
    home_wiki: str = ""
    registration: str = ""  # ISO timestamp from CentralAuth
    global_editcount: int | None = None
    recent_editcount: int | None = None
    wikidata_count: int | None = None
    last_edit: str | None = None  # Y-m-d

    @property
    def age(self) -> str:
        return calculate_age(self.registration)

    @property
    def global_without_wikidata_str(self) -> str:
        if self.global_editcount is not None and self.wikidata_count is not None:
            global_without_wikidata = max(0, self.global_editcount - self.wikidata_count)
            return f"{global_without_wikidata:,}"

        return ""

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_globaluserinfo(cls, username: str, info: Mapping[str, Any]) -> UserInfo:
        """
        Build from the dict returned by ``meta=globaluserinfo``.

        info example:
        { "home": "enwiki", "id": 26378, "registration": "2008-07-24T01:18:05Z", "name": "Doc James", "editcount": 2066486 }
        """
        return cls(
            username=username,
            home_wiki=str(info.get("home") or ""),
            registration=str(info.get("registration") or ""),
            global_editcount=_as_optional_int(info.get("editcount")),
        )

    def with_editcounts(
        self,
        *,
        global_editcount: int | None = None,
        recent_editcount: int | None = None,
        wikidata_count: int | None = None,
        last_edit: str | None = None,
    ) -> UserInfo:
        """Return a new instance with updated edit-count fields."""
        return UserInfo(
            username=self.username,
            home_wiki=self.home_wiki,
            registration=self.registration,
            global_editcount=(global_editcount if global_editcount is not None else self.global_editcount),
            recent_editcount=(recent_editcount if recent_editcount is not None else self.recent_editcount),
            wikidata_count=(wikidata_count if wikidata_count is not None else self.wikidata_count),
            last_edit=last_edit if last_edit is not None else self.last_edit,
        )


__all__ = [
    "UserInfo",
]
