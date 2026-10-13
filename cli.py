#!/usr/bin/env python3
"""Convenience entry point: `python3 cli.py` runs the same session as tatamifit.py."""

import sys

from tatamifit import main

if __name__ == "__main__":
    sys.exit(main())
