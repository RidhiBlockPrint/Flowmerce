"""Command-line entry point: ``python -m flowmerce`` or the ``flowmerce`` command.

Commands:
    version  Print the installed version.
    health   Validate configuration and report status (exit code 0 = healthy, 2 = bad config).
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence

from flowmerce import __version__
from flowmerce.config import ConfigError, load_settings
from flowmerce.core.logging import configure_logging

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(prog="flowmerce", description="Flowmerce ERP")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("version", help="print the version")
    sub.add_parser("health", help="validate configuration and report status")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    args = build_parser().parse_args(argv)
    if args.command == "version":
        print(__version__)
        return 0
    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"configuration error: {exc}")
        return 2
    configure_logging(settings.log_level)
    logger.info("health check env=%s", settings.env)
    print(f"flowmerce {__version__} OK (env={settings.env})")
    return 0
