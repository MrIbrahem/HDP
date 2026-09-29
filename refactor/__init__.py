"""
Hardware Donation Program (HDP) tools.

Package layout::

    hdp/
    ├── config.py          # Settings, Credentials
    ├── models.py          # UserInfo, ApplicationRow
    ├── cache.py           # HomeWikiCache, RecentEditCache
    ├── services.py        # HdpService
    ├── logging_setup.py
    ├── cli.py / __main__.py
    ├── wiki/              # WikiClient, CategoryService, UserResolver
    ├── xtools/            # XToolsClient
    └── parsing/           # LinkExtractor, table managers
"""

from .config import Credentials, Settings
from .models import ApplicationRow, UserInfo
from .services import HdpService

__all__ = [
    "Settings",
    "Credentials",
    "UserInfo",
    "ApplicationRow",
    "HdpService",
]
