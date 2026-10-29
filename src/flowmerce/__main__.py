"""Allow ``python -m flowmerce``."""

import sys

from flowmerce.main import main

if __name__ == "__main__":
    sys.exit(main())
