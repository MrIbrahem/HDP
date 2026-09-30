"""
Domain data models for the Hardware Donation Program tools.
"""

from __future__ import annotations

from .application_row import ApplicationRow, extract_country
from .user_info import UserInfo, calculate_age

__all__ = [
    "UserInfo",
    "ApplicationRow",
    "calculate_age",
    "extract_country",
]
