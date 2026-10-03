#!/usr/bin/env bash
# Show the main commands on the shipped examples (assumes `pip install -e .`).
set -euo pipefail
cd "$(dirname "$0")/.."
ilc check examples/reversible.lang
ilc inspect examples/recovery.lang
ilc plan examples/reversible.lang
ilc plan examples/reversible.lang --profile cmos-like | sed -n '/Selected fates/,/Execution plan/p'
ilc run examples/recovery.lang --inject-fault guard | tail -4
ilc simulate examples/checkpoint.lang --profile fragile
