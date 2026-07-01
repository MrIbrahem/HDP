""" """

import logging
import re
from typing import Any

import wikitextparser as wtp
from wikitextparser._cell import Cell

logger = logging.getLogger(__name__)


def _build_header_index(all_rows: list[list[Cell]]) -> dict[str, int]:
    """
    Build a mapping of header text -> column index.
    """
    header_index: dict[str, int] = {}
    for row in all_rows:
        if not row or row[0] is None or not row[0].is_header:
            continue
        for idx, cell in enumerate(row):
            if cell is None:
                continue
            header_index[cell.value.strip()] = idx
        break
    return header_index


def update_table(
    table: wtp.Table,
    rows: dict[str, Any],
    table_headers_to_row_key: dict[str, str],
    replace_values: bool = False,
) -> None:
    """
    rows keys:
        (page_link, last_update, user_link, editcount_str, recent_editcount_str, age, home_wiki)
    """
    all_rows = table.cells()
    if not all_rows:
        return

    # 1. Map header text to its column index
    header_index = _build_header_index(all_rows)

    for row in all_rows:
        if not row or row[0] is None or row[0].is_header:
            continue

        # Cell('\n| [[Hardware donation program/Ibjaja055]] ')
        first_cell: Cell = row[0]
        first_cell_value: str = first_cell.value
        match_links = re.search(r"\[\[(.*?)\]\]", first_cell_value)

        if not match_links:
            continue

        # Clean the link name to match the dictionary keys
        match_link = match_links.group(1).split("|")[0].strip().replace("_", " ")

        logger.debug(f"match_link: {match_link}")

        if match_link not in rows:
            continue

        # 2. Get the row data from the dictionary
        row_data = rows[match_link]

        # 3. Update cells based on their column index
        for header, row_key in table_headers_to_row_key.items():
            col_idx = header_index.get(header)
            if col_idx is None or col_idx >= len(row) or row[col_idx] is None:
                continue

            if row_key not in row_data:
                continue

            if not row[col_idx].value.strip() or replace_values:
                row[col_idx].value = f" {row_data[row_key]}"


def update_wikitable_data(
    rows: dict[str, Any],
    wikitext: str,
    table_headers_to_row_key: dict[str, str],
    replace_values: bool = False,
) -> str:
    """rows: list of rows data."""
    parsed = wtp.parse(wikitext)
    tables = parsed.get_tables(recursive=False)

    for table in tables:
        update_table(
            table,
            rows,
            table_headers_to_row_key,
            replace_values=replace_values,
        )

    # Return the updated string representation of the parsed wikitext
    return parsed.string


__all__ = [
    "update_wikitable_data",
]
