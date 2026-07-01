#!/usr/bin/env python3
"""

python run.py
python -m run

"""

import logging

from dotenv import load_dotenv

from src.v3 import main

import os

env_path = os.getenv("ENV_PATH", ".env")
if not load_dotenv(env_path) and env_path != ".env":
    print(f"Warning: Failed to load .env from {env_path}")

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
