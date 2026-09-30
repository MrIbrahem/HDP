"""
Domain data models for the Hardware Donation Program tools.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .user_info import UserInfo

# ---------------------------------------------------------------------------
# Pure helpers used by the models
# ---------------------------------------------------------------------------


def extract_country(wikitext: str) -> str:
    """
    Extract the applicant country from an HDP application page.

    Looks for a line matching the application template field::

        ; country your from: Rwanda

    Case-insensitive; returns the trimmed value or ``""`` when absent.

    Handles patterns like:
        ; country your from:Rwanda
        ;country your from: Rwanda
        ; Country your from: Germany
    """

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
    global_without_wikidata_str: str = ""
    recent_editcount_str: str = "unknown"
    wikidata_editcount_str: str = "unknown"

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
        sub = sub.replace("_", " ")
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

        if info.wikidata_count is not None:
            self.wikidata_editcount_str = f"{info.wikidata_count:,}"
        else:
            self.wikidata_editcount_str = unknown

        if info.last_edit:
            self.last_edit = info.last_edit
        else:
            self.last_edit = unknown

        self.global_without_wikidata_str = info.global_without_wikidata_str

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


__all__ = [
    "extract_country",
    "ApplicationRow",
]
