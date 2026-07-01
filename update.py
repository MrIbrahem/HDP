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

if __name__ == "__main__":
    update(
        "User:Mr. Ibrahem/hdp",
        "Mr. Ibrahem_hdp.wiki",
    )
