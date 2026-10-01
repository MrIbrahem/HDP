"""
Command-line entry point for HDP tools.

Usage::

    python -m hdp generate [--output PATH] [--no-recent] [--last-edits]
    python -m hdp update   [--page TITLE] [--output PATH] [--no-recent] [--test]
"""

from __future__ import annotations

import argparse
import logging

from .config import DEFAULT_SECTION_NAMES, Settings
from .logging_setup import setup_logging
from .services import HdpService

logger = logging.getLogger(__name__)


class Cli:
    """Parse arguments, wire ``HdpService``, and run generate / update."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings.from_env()

    # ------------------------------------------------------------------
    # Public entry
    # ------------------------------------------------------------------

    def run(self, argv: list[str] | None = None) -> int:
        parser = self._build_parser()
        args = parser.parse_args(argv)

        setup_logging(level=args.log_level)

        hdp_service = HdpService.load(
            settings=self.settings,
        )

        if hdp_service is None:
            logger.error("Could not connect to Meta Wiki — aborting")
            return 1

        # set (offline/no_recent/last_edits) args in HdpService
        hdp_service.set_args(args)

        if args.command == "generate":
            return self._cmd_generate(hdp_service, args)

        if args.command == "update":
            return self._cmd_update(hdp_service, args)

        parser.print_help()
        return 2

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def _cmd_generate(self, service: HdpService, args: argparse.Namespace) -> int:
        logger.info("Starting generate script")
        section_names = args.sections or list(DEFAULT_SECTION_NAMES)

        text = service.generate(
            page_title=args.page or self.settings.base_page,
            section_names=section_names,
            unknown=args.unknown,
        )
        if not text:
            logger.error("generate produced empty output")
            return 1

        self.settings.write_to_cache_dir(args.output, text)

        return 0

    def _cmd_update(self, service: HdpService, args: argparse.Namespace) -> int:
        # default: User:Mr. Ibrahem/hdp
        page_title = args.page
        output = args.output

        section_names = args.sections or list(DEFAULT_SECTION_NAMES)
        if args.test:
            page_title = "User:Mr. Ibrahem/test"
            section_names = []

        logger.info("Starting update script, page_title: %s", page_title)
        if args.test and output == "Mr._Ibrahem_hdp.wiki":
            output = "test.wiki"

        text = service.update(
            page_title=page_title,
            section_names=section_names,
            unknown=args.unknown,
        )
        if not text:
            logger.error("update produced empty output")
            return 1

        self.settings.write_to_cache_dir(output, text)
        return 0

    # ------------------------------------------------------------------
    # Argument parser
    # ------------------------------------------------------------------

    def add_shared_args(self, com: argparse.ArgumentParser) -> None:
        com.add_argument(
            "--sections",
            nargs="+",
            default=None,
            help="Section headings or Category: names to include",
        )
        com.add_argument(
            "--offline",
            action="store_true",
            default=False,
            help="Skip All network calls; use offline cache only",
        )
        com.add_argument(
            "--no-recent",
            action="store_true",
            help="Skip XTools network calls; use offline cache only",
        )
        com.add_argument(
            "--last-edits",
            action="store_true",
            help="Include last-edit-date column",
        )

    def _build_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            prog="hdp",
            description="Hardware Donation Program tracking tools",
        )
        parser.add_argument(
            "--log-level",
            default="INFO",
            choices=["DEBUG", "INFO", "WARNING", "ERROR"],
            help="Logging verbosity (default: INFO)",
        )

        sub = parser.add_subparsers(dest="command", required=True)

        # --- generate ---
        gen = sub.add_parser(
            "generate",
            help="Build section tables from categories / sections",
        )
        gen.add_argument(
            "--page",
            default=None,
            help=f"Source page title (default: {self.settings.base_page})",
        )
        gen.add_argument(
            "--output",
            default="table.wiki",
            help="Output file path (default: data/table.wiki)",
        )
        gen.add_argument(
            "--unknown",
            default="unknown",
            help="Placeholder for missing values (default: unknown)",
        )
        self.add_shared_args(gen)

        # --- update ---
        upd = sub.add_parser(
            "update",
            help="Refresh table cells inside an existing wiki page",
        )
        upd.add_argument(
            "--page",
            default="User:Mr. Ibrahem/hdp",
            help="Page whose tables will be updated",
        )
        upd.add_argument(
            "--test",
            action="store_true",
            help="Use User:Mr. Ibrahem/test instead of --page",
        )
        upd.add_argument(
            "--output",
            default="Mr._Ibrahem_hdp.wiki",
            help="Output file path",
        )
        upd.add_argument(
            "--unknown",
            default="",
            help="Placeholder for missing values (default: empty string)",
        )
        self.add_shared_args(upd)

        return parser


def main(argv: list[str] | None = None) -> int:
    return Cli().run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
