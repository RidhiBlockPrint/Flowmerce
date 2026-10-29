"""Consistent application logging setup."""

from __future__ import annotations

import logging

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def configure_logging(level: str = "INFO") -> None:
    """Configure the root logger once with a consistent format.

    Never log credentials, tokens, passwords or customer personal data through this logger.

    Args:
        level: A standard level name such as ``"INFO"``.
    """
    logging.basicConfig(level=getattr(logging, level.upper()), format=LOG_FORMAT, force=True)
