from ilc.fates import Ablation
from ilc.interpreter import acceptable, apply_op, default_inputs, reference_values, run_plan
from ilc.plan import plan_from_tuples
from ilc.planner import make_plan
from ilc.types import tolerant, EXACT, DISTRIBUTIONAL
from helpers import RECOVERY, REVERSIBLE, STOCH, default_cfg, example, graph

CFG = default_cfg()


def test_basic_execution_matches_reference_semantics():
    g = graph(example("basic"))
    p = make_plan(g, CFG)
    res = run_plan(g, p.execution, {"a": 200, "b": 100})
    assert res.ok and res.outputs == {"sum": 44} == res.reference  # 300 mod 256


def test_reference_values_follow_op_semantics():
    g = graph("system S { stato a : u8 stato b : u8 trasforma xor(a,b)->x trasforma not(x)->n trasforma parity(a)->p trasforma quantize(b)->q }")
    v = reference_values(g, {"a": 0b1011, "b": 0b10111101})
    assert v["x"] == 0b1011 ^ 0b10111101 and v["n"] == 0xFF ^ v["x"] and v["p"] == 1 and v["q"] == 0b10110000


def test_uncompute_runs_the_inverse_and_cleans_the_register():
    g = graph(REVERSIBLE)
    p = make_plan(g, CFG)
    assert p.fates["tmp"].value == "uncompute"
    res = run_plan(g, p.execution, {"a": 1, "b": 0})
    assert res.ok and res.outputs["result"] == 1
    assert any("uncompute tmp" in line for line in res.trace)


def test_uncompute_of_a_noisy_transform_leaves_residual_garbage():
    g = graph(STOCH.replace("ACCEPT", "accept = distributional"))
    plan = plan_from_tuples(g, [(1, "exec", "EXEC", "y"), (2, "exec", "EXEC", "u1"), (2, "post", "UNCOMPUTE", "y")])
    # the re-execution draws fresh noise, so for some seeds it fails to cancel the original value
    msgs = [e for sd in range(16) for e in run_plan(g, plan, seed=sd).errors if "residual garbage" in e]
    assert msgs and "inverse is not exact" in msgs[0]


def test_invalid_execution_use_after_release():
    g = graph(REVERSIBLE)
    plan = plan_from_tuples(g, [(1, "exec", "EXEC", "tmp"), (1, "post", "ERASE", "tmp"), (2, "exec", "EXEC", "result")])
    res = run_plan(g, plan)
    assert not res.ok and any("already released" in e for e in res.errors)
    assert any("never emitted" in e for e in res.errors)


def test_erasing_twice_and_restoring_without_checkpoint_are_errors():
    g = graph(REVERSIBLE)
    plan = plan_from_tuples(g, [(1, "exec", "EXEC", "tmp"), (1, "post", "ERASE", "a"), (1, "post", "ERASE", "a"),
                                (1, "post", "RESTORE", "b")])
    errs = run_plan(g, plan).errors
    assert any("erase of 'a'" in e for e in errs) and any("no durable copy" in e for e in errs)


def test_recovery_by_replay_succeeds_when_frontier_is_kept():
    g = graph(RECOVERY)
    p = make_plan(g, CFG)
    res = run_plan(g, p.execution, fault="guard")
    assert res.ok and res.recoveries == 1 and any("recovered region" in t for t in res.trace)


def test_recovery_fails_without_recovery_coupling():
    g = graph(RECOVERY)
    p = make_plan(g, CFG, Ablation(recovery_coupling=False))
    assert run_plan(g, p.execution).ok  # fault-free it is fine ...
    res = run_plan(g, p.execution, fault="guard")  # ... but the recovery obligation is uncovered
    assert not res.ok and any("recovery of region 'guard' failed" in e for e in res.errors)


def test_recovery_by_restore_reads_durable_copies():
    src = "system S { stato a : u8 trasforma inc(a) -> s emit s recupero g { region = [s] policy = restore } }"
    g = graph(src)
    p = make_plan(g, CFG)
    assert p.fates["a"].value == "checkpoint"
    res = run_plan(g, p.execution, fault="g")
    assert res.ok and res.recoveries == 1


def test_unknown_fault_region_is_reported():
    g = graph(REVERSIBLE)
    res = run_plan(g, make_plan(g, CFG).execution, fault="nope")
    assert any("no recovery region named 'nope'" in e for e in res.errors)


def test_regeneration_of_noisy_state_diverges_when_typing_is_ablated():
    g = graph(STOCH.replace("ACCEPT", ""))  # accept defaults to exact
    cfg = CFG.with_overrides(e_reset=0.3, l_reset=0.2, w_primary=6.0)
    sound = make_plan(g, cfg)
    assert sound.fates["y"].value != "recompute" and run_plan(g, sound.execution, seed=1).ok
    unsound = make_plan(g, cfg, Ablation(boundary_typing=False))
    assert unsound.fates["y"].value == "recompute"
    found = [s for s in range(12) if not run_plan(g, unsound.execution, seed=s).ok]
    assert found, "no seed exposed the divergence of the unsound recompute"
    assert any("unsound regeneration" in e or "differs" in e for e in run_plan(g, unsound.execution, seed=found[0]).errors)


def test_accepted_divergence_is_noted_not_failed():
    g = graph(STOCH.replace("ACCEPT", "accept = distributional"))
    cfg = CFG.with_overrides(e_reset=0.3, l_reset=0.2, w_primary=6.0)
    p = make_plan(g, cfg)
    assert p.fates["y"].value == "recompute"
    results = [run_plan(g, p.execution, seed=s) for s in range(12)]
    assert all(r.ok for r in results)
    assert any(r.notes for r in results)


def test_acceptable_helper_and_determinism():
    assert acceptable(5, 5, EXACT, 8) and not acceptable(5, 6, EXACT, 8)
    assert acceptable(5, 6, DISTRIBUTIONAL, 8) and acceptable(5, 6, tolerant(0.1), 8) and not acceptable(5, 90, tolerant(0.1), 8)
    g = graph(example("basic"))
    assert default_inputs(g, 1) == default_inputs(g, 1) and default_inputs(g, 1) != default_inputs(g, 2)
