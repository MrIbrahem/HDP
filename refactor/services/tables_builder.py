""" """

import logging

from ..models import ApplicationRow

logger = logging.getLogger(__name__)


def build_wikitable(
    rows: dict[str, ApplicationRow],
    *,
    add_last_edit: bool = False,
) -> str:
    """
    Render a fresh MediaWiki table from rows.
    """
    lines = [
        '{| class="wikitable sortable"',
        "! Page",
        "! Last edited to application",
        "! User ",
        "! Country",
        # "! Global edits",
        "! Global edits without wikidata",
        "! Wikidata edits",
        "! Edits in last 3 months",
        "! Age of account",
        "! Home Wiki",
        # "! Last edit",
        # "! Approved",
    ]

    if add_last_edit:
        lines.append("! Last edit")

    lines.append("! Approved")

    for row in rows.values():
        row_list = row.build_row(add_last_edit)
        lines.extend(row_list)

    lines.append("|}")

    return "\n".join(lines)

__all__ = [
    "build_wikitable",
]
