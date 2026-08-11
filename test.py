#!/usr/bin/env python3
"""

python -m test
"""

import logging

from src import setup_logging
from src.api.xtools_cached import get_recent_editcounts_cached

setup_logging(level=logging.DEBUG)

recent_editcounts = get_recent_editcounts_cached(["Aelita14"], set_zero=True)

print(recent_editcounts)
