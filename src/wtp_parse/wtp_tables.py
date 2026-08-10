""" """

import logging
import re
from typing import Any

import wikitextparser as wtp
from wikitextparser._cell import Cell

from .wtp_table_manager import WikiTableColumnManager

logger = logging.getLogger(__name__)

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
    manager = WikiTableColumnManager()
    header_index = manager.get_header_index(table)

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

        # logger.debug(f"match_link: {match_link}")

        if match_link not in rows:
            continue

        # 2. Get the row data from the dictionary
        row_data = rows[match_link]

        # 3. Update cells based on their column index
        for header, row_key in table_headers_to_row_key.items():
            col_idx = header_index.get(header.strip().lower())
            if col_idx is None or col_idx >= len(row) or row[col_idx] is None:
                continue

            if row_key not in row_data:
                continue

            cell_value = row[col_idx].value
            is_empty = not cell_value or not cell_value.strip()
            if is_empty or replace_values:
                row[col_idx].value = f" {row_data[row_key]}"


def update_wikitable_data(
    rows: dict[str, Any],
    wikitext: str,
    table_headers_to_row_key: dict[str, str],
    replace_values: bool = False,
    add_missing_headers: bool = True,
) -> str:
    """rows: list of rows data."""
    manager = WikiTableColumnManager()
    parsed = wtp.parse(wikitext)
    tables = parsed.get_tables(recursive=False)

    for table in tables:
        if add_missing_headers:
            manager.ensure_columns_exists(
                table=table,
                cols_name=list(table_headers_to_row_key.keys()),
                position="after_first",
                default_value="",
            )

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
