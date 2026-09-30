"""
Domain data models for the Hardware Donation Program tools.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


def calculate_age(registration: str) -> str:
    """
    Input example:
        registration: "2008-07-24T01:18:05Z"
    Returns example:
        {{age in years and months |2008|07|24}}
    """
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
    last_edit: str | None = None  # Y-m-d

    @property
    def age(self) -> str:
        return calculate_age(self.registration)

    def with_editcounts(
        self,
        *,
        global_editcount: int | None = None,
        recent_editcount: int | None = None,
        last_edit: str | None = None,
    ) -> UserInfo:
        """Return a new instance with updated edit-count fields."""
        return UserInfo(
            username=self.username,
            home_wiki=self.home_wiki,
            registration=self.registration,
            global_editcount=(global_editcount if global_editcount is not None else self.global_editcount),
            recent_editcount=(recent_editcount if recent_editcount is not None else self.recent_editcount),
            last_edit=last_edit if last_edit is not None else self.last_edit,
        )

    @classmethod
    def from_globaluserinfo(cls, username: str, info: Mapping[str, Any]) -> UserInfo:
        """Build from the dict returned by ``meta=globaluserinfo``."""
        return cls(
            username=username,
            home_wiki=str(info.get("home") or ""),
            registration=str(info.get("registration") or ""),
            global_editcount=_as_optional_int(info.get("editcount")),
        )


def _as_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


__all__ = [
    "UserInfo",
    "calculate_age",
]
