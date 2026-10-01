"""
Domain data models for the Hardware Donation Program tools.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
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

    value = match.group(1).strip()
    # Take only the first line (strip trailing wikitext artifacts)
    value = value.splitlines()[0]
    # Remove trailing carriage return if present
    return value.strip().rstrip("\r").strip()


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

    user_info: UserInfo
    full_title: str
    sub: str
    country: str = ""

    @property
    def username(self) -> str | None:
        return self.user_info.username

    @property
    def last_edit(self) -> str | None:
        return self.user_info.last_edit

    @property
    def page_link(self) -> str:
        if self.full_title:
            return f"[[{self.full_title}]]"
        return ""

    @property
    def last_update(self) -> str:
        if self.full_title:
            return f"{{{{#time:Y-m-d|{{{{REVISIONTIMESTAMP:{self.full_title}}}}}}}}}"
        return ""

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_subpage(
        cls,
        sub: str,
        *,
        base_page: str,
        username: str = "",
    ) -> ApplicationRow:
        """Create a minimal row from a subpage name (before enrichment)."""
        sub = sub.replace("_", " ")
        full_title = f"{base_page}/{sub}"
        user_info = UserInfo(username=username)
        return cls(
            user_info=user_info,
            full_title=full_title,
            sub=sub,
        )

    def apply_user_info(self, user_info: UserInfo) -> ApplicationRow:
        """
        Fill user-related columns from a ``UserInfo`` snapshot.
        """
        self.user_info = user_info
        return self

    def apply_country(self, wikitext: str) -> ApplicationRow:
        """Extract and set the country field from application wikitext."""
        self.country = extract_country(wikitext)
        return self

    # ------------------------------------------------------------------
    # Table / export helpers
    # ------------------------------------------------------------------

    def to_table_dict(self, unknown: str = "unknown") -> dict[str, str]:
        """
        Dict of header-key → cell value expected by ``WikiTableDataUpdater``
        and ``ApplicationTable.build_wikitable``.
        """
        data = {
            "page_link": self.page_link,
            "last_update": self.last_update,
            "country": self.country,
            **self.user_info.to_table_dict(unknown=unknown),
        }
        return data

    def to_json(self) -> dict[str, Any]:
        """Full field dump (useful for debugging / JSON export)."""
        return asdict(self)

    def build_row(self, add_last_edit: bool = False) -> list[str]:
        lines = ["|-"]
        lines.append(f"| {self.page_link}")
        lines.append(f"| {self.last_update}")
        lines.append(f"| {self.user_info.user_link}")
        lines.append(f"| {self.country}")
        lines.append(f"| {self.user_info.global_editcount_str}")

        lines.append(f"| {self.user_info.global_without_wikidata_str}")
        lines.append(f"| {self.user_info.wikidata_editcount_str}")

        lines.append(f"| {self.user_info.recent_editcount_str}")
        lines.append(f"| {self.user_info.age}")
        lines.append(f"| {self.user_info.home_wiki}")

        if add_last_edit:
            lines.append(f"| {self.user_info.last_edit}")

        lines.append("| ")
        return lines


__all__ = [
    "extract_country",
    "ApplicationRow",
]
