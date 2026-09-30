""" """

import logging
from typing import Any

from ..config import BASE_PAGE
from ..services.hdp_service import HdpService
from ..wiki.client import WikiClient

logger = logging.getLogger(__name__)


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
