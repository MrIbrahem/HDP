#!/usr/bin/env python3
"""

python HDP/dj.py

"""

import logging

from dotenv import load_dotenv

from v3 import main

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
    main()
