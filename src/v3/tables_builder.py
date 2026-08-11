""" """

import logging

logger = logging.getLogger(__name__)


def build_wikitable(rows) -> str:
    """rows: list of rows data."""
    lines = [
        '{| class="wikitable sortable"',
        "! Page",
        "! Last edited to application",
        "! User ",
        "! Country",
        "! Global edits",
        "! Edits in last 3 months",
        "! Age of account",
        "! Home Wiki",
        "! Last edit",
        "! Approved",
    ]
    for _, row in rows.items():
        lines.append("|-")
        lines.append(f"| {row['page_link']}")
        lines.append(f"| {row['last_update']}")
        lines.append(f"| {row['user_link']}")
        lines.append(f"| {row.get('country', '')}")
        lines.append(f"| {row['editcount_str']}")
        lines.append(f"| {row['recent_editcount_str']}")
        lines.append(f"| {row['age']}")
        lines.append(f"| {row['home_wiki']}")

        if "last_edit" in row:
            lines.append(f"| {row['last_edit']}")

        lines.append("| ")

    lines.append("|}")

    return "\n".join(lines)


__all__ = [
    "build_wikitable",
]
