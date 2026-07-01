import logging
import sys

import colorlog

# User-Agent header (required by Wikimedia)
USER_AGENT = "HDP-Donation-Tracking/1.0 (https://github.com/MrIbrahem/HDP; contact via GitHub)"


def setup_logging(
    level: str | int = "WARNING",
    name: str = "src",
) -> None:
    """
    Configure logging for the entire project namespace only.
    """
    project_logger = logging.getLogger(name)

    # Resolve level, fallback to WARNING for invalid strings
    if isinstance(level, str):
        numeric_level = getattr(logging, level.upper(), None)
        if numeric_level is None:
            numeric_level = logging.WARNING
    else:
        numeric_level = level

    project_logger.setLevel(numeric_level)
    project_logger.propagate = False

    # Prevent duplicate handlers
    if any(isinstance(h, logging.StreamHandler) for h in project_logger.handlers):
        project_logger.debug("Logging already configured for '%s'", name)
        return

    console_formatter = colorlog.ColoredFormatter(
        fmt="%(asctime)s - %(name)s - %(log_color)s%(levelname)-s %(reset)s- [%(lineno)d] - %(message)s",
        datefmt="%H:%M:%S",
    )
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(numeric_level)
    project_logger.addHandler(console_handler)

    project_logger.debug("Setting up logging for '%s' with level '%s'", name, level)
