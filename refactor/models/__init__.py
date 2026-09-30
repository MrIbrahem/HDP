"""
Domain data models for the Hardware Donation Program tools.
"""

from __future__ import annotations

from .application_row import ApplicationRow, extract_country
from .user_info import UserInfo, calculate_age

# ---------------------------------------------------------------------------
# Header ↔ row-key mapping used when updating existing wikitables
# ---------------------------------------------------------------------------

TABLE_HEADERS_TO_ROW_KEY: dict[str, str] = {
    "Page": "page_link",
    "Last edited to application": "last_update",
    "User": "user_link",
    "Country": "country",
    # "Global edits": "editcount_str",
    "Global edits without wikidata": "global_without_wikidata_str",
    "Wikidata edits": "wikidata_editcount_str",
    "Edits in last 3 months": "recent_editcount_str",
    "Age of account": "age",
    "Home Wiki": "home_wiki",
}

__all__ = [
    "UserInfo",
    "ApplicationRow",
    "TABLE_HEADERS_TO_ROW_KEY",
    "calculate_age",
    "extract_country",
]
