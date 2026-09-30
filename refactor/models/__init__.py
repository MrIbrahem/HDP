"""
Domain data models for the Hardware Donation Program tools.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Optional
from collections.abc import Mapping

# ---------------------------------------------------------------------------
# Pure helpers used by the models
# ---------------------------------------------------------------------------


def calculate_age(registration: str) -> str:
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


def extract_country(wikitext: str) -> str:
    """
    Extract the applicant country from an HDP application page.

    Looks for a line matching the application template field::

        ; country your from: Rwanda

    Case-insensitive; returns the trimmed value or ``""`` when absent.
    """
    import re

    if not wikitext:
        return ""

    # Allow optional spaces around the semicolon and colon.
    pattern = re.compile(
        r";\s*country\s+your\s+from\s*:\s*(.+)",
        re.IGNORECASE,
    )
    match = pattern.search(wikitext)
    if not match:
        return ""

    value = match.group(1).splitlines()[0]
    return value.strip().rstrip("\r")


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


# ---------------------------------------------------------------------------
# ApplicationRow
# ---------------------------------------------------------------------------


@dataclass
class ApplicationRow:
    """
    One row in an HDP tracking table (one donation application page).

    Field names match the keys used by the table builder / updater so the
    same object can be passed straight through to wikitext generation.
    """

    full_title: str
    sub: str
    page_link: str = ""
    last_update: str = ""
    user_link: str = "unknown"
    country: str = ""
    editcount_str: str = "unknown"
    recent_editcount_str: str = "unknown"
    age: str = ""
    home_wiki: str = "unknown"
    last_edit: str = "unknown"
    username: str = ""

    def __post_init__(self) -> None:
        if not self.page_link and self.full_title:
            self.page_link = f"[[{self.full_title}]]"
        if not self.last_update and self.full_title:
            self.last_update = f"{{{{#time:Y-m-d|{{{{REVISIONTIMESTAMP:{self.full_title}}}}}}}}}"

    # ------------------------------------------------------------------
    # Factory helpers
    # ------------------------------------------------------------------

    @classmethod
    def from_subpage(
        cls,
        sub: str,
        *,
        base_page: str,
        username: str = "",
        unknown: str = "unknown",
    ) -> ApplicationRow:
        """Create a minimal row from a subpage name (before enrichment)."""
        full_title = f"{base_page}/{sub}"
        user_link = f"[[User:{username}]]" if username else unknown
        return cls(
            full_title=full_title,
            sub=sub,
            username=username,
            user_link=user_link,
            editcount_str=unknown,
            recent_editcount_str=unknown,
            home_wiki=unknown,
            last_edit=unknown,
        )

    def apply_user_info(
        self,
        info: UserInfo,
        *,
        unknown: str = "unknown",
    ) -> ApplicationRow:
        """Fill user-related columns from a ``UserInfo`` snapshot."""
        self.username = info.username
        self.user_link = f"[[User:{info.username}]]" if info.username else unknown
        self.home_wiki = info.home_wiki or unknown
        self.age = info.age

        if isinstance(info.global_editcount, int):
            self.editcount_str = f"{info.global_editcount:,}"
        else:
            self.editcount_str = unknown

        if info.recent_editcount is not None:
            self.recent_editcount_str = f"{info.recent_editcount:,}"
        else:
            self.recent_editcount_str = unknown

        if info.last_edit:
            self.last_edit = info.last_edit
        else:
            self.last_edit = unknown

        return self

    def apply_country(self, wikitext: str) -> ApplicationRow:
        """Extract and set the country field from application wikitext."""
        self.country = extract_country(wikitext)
        return self

    # ------------------------------------------------------------------
    # Table / export helpers
    # ------------------------------------------------------------------

    def to_table_dict(self) -> dict[str, str]:
        """
        Dict of header-key → cell value expected by ``WikiTableDataUpdater``
        and ``build_wikitable``.
        """
        return {
            "page_link": self.page_link,
            "last_update": self.last_update,
            "user_link": self.user_link,
            "country": self.country,
            "editcount_str": self.editcount_str,
            "recent_editcount_str": self.recent_editcount_str,
            "age": self.age,
            "home_wiki": self.home_wiki,
            "last_edit": self.last_edit,
        }

    def as_mapping(self) -> dict[str, Any]:
        """Full field dump (useful for debugging / JSON export)."""
        return {
            "full_title": self.full_title,
            "sub": self.sub,
            "username": self.username,
            **self.to_table_dict(),
        }


# ---------------------------------------------------------------------------
# Header ↔ row-key mapping used when updating existing wikitables
# ---------------------------------------------------------------------------

TABLE_HEADERS_TO_ROW_KEY: dict[str, str] = {
    "Page": "page_link",
    "Last edited to application": "last_update",
    "User": "user_link",
    "Country": "country",
    "Global edits": "editcount_str",
    "Edits in last 3 months": "recent_editcount_str",
    "Age of account": "age",
    "Home Wiki": "home_wiki",
    "Last edit": "last_edit",
}


__all__ = [
    "UserInfo",
    "ApplicationRow",
    "TABLE_HEADERS_TO_ROW_KEY",
    "calculate_age",
    "extract_country",
]
