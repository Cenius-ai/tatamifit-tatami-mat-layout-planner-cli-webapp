#!/usr/bin/env sh
# TatamiFit demo -- three piped sessions, no interaction required.
set -eu
cd "$(dirname "$0")"

echo "== TatamiFit demo 1/3: a 3.70 m x 2.90 m guest room =="
printf '3.70\n2.90\n\n' | python3 tatamifit.py
echo
echo "== TatamiFit demo 2/3: a 3.64 m x 1.82 m passage =="
printf '3.64\n1.82\n\n' | python3 tatamifit.py
echo
echo "== TatamiFit demo 3/3: a 1.20 m x 0.80 m closet is refused =="
printf '1.20\n0.80\n\n' | python3 tatamifit.py || echo "(refused as expected)"
echo
echo "== TatamiFit usage =="
python3 tatamifit.py --help
