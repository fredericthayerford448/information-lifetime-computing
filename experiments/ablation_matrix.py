"""Ablation matrix: what breaks when part of the model is switched off?

For every program and every ablation (boundary typing, recovery coupling, uncompute)
this plans with the ablated engine, then asks the INDEPENDENT verifier and the
reference interpreter (with fault injection and several noise seeds) whether the
resulting plan is still sound.  This mirrors the ablation arms of the killer
experiment (foundation section 20) in a digital-only, model-only setting.

A "caught" cell means the ablated plan was unsound and was detected.  A "-" means no
violation was observed for that program: it does NOT prove the ablation is harmless
in general.  Nothing here is a measurement of hardware.

    python experiments/ablation_matrix.py
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ilc.costs import PROFILES  # noqa: E402
from ilc.diagnostics import ILCError  # noqa: E402
from ilc.fates import Ablation  # noqa: E402
from ilc.pipeline import run_pipeline  # noqa: E402

ABLATIONS = {
    "none": Ablation(),
    "boundary-typing": Ablation(boundary_typing=False),
    "recovery-coupling": Ablation(recovery_coupling=False),
    "uncompute": Ablation(allow_uncompute=False),
}
PROGRAMS = sorted((ROOT / "examples").glob("*.lang")) + sorted((ROOT / "experiments" / "programs").glob("*.lang"))
CFG_NAMES = ["abstract-default", "storage-scarce"]
SEEDS = range(8)


def probe(path, cfg, abl):
    src = path.read_text()
    first = run_pipeline(src, path.name, cfg, ablation=abl)
    problems = list(first.verification.all_messages()) + list(first.execution.errors)
    for r in first.graph.regions:
        for seed in SEEDS:
            problems += run_pipeline(src, path.name, cfg, ablation=abl, fault=r.name, seed=seed).execution.errors
    for seed in SEEDS:
        problems += run_pipeline(src, path.name, cfg, ablation=abl, seed=seed).execution.errors
    return first, problems


def main() -> int:
    print(f"{'program':<22}{'profile':<18}" + "".join(f"{a:<20}" for a in ABLATIONS))
    unsound_baseline = 0
    for path in PROGRAMS:
        for cn in CFG_NAMES:
            cfg = PROFILES[cn]
            cells = []
            for name, abl in ABLATIONS.items():
                try:
                    plan, problems = probe(path, cfg, abl)
                    cost = f"{plan.plan.objective:.1f}"
                    cells.append(f"CAUGHT ({cost})" if problems else f"- ({cost})")
                    if name == "none" and problems:
                        unsound_baseline += 1
                except ILCError:
                    cells.append("no plan")
            print(f"{path.stem:<22}{cn:<18}" + "".join(f"{c:<20}" for c in cells))
    print("\nCAUGHT = ablated plan failed the verifier or interpreter; '-' = no violation observed;"
          " number = plan objective (abstract units).")
    if unsound_baseline:
        print("ERROR: the unablated engine produced an unsound plan - that is a bug.")
        return 1
    print("The unablated engine produced no unsound plan on any program/profile/seed probed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
