"""
Constants for the HDP tools.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Header ↔ row-key mapping used when updating existing wikitables
# ---------------------------------------------------------------------------

TABLE_HEADERS_TO_ROW_KEY: dict[str, str] = {
    "Page": "page_link",
    "Last edited to application": "last_update",
    "User": "user_link",
    "Country": "country",
    "Global edits": "global_editcount_str",
    "Global edits without wikidata": "global_without_wikidata_str",
    "Wikidata edits": "wikidata_editcount_str",
    "Edits in last 3 months": "recent_editcount_str",
    "Age of account": "age",
    "Home Wiki": "home_wiki",
    "Last edit": "last_edit",
}

# ---------------------------------------------------------------------------
# Constants (rarely overridden)
# ---------------------------------------------------------------------------

XTOOLS_GLOBALCONTRIBS_URL = "https://xtools.wmcloud.org/api/user/globalcontribs"

BASE_PAGE = "Hardware donation program"

RECENT_DAYS = 90

USER_AGENT = (
    "HDP-Bot/2.0 (https://meta.wikimedia.org/wiki/Hardware_donation_program; "
    "contact: meta.wikimedia.org user Mr. Ibrahem)"
)

# Section heading → MediaWiki category (used by subpage discovery)
SECTION_TO_CATEGORY: dict[str, str] = {
    "Draft requests": "Category:Hardware donation program drafts",
    "Open requests": "Category:Hardware donation program open requests",
    "Approved requests not yet delivered": "Category:Hardware donation program approved requests",
}

# Default category list used by generate / update CLI commands
DEFAULT_SECTION_NAMES: list[str] = [
    "Category:Hardware donation program open requests",
    "Category:Hardware donation program approved requests",
    "Category:Hardware donation program drafts",
]

# Static username redirects (lowercase key → canonical display name).
# Prefer loading from data/users_redirects.json when the file exists;
# this dict is the fallback / starter set.
DEFAULT_USERS_REDIRECTS: dict[str, str] = {
    # Add known renames here, e.g.:
    # "oldname": "NewName",
}

__all__ = [
    "USER_AGENT",
    "XTOOLS_GLOBALCONTRIBS_URL",
    "SECTION_TO_CATEGORY",
    "BASE_PAGE",
    "TABLE_HEADERS_TO_ROW_KEY",
    "DEFAULT_SECTION_NAMES",
    "DEFAULT_USERS_REDIRECTS",
    "RECENT_DAYS",
]
