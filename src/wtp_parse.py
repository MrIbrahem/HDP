""" """

import logging
from typing import Any

import wikitextparser as wtp
from wikitextparser._cell import Cell

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


def update_table(
    table: wtp.Table,
    rows: dict[str, Any],
    base_page: str,
) -> None:
    """
    rows keys:
        (page_link, last_update, user_link, editcount_str, recent_editcount_str, age, home_wiki)
    """
    table_links: list[str] = extract_subpage_links(base_page, table)
    table_rows = {x: v for x, v in rows.items() if x in table_links}
    logger.info(f"found {len(table_links)} links in table, {len(table_rows)} has data in rows.")

    table_headers_to_row_key = {
        "Page": "page_link",
        "Last edited to application": "last_update",
        "User": "user_link",
        "Global edits": "editcount_str",
        "Edits in last 3 months": "recent_editcount_str",
        "Age of account": "age",
        "Home Wiki": "home_wiki",
    }
    # for each row match the page_link to the row key then update the row

    for row in table.cells():
        # Cell('\n| [[Hardware donation program/Ibjaja055]] ')
        _first_cell: Cell = row[0].value
        match_links = extract_subpage_links(base_page, row[0])

        if not match_links:
            continue

        match_link = f"{base_page}/{match_links[0]}"
        logger.debug(f"match_link: {match_link}")

        if match_link in table_rows:
            row_data = table_rows[match_link]
            for header, row_key in table_headers_to_row_key.items():
                cell = row[header]
                cell.value = row_data[row_key]


def update_wikitable(
    rows: dict[str, Any],
    wikitext: str,
    base_page: str,
) -> str:
    """rows: list of rows data."""
    parsed = wtp.parse(wikitext)
    tables = parsed.get_tables(recursive=False)
    for table in tables:
        table_str = table.string
        if f"[[{base_page}/" in table_str:
            update_table(table, rows, base_page)

    return parsed.string


__all__ = [
    "get_section_by_heading",
    "extract_subpage_links",
    "update_wikitable",
]
