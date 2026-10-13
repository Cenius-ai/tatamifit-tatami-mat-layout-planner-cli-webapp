#!/usr/bin/env bash
# TatamiFit setup: installs the (tiny) project dependencies and exits.
# It never starts the planner and never touches system packages.
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"

echo "==> Checking the Python interpreter"
"$PYTHON" -c 'import sys; assert sys.version_info >= (3, 8), sys.version_info; print(sys.version.split()[0])'

echo "==> Upgrading pip, setuptools and wheel (safe to re-run)"
"$PYTHON" -m pip install --disable-pip-version-check --upgrade pip setuptools wheel \
  || echo "warning: could not upgrade pip/setuptools/wheel; continuing with what is installed"

echo "==> Installing project dependencies from requirements.txt"
"$PYTHON" -m pip install --disable-pip-version-check -r requirements.txt

echo "==> Installing the 'tatamifit' console command (optional, editable)"
if "$PYTHON" -m pip install --disable-pip-version-check --no-build-isolation -e .; then
  echo "    console command installed: tatamifit --help"
else
  echo "    warning: editable install skipped; the planner still runs as"
  echo "             'python3 tatamifit.py' or 'python3 cli.py'"
fi

echo "==> Self-check: importing the planner"
"$PYTHON" -c 'import tatamifit; print("tatamifit", tatamifit.VERSION, "imports cleanly")'

echo "Setup complete. Nothing was started and no state was written."
echo "  Plan a room : python3 tatamifit.py"
echo "  Run the demo: sh demo.sh"
echo "  Run the tests: python3 -m pytest"
