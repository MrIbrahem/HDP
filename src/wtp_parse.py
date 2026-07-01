""" """

import logging
from typing import Any

import wikitextparser as wtp

logger = logging.getLogger(__name__)


def get_section_by_heading(wikitext, heading):
    """Use wikitextparser to find a section by its heading text."""
    parsed = wtp.parse(wikitext)
    for section in parsed.get_sections(include_subsections=True):
        if section.title and section.title.strip() == heading:
            return section
    raise ValueError(f"Section '{heading}' not found")


def extract_subpage_links(
    base_page: str,
    section: Any,
) -> list[str]:
    """Use wikitextparser's wikilinks to pull out 'Base/Sub' page names."""
    prefix = base_page + "/"
    seen = []
    for link in section.wikilinks:
        title = link.title.strip()
        title = title.replace("_", " ")

        if title.startswith(prefix):
            name = title[len(prefix) :]
            if name not in seen:
                seen.append(name)
    return seen

def update_wikitable(rows, wikitext) -> str:
    """rows: list of rows data."""
    lines = [
        '{| class="wikitable sortable"',
        "! Page",
        "! Last edited to application",
        "! User ",
        "! Global edits",
        "! Edits in last 3 months",
        "! Age of account",
        "! Home Wiki",
        "! Approved",
    ]
    for full_title, row in rows.items():
        lines.append("|-")
        lines.append(f"| [[{full_title}]] ")
        lines.append(f"| {{{{#time:H:i, j F Y|{{{{REVISIONTIMESTAMP:{full_title}}}}}}}}}")
        lines.append(f"| {row['user_link']}")
        lines.append(f"| {row['editcount_str']}")
        lines.append(f"| {row['recent_editcount_str']}")
        lines.append(f"| {row['age']}")
        lines.append(f"| {row['home_wiki']}")
        lines.append("| ")

    lines.append("|}")

    return "\n".join(lines)


__all__ = [
    "get_section_by_heading",
    "extract_subpage_links",
    "update_wikitable",
]
