#!/usr/bin/env python3
"""

python -m update
python -m update test

update `User:Mr. Ibrahem/hdp` page
"""

import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from ..logging_setup import setup_logging

from ..config import BASE_PAGE, DEFAULT_SECTION_NAMES
from ..services.hdp_service import HdpService

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

OUTPUT_DIR = Path(__file__).parent / "data"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def run() -> None:
    service = HdpService.from_settings()

    if not service:
        logger.error("Failed to connect to Meta Wiki")
        return ""

    full_text_table = service.update(
        page_title=page_title,
        section_names=DEFAULT_SECTION_NAMES,
        load_recent_editcounts=False,
        load_last_edits=False,
        unknown="",
    )

    if full_text_table:
        file = OUTPUT_DIR / output_file_name

        file.write_text(full_text_table, encoding="utf-8")

        logger.info(f"Saved to {file}")


if __name__ == "__main__":
    run()
