"""
Project-scoped logging configuration.
"""

from __future__ import annotations

import logging
import sys

import colorlog


def setup_logging(
    level: str | int = "WARNING",
    name: str = "hdp",
) -> None:
    """
    Configure logging for the HDP package namespace only.

    Safe to call multiple times — duplicate stream handlers are skipped.
    """
    project_logger = logging.getLogger(name)
    numeric_level = (
        getattr(logging, level.upper(), logging.INFO)
        if isinstance(level, str)
        else level
    )
    project_logger.setLevel(numeric_level)
    project_logger.propagate = False

    if any(isinstance(h, logging.StreamHandler) for h in project_logger.handlers):
        project_logger.debug("Logging already configured for %r", name)
        return

    console_formatter = colorlog.ColoredFormatter(
        fmt=(
            "%(asctime)s - %(name)s - %(log_color)s%(levelname)-s %(reset)s"
            "- [%(funcName)s:%(lineno)d] - %(message)s"
        ),
        datefmt="%H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(numeric_level)
    project_logger.addHandler(console_handler)

    project_logger.debug(
        "Setting up logging for %r with level %r", name, level
    )


__all__ = ["setup_logging"]
