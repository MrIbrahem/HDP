#!/usr/bin/env python3
"""

python run.py
python -m run

"""

import logging

from dotenv import load_dotenv

from src.v3 import main

try:
    load_dotenv()
except Exception:
    pass

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)-s - [%(lineno)d] - %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger(__name__)

SECTION_HEADINGS = [
    # "Updated as of May 1st 2026",
    # "Messaged to update application",
    # "Draft requests",
    "Current donation requests",
    # "Approved requests not yet delivered",
]

if __name__ == "__main__":
    main(SECTION_HEADINGS)
