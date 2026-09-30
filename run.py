#!/usr/bin/env python3
"""

python run.py
python -m run

"""

import logging
from pathlib import Path

from dotenv import load_dotenv

from src.logging_setup import setup_logging
from src.v3 import main

from .src.config import BASE_PAGE, DEFAULT_SECTION_NAMES

setup_logging(level=logging.DEBUG)

try:
    load_dotenv()
except Exception:
    pass

logger = logging.getLogger(__name__)


OUTPUT_DIR = Path(__file__).parent / "data"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def run() -> None:
    full_text_table = main(
        page_title=BASE_PAGE,
        unknown_placeholder="unknown",
        load_recent_editcounts=True,
        section_names=DEFAULT_SECTION_NAMES,
    )

    if full_text_table:
        file = OUTPUT_DIR / "table.wiki"

        file.write_text(full_text_table, encoding="utf-8")

        logger.info(f"Saved to {file}")


if __name__ == "__main__":
    run()
