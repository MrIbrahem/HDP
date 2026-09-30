"""
Command-line entry point for HDP tools.

Usage::

    python -m hdp generate [--output PATH] [--no-recent] [--last-edits]
    python -m hdp update   [--page TITLE] [--output PATH] [--no-recent] [--test]
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

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

        service = HdpService.from_settings(self.settings)
        if service is None:
            logger.error("Could not connect to Meta Wiki — aborting")
            return 1

        if args.command == "generate":
            return self._cmd_generate(service, args)
        if args.command == "update":
            return self._cmd_update(service, args)

        parser.print_help()
        return 2

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def _cmd_generate(self, service: HdpService, args: argparse.Namespace) -> int:
        section_names = args.sections or list(DEFAULT_SECTION_NAMES)
        text = service.generate(
            page_title=args.page or self.settings.base_page,
            section_names=section_names,
            load_recent_editcounts=not args.no_recent,
            load_last_edits=args.last_edits,
            unknown=args.unknown,
        )
        if not text:
            logger.error("generate produced empty output")
            return 1

        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        logger.info("Saved to %s", out)
        return 0

    def _cmd_update(self, service: HdpService, args: argparse.Namespace) -> int:
        page_title = args.page
        if args.test:
            page_title = "User:Mr. Ibrahem/test"

        section_names = args.sections or list(DEFAULT_SECTION_NAMES)
        text = service.update(
            page_title=page_title,
            section_names=section_names,
            load_recent_editcounts=not args.no_recent,
            load_last_edits=args.last_edits,
            unknown=args.unknown,
        )
        if not text:
            logger.error("update produced empty output")
            return 1

        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        logger.info("Saved to %s", out)
        return 0

    # ------------------------------------------------------------------
    # Argument parser
    # ------------------------------------------------------------------

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
            "--sections",
            nargs="+",
            default=None,
            help="Section headings or Category: names to include",
        )
        gen.add_argument(
            "--output",
            default="data/table.wiki",
            help="Output file path (default: data/table.wiki)",
        )
        gen.add_argument(
            "--no-recent",
            action="store_true",
            help="Skip XTools network calls; use offline cache only",
        )
        gen.add_argument(
            "--last-edits",
            action="store_true",
            help="Include last-edit-date column",
        )
        gen.add_argument(
            "--unknown",
            default="unknown",
            help="Placeholder for missing values (default: unknown)",
        )

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
            "--sections",
            nargs="+",
            default=None,
            help="Section headings or Category: names to include",
        )
        upd.add_argument(
            "--output",
            default="data/Mr. Ibrahem_hdp.wiki",
            help="Output file path",
        )
        upd.add_argument(
            "--no-recent",
            action="store_true",
            help="Skip XTools network calls; use offline cache only",
        )
        upd.add_argument(
            "--last-edits",
            action="store_true",
            help="Include last-edit-date column",
        )
        upd.add_argument(
            "--unknown",
            default="",
            help="Placeholder for missing values (default: empty string)",
        )

        return parser


def main(argv: list[str] | None = None) -> int:
    return Cli().run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
