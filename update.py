#!/usr/bin/env python3
"""

python -m update

update `User:Mr. Ibrahem/hdp` page
"""

import logging
import sys

from dotenv import load_dotenv

from src import setup_logging
from src.v3 import update

setup_logging(level=logging.DEBUG)

try:
    load_dotenv()
except Exception:
    pass

logger = logging.getLogger(__name__)

page_title = "User:Mr. Ibrahem/hdp"
output_file_name = "Mr. Ibrahem_hdp.wiki"

if "test" in sys.argv:
    page_title = "User:Mr. Ibrahem/test"
    output_file_name = "test.wiki"

if __name__ == "__main__":
    update(
        page_title=page_title,
        output_file_name=output_file_name,
        unknown_placeholder="",
        load_recent_editcounts=False,
        section_name="Category:Hardware donation program open requests",
    )
