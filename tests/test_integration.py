"""End-to-end: source -> parser -> semantic checker -> IR -> fate analysis -> planner -> execution plan
-> verifier -> simulator -> interpreter."""
import pytest

from conftest import EXAMPLES
from ilc.costs import PROFILES
from ilc.fates import Ablation, assess, needs_for
from ilc.parser import parse
from ilc.pipeline import run_pipeline
from ilc.planner import make_plan
from ilc.semantics import check
from ilc.types import ALL_FATES, Fate

NAMES = sorted(p.stem for p in EXAMPLES.glob("*.lang"))


def test_manual_chain_through_every_stage():
    src = (EXAMPLES / "reversible.lang").read_text()
    ast = parse(src, "reversible.lang")                       # source -> AST
    res = check(ast)                                          # semantic checker -> IR
    assert res.ok
    g = res.graph
    cfg = PROFILES["abstract-default"]
    tmp = g.states["tmp"]
    verdicts = {f: assess(g, tmp, f, needs_for(g, tmp, {}, Ablation()), cfg) for f in ALL_FATES}   # fate analysis
    assert verdicts[Fate.UNCOMPUTE].legal and not verdicts[Fate.RETAIN].legal
    plan = make_plan(g, cfg)                                  # planner
    assert plan.fates["tmp"] is Fate.UNCOMPUTE
    assert [a.kind for a in plan.execution.actions][:3] == ["EXEC", "EXEC", "UNCOMPUTE"]   # execution plan


def test_all_examples_are_present():
    assert {"basic", "reversible", "recomputation", "checkpoint", "recovery", "boundary"} <= set(NAMES)


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("profile", list(PROFILES))
def test_every_example_plans_verifies_and_executes(name, profile):
    cfg = PROFILES[profile]
    src = (EXAMPLES / f"{name}.lang").read_text()
    r = run_pipeline(src, f"{name}.lang", cfg)
    assert r.verification.ok, r.verification.all_messages()
    assert r.execution.ok, r.execution.errors
    assert r.plan.optimal
    assert r.simulation.cost.close_to(r.plan.cost)
    for seed in range(3):
        assert run_pipeline(src, f"{name}.lang", cfg, seed=seed).execution.ok


@pytest.mark.parametrize("name", NAMES)
def test_every_region_survives_fault_injection(name):
    src = (EXAMPLES / f"{name}.lang").read_text()
    g = run_pipeline(src, f"{name}.lang", PROFILES["abstract-default"]).graph
    for region in g.regions:
        for profile in PROFILES:
            r = run_pipeline(src, f"{name}.lang", PROFILES[profile], fault=region.name)
            assert r.execution.ok and r.execution.recoveries == 1, (name, profile, r.execution.errors)


def test_fate_regimes_demonstrated_by_the_shipped_examples():
    def fates(name, profile):
        src = (EXAMPLES / f"{name}.lang").read_text()
        return {k: v.value for k, v in run_pipeline(src, name, PROFILES[profile]).plan.fates.items()}
    assert fates("reversible", "abstract-default")["tmp"] == "uncompute"
    assert fates("reversible", "cmos-like")["tmp"] == "erase"
    assert fates("recomputation", "storage-scarce")["t"] == "recompute"
    assert fates("checkpoint", "fragile")["sample"] == "checkpoint"
    assert fates("checkpoint", "abstract-default")["sample"] != "checkpoint"
    assert fates("boundary", "abstract-default")["q"] != "uncompute"
