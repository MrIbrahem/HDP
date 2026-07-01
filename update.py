#!/usr/bin/env python3
"""

python -m update

update `User:Mr. Ibrahem/hdp` page
"""

import logging
import sys

from dotenv import load_dotenv

from src import setup_logging
import os
from src.v3 import update

setup_logging(level=logging.DEBUG)

env_path = os.getenv("ENV_PATH", ".env")
if not load_dotenv(env_path) and env_path != ".env":
    print(f"Warning: Failed to load .env from {env_path}")

"""
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)-s - [%(lineno)d] - %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)
"""

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
        load_recent_editcounts=True,
    )
