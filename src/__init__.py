import logging
import sys

import colorlog


def setup_logging(
    level: str | int = "WARNING",
    name: str = "src",
) -> None:
    """
    Configure logging for the entire project namespace only.
    """
    project_logger = logging.getLogger(name)
    numeric_level = getattr(logging, level.upper(), logging.INFO) if isinstance(level, str) else level
    project_logger.setLevel(numeric_level)
    project_logger.propagate = False

    console_formatter = colorlog.ColoredFormatter(
        fmt="%(asctime)s - %(name)s - %(log_color)s%(levelname)-s %(reset)s- [%(lineno)d] - %(message)s",
        datefmt="%H:%M:%S",
    )
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(numeric_level)
    project_logger.addHandler(console_handler)

    project_logger.debug("Setting up logging for '%s' with level '%s'", name, level)
