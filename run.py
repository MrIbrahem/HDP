#!/usr/bin/env python3
"""

python run.py
python -m run

"""

import logging

from dotenv import load_dotenv

from src import setup_logging
from src.v3 import main

setup_logging(level=logging.DEBUG)

try:
    load_dotenv()
except Exception:
    pass

logger = logging.getLogger(__name__)

SECTION_HEADINGS = [
    # "Updated as of May 1st 2026",
    # "Messaged to update application",
    # "Draft requests",
    "Current donation requests",
    # "Approved requests not yet delivered",
]

if __name__ == "__main__":
    main(
        SECTION_HEADINGS,
        output_file_name="table.wiki",
        unknown_placeholder="unknown",
        load_recent_editcounts=False,
    )
