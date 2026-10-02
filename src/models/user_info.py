"""
Domain data models for the Hardware Donation Program tools.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from typing import Any

logger = logging.getLogger(__name__)


def calculate_age_new(registration: str, today: str | date | None = None) -> str:
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

    if today is None:
        today = datetime.now(UTC)
    elif isinstance(today, str):
        today = datetime.fromisoformat(today)

    if registered > today:
        return ""

    delta = today - registered
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


@dataclass  # (frozen=True)
class UserInfo:
    """
    Immutable snapshot of a Wikimedia user's global account data.

    ``home_wiki`` and ``registration`` come from CentralAuth and never change
    for a given account, which is why this model is frozen and suitable for
    long-lived caching.
    """

    username: str
    refirect_username: str = ""
    home_wiki: str = ""
    registration: str = ""  # ISO timestamp from CentralAuth
    global_editcount: int | None = None
    recent_editcount: int | None = None
    wikidata_count: int | None = None
    last_edit: str | None = None  # Y-m-d

    def update_username(self, username: str) -> None:
        self.refirect_username = self.username
        self.username = username

    def to_json(self) -> dict[str, Any]:
        data = asdict(self)
        data["user_link"] = self.user_link
        data["age"] = self.age
        data["global_without_wikidata_str"] = self.global_without_wikidata_str
        data["global_editcount_str"] = self.global_editcount_str
        data["recent_editcount_str"] = self.recent_editcount_str
        data["wikidata_editcount_str"] = self.wikidata_editcount_str
        return data

    @property
    def user_link(self) -> str:
        return f"[[User:{self.username}]]" if self.username else None

    @property
    def age(self) -> str:
        return calculate_age(self.registration)

    @property
    def global_without_wikidata_str(self) -> str:
        if self.global_editcount is not None and self.wikidata_count is not None:
            global_without_wikidata = max(0, self.global_editcount - self.wikidata_count)
            return f"{global_without_wikidata:,}"

        return ""

    @property
    def global_editcount_str(self) -> str:
        if self.global_editcount is not None:
            return f"{self.global_editcount:,}"
        return ""

    @property
    def recent_editcount_str(self) -> str:
        if self.recent_editcount is not None:
            return f"{self.recent_editcount:,}"
        return ""

    @property
    def wikidata_editcount_str(self) -> str:
        if self.wikidata_count is not None:
            return f"{self.wikidata_count:,}"
        return ""

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    def update(
        self,
        *,
        globaluser_data: Mapping[str, Any],
        global_editcount: int | None = None,
        recent_editcount: int | None = None,
        wikidata_count: int | None = None,
        last_edit: str | None = None,
    ) -> UserInfo:
        """Return a new instance with updated edit-count fields."""
        globaluser_data = globaluser_data or {}

        home_wiki = str(globaluser_data.get("home") or "")
        if home_wiki:
            self.home_wiki = home_wiki

        registration = str(globaluser_data.get("registration") or "")
        if registration:
            self.registration = registration

        global_editcount = global_editcount or globaluser_data.get("editcount")

        if global_editcount and global_editcount is not None:
            self.global_editcount = _as_optional_int(global_editcount)

        if recent_editcount is not None:
            self.recent_editcount = recent_editcount

        if wikidata_count is not None:
            self.wikidata_count = wikidata_count

        if last_edit is not None:
            self.last_edit = last_edit

        return self

    # ------------------------------------------------------------------
    # Table / export helpers
    # ------------------------------------------------------------------

    def to_table_dict(self, unknown: str = "unknown") -> dict[str, str]:
        """
        Dict of header-key → cell value expected by ``WikiTableDataUpdater``
        and ``ApplicationTable.build_wikitable``.
        """
        return {
            "global_editcount_str": self.global_editcount_str or unknown,
            "recent_editcount_str": self.recent_editcount_str or unknown,
            "wikidata_editcount_str": self.wikidata_editcount_str or unknown,
            "global_without_wikidata_str": self.global_without_wikidata_str,
            "user_link": self.user_link or unknown,
            "age": self.age,
            "home_wiki": self.home_wiki or unknown,
            "last_edit": self.last_edit or unknown,
        }


__all__ = [
    "UserInfo",
]
