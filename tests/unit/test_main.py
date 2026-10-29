"""Unit tests for flowmerce.main."""

import pytest

from flowmerce import __version__
from flowmerce.main import main


def test_version_command(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["version"]) == 0
    assert capsys.readouterr().out.strip() == __version__


def test_health_ok(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("FLOWMERCE_ENV", "test")
    assert main(["health"]) == 0
    assert "OK (env=test)" in capsys.readouterr().out


def test_health_reports_bad_config(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("FLOWMERCE_ENV", "bogus")
    assert main(["health"]) == 2
    assert "configuration error" in capsys.readouterr().out
