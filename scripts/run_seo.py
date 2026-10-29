"""Compatibility entry point. Flowmerce now runs as two local services (Python API + Next.js frontend) started
together by scripts/run_flowmerce.py; this file just forwards to it so the old command keeps working.

    python scripts/run_seo.py [--dev] [--no-browser]
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

if __name__ == "__main__":
    args = sys.argv[1:]
    unsupported = [a for a in args if a.split("=")[0] in ("--port", "--host", "--reload")]
    if unsupported:
        sys.exit("The ports and addresses are fixed (API 127.0.0.1:8787, frontend 127.0.0.1:3000); "
                 f"{', '.join(unsupported)} is no longer supported. Use --dev for frontend development mode.")
    runpy.run_path(str(Path(__file__).with_name("run_flowmerce.py")), run_name="__main__")
