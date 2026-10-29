"""Integration test: the installed entry point runs as a real process."""

import os
import subprocess
import sys


def test_python_dash_m_health() -> None:
    env = {**os.environ, "FLOWMERCE_ENV": "test"}
    result = subprocess.run(  # noqa: S603 - fixed argv, no user input
        [sys.executable, "-m", "flowmerce", "health"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0
    assert "OK (env=test)" in result.stdout
