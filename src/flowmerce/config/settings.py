"""Environment-based settings.

Settings are read from environment variables (optionally populated from a local ``.env`` file by
the operator's shell or process manager). This module never reads credentials from source code and
never logs raw values.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

VALID_ENVIRONMENTS = ("development", "test", "production")
VALID_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


class ConfigError(ValueError):
    """Raised when a configuration value is missing or invalid."""


@dataclass(frozen=True, slots=True)
class Settings:
    """Validated application settings."""

    env: str = "development"
    log_level: str = "INFO"


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """Build :class:`Settings` from ``environ`` (defaults to ``os.environ``).

    Args:
        environ: Mapping of environment variables. Pass a dict in tests.

    Raises:
        ConfigError: If a value is outside the allowed set.
    """
    source = os.environ if environ is None else environ
    env = source.get("FLOWMERCE_ENV", "development").strip().lower()
    level = source.get("FLOWMERCE_LOG_LEVEL", "INFO").strip().upper()
    if env not in VALID_ENVIRONMENTS:
        raise ConfigError(f"FLOWMERCE_ENV must be one of {VALID_ENVIRONMENTS}, got {env!r}")
    if level not in VALID_LOG_LEVELS:
        raise ConfigError(f"FLOWMERCE_LOG_LEVEL must be one of {VALID_LOG_LEVELS}, got {level!r}")
    return Settings(env=env, log_level=level)
