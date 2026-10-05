"""
Domain data models for the Hardware Donation Program tools.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from .user_info import UserInfo

# Matches a line like: `; your username : <value>`
# (flexible with spaces around the semicolon/colon and with letter case)
USERNAME_LINE_RE = re.compile(
    r"^[ \t]*;[ \t]*your[ \t]+username[ \t]*:[ \t]*(?P<value>.*?)[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)

# Matches [[User:Name]] or [[User:Name|Label]]
# (an optional leading colon, as in [[:User:Name]], is also accepted)
USER_LINK_RE = re.compile(
    r"^\[\[[ \t]*:?[ \t]*user[ \t]*:[ \t]*(?P<name>[^\]|]+?)[ \t]*(?:\|[^\]]*)?\]\]$",
    re.IGNORECASE,
)


def extract_username(wikitext: str) -> str:
    """Return the username found in the wikitext, or '' if none is found."""
    # ;Your username\n:<!--Answer on this line-->[[User:Robertjamal12|Robertjamal12]]
    # Find the first "your username" line
    m = USERNAME_LINE_RE.search(wikitext)
    if not m:
        return ""

    value = m.group("value").strip()

    # If the value is a user link, keep only the target name (drop the label)
    link = USER_LINK_RE.match(value)
    if link:
        value = link.group("name")

    # if value dosen't contain letters, return empty string
    if not any(c.isalpha() for c in value):
        return ""
    # Wikimedia usernames use spaces; underscores in links are equivalent
    value = value.replace("_", " ").strip()
    value = value.rstrip(".").lstrip(".").strip()

    skip_names = [
        "name here",
        "yourusername",
        "your user name",
    ]
    if value in skip_names:
        return ""

    return value
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
    approved: str = ""

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

    def apply_user_info(self, user_info: UserInfo) -> None:
        """
        Fill user-related columns from a ``UserInfo`` snapshot.
        """
        self.user_info = user_info

    def apply_country(self, wikitext: str) -> None:
        """Extract and set the country field from application wikitext."""
        self.country = extract_country(wikitext)

    def match_username(self, wikitext: str) -> None:
        """
        Extract and set the username from application wikitext.
        Patterns:
        `; your username : [[User:...]]`
        `; your username : Flixtey`
        `;your username: Muddyb`
        `; your username : [[user:Vojtěch Dostál|Vojtěch Dostál]]`
        `; your username : [[User:Sumanth699]]`
        `;your username: [[User:გიო ოქრო|გიო ოქრო]]`
        """
        username = extract_username(wikitext)

        # Only update when a username was actually found
        if username:
            self.user_info.update_username(username)

    # ------------------------------------------------------------------
    # Table / export helpers
    # ------------------------------------------------------------------

    def to_table_dict(self, unknown: str = "unknown") -> dict[str, str]:
        """
        Dict of header-key → cell value expected by ``WtpTableUpdater``
        and ``ApplicationTable.build_wikitable_template``.
        """
        data = {
            "page_link": self.page_link,
            "last_update": self.last_update,
            "country": self.country,
            "approved": self.approved,
            **self.user_info.to_table_dict(unknown=unknown),
        }
        return data

    def build_row_template(self, template: str) -> str:
        map = self.to_table_dict(unknown="")
        return template.format_map(map)

    def to_json(self) -> dict[str, Any]:
        """Full field dump (useful for debugging / JSON export)."""
        return asdict(self)

    def build_row(self, add_last_edit: bool = False) -> list[str]:
        lines = ["|-"]
        lines.append(f"| {self.page_link}")
        lines.append(f"| {self.last_update}")
        lines.append(f"| {self.user_info.user_link}")
        lines.append(f"| {self.country}")
        lines.append(f"| {self.user_info.extended_rights}")

        lines.append(f"| {self.user_info.global_editcount_str}")
        lines.append(f"| {self.user_info.global_without_wikidata_str}")
        lines.append(f"| {self.user_info.wikidata_editcount_str}")

        lines.append(f"| {self.user_info.recent_editcount_str}")
        lines.append(f"| {self.user_info.recent_wikidata_editcount_str}")
        lines.append(f"| {self.user_info.age}")
        lines.append(f"| {self.user_info.home_wiki}")
        lines.append(f"| {self.approved}")

        if add_last_edit:
            lines.append(f"| {self.user_info.last_edit}")

        return lines


__all__ = [
    "extract_country",
    "ApplicationRow",
]
