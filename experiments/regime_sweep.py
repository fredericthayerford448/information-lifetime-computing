"""Regime sweep: which fate does the planner pick as one cost coefficient varies?

MODEL-ONLY.  This sweeps abstract coefficients; it shows that the planner responds
to the regime (the *mechanism* works).  It does NOT test the thesis and says nothing
about real hardware.  See experiments/README.md.

    python experiments/regime_sweep.py
    python experiments/regime_sweep.py --csv experiments/results/sweep.csv
"""
import argparse
import csv
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ilc.costs import PROFILES  # noqa: E402
from ilc.pipeline import compile_source  # noqa: E402
from ilc.planner import make_plan  # noqa: E402

SWEEPS = [
    # (example, state of interest, coefficient, values)
    ("reversible", "tmp", "e_reset", [0.1, 0.3, 1.0, 2.0, 3.0, 5.0, 8.0]),
    ("recomputation", "t", "w_primary", [0.5, 1.0, 2.0, 4.0, 6.0, 10.0]),
    ("checkpoint", "sample", "fault_prob_slot", [0.0, 0.01, 0.05, 0.1, 0.25, 0.5]),
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--csv", help="also write rows to this CSV file")
    args = ap.parse_args()
    rows = []
    base = PROFILES["abstract-default"]
    for example, state, coef, values in SWEEPS:
        path = ROOT / "examples" / f"{example}.lang"
        g = compile_source(path.read_text(), str(path))
        print(f"\n{example}.lang: fate of '{state}' as {coef} varies (other coefficients: {base.name})")
        for v in values:
            cfg = base.with_overrides(**{coef: v})
            p = make_plan(g, cfg)
            fate = p.fates[state].value
            print(f"  {coef} = {v:<6g} -> {fate:<10} (plan objective {p.objective:8.2f})")
            rows.append({"example": example, "state": state, "coefficient": coef, "value": v,
                         "fate": fate, "objective": round(p.objective, 4)})
    if args.csv:
        out = pathlib.Path(args.csv)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        print(f"\nwrote {out}")
    print("\nReminder: abstract units; this is a mechanism demo, not evidence for the thesis.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
