#!/usr/bin/env bash
# Fresh-environment check: install, run the test suite, run every example end to end.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
. .venv/bin/activate
pip install -q -e ".[dev]"
python -m pytest
for f in examples/*.lang; do
  echo "== $f"
  ilc plan "$f" | tail -1
done
python experiments/ablation_matrix.py | tail -3
echo "ALL CHECKS PASSED"
