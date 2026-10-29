"""Unit tests for flowmerce.config.settings."""

import pytest

from flowmerce.config import ConfigError, Settings, load_settings


def test_defaults_when_environment_is_empty() -> None:
    assert load_settings({}) == Settings(env="development", log_level="INFO")


def test_values_are_normalised() -> None:
    settings = load_settings({"FLOWMERCE_ENV": " Production ", "FLOWMERCE_LOG_LEVEL": "debug"})
    assert settings == Settings(env="production", log_level="DEBUG")


def test_invalid_environment_is_rejected() -> None:
    with pytest.raises(ConfigError, match="FLOWMERCE_ENV"):
        load_settings({"FLOWMERCE_ENV": "staging"})


def test_invalid_log_level_is_rejected() -> None:
    with pytest.raises(ConfigError, match="FLOWMERCE_LOG_LEVEL"):
        load_settings({"FLOWMERCE_LOG_LEVEL": "LOUD"})
