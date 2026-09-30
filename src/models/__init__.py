"""
Domain data models for the Hardware Donation Program tools.
"""

from __future__ import annotations

from .application_row import ApplicationRow, extract_country
from .user_info import UserInfo

__all__ = [
    "UserInfo",
    "ApplicationRow",
    "extract_country",
]
