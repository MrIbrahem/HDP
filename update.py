#!/usr/bin/env python3
"""

python -m update

update `User:Mr. Ibrahem/hdp` page
"""

import logging

from dotenv import load_dotenv

from src.v3 import update

try:
    load_dotenv("I:/TOOLFORGE_TOOLS/.env")
except Exception:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)-s - [%(lineno)d] - %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger(__name__)

page_title = "User:Mr. Ibrahem/hdp"
output_file_name = "Mr. Ibrahem_hdp.wiki"

page_title = "User:Mr. Ibrahem/test"
output_file_name = "test.wiki"

if __name__ == "__main__":
    update(
        page_title=page_title,
        output_file_name=output_file_name,
        unknown_placeholder="",
        load_recent_editcounts=False,
    )
