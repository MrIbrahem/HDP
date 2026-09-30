""" """

import logging
from typing import Any

from ..services.hdp_service import HdpService

from ..cache.home_wiki_cache import get_many
from ..cache.xtools_cached import get_recent_editcounts_cached, get_recent_editcounts_offline
from ..config import BASE_PAGE
from ..models.application_row import calculate_age, extract_country
from ..wiki.client import WikiClient
from ..xtools import get_last_edit_timestamps

logger = logging.getLogger(__name__)


def solve_users_redirects(api: WikiClient, data: list[dict[str, str]]) -> list[dict[str, str]]:
    users = []
    for x in data:
        if not x["username"]:
            continue
        user_str = f"User:{x['username']}"
        users.append(user_str)

    users_redirects_api = api.solve_pages_redirects(users)

    new_data = []
    for x in data[:]:
        username = x["username"]
        user_str = f"User:{username}"
        if users_redirects_api.get(user_str):
            x["username"] = users_redirects_api[user_str].removeprefix("User:")

            if user_str == "User:Johnjoy12":
                logger.info(f"Johnjoy12 is a redirect to {x['username']}")
                logger.info(x)

        new_data.append(x)

    return new_data


def load_rows(
    api: WikiClient,
    subpages: set[str],
    unknown_placeholder: str = "unknown",
    load_recent_editcounts: bool = True,
    load_last_edits: bool = False,
    base_page: str = BASE_PAGE,
) -> dict[str, Any]:
    service = HdpService(
        wiki=api,
    )
    return service.load_rows(
        subpages=subpages,
        load_recent_editcounts=load_recent_editcounts,
        load_last_edits=load_last_edits,
        unknown=unknown_placeholder,
    )
__all__ = [
    "load_rows",
]
