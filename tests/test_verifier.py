"""Verifier tests, including the falsification-oriented negative plans: each
hand-built plan must fail for an explicit, named reason."""
import pytest

from ilc.fates import Ablation
from ilc.plan import plan_from_tuples
from ilc.planner import make_plan
from ilc.verifier import verify
from helpers import BOUNDARY, RECOVERY, REVERSIBLE, STOCH, default_cfg, example, graph

CFG = default_cfg()
EXAMPLES = ["basic", "reversible", "recomputation", "checkpoint", "recovery", "boundary"]


@pytest.mark.parametrize("name", EXAMPLES)
def test_planner_output_always_verifies(name):
    g = graph(example(name))
    for profile in ("abstract-default", "cmos-like", "storage-scarce", "fragile", "reversible-hw"):
        from ilc.costs import PROFILES
        p = make_plan(g, PROFILES[profile])
        rep = verify(g, p.execution, PROFILES[profile])
        assert rep.ok, (name, profile, rep.all_messages())


GOOD_REV = [(1, "exec", "EXEC", "tmp"), (2, "exec", "EXEC", "result"), (2, "post", "UNCOMPUTE", "tmp"),
            (2, "post", "ERASE", "b"), (2, "post", "ERASE", "a"), (3, "exec", "EMIT", "result")]


def v(g, rows, cfg=CFG):
    return verify(g, plan_from_tuples(g, rows), cfg)


def test_hand_written_good_plan_passes():
    assert v(graph(REVERSIBLE), GOOD_REV).ok


def test_premature_erase_is_caught():
    rows = [(1, "exec", "EXEC", "tmp"), (1, "post", "ERASE", "tmp"), (2, "exec", "EXEC", "result"),
            (2, "post", "ERASE", "b"), (2, "post", "ERASE", "a"), (3, "exec", "EMIT", "result")]
    rep = v(graph(REVERSIBLE), rows)
    assert not rep.ok and any("'tmp'" in m and "resident" in m for m in rep.violations["I2"])


def test_lost_dependency_for_uncompute_is_caught():
    rows = [(1, "exec", "EXEC", "tmp"), (1, "post", "ERASE", "b"), (2, "exec", "EXEC", "result"),
            (2, "post", "UNCOMPUTE", "tmp"), (2, "post", "ERASE", "a"), (3, "exec", "EMIT", "result")]
    rep = v(graph(REVERSIBLE), rows)
    assert any("needs 'b' resident" in m for m in rep.violations["I4"])


def test_illegal_uncompute_across_hard_boundary_is_caught():
    g = graph(BOUNDARY)
    rows = [(1, "exec", "EXEC", "q"), (2, "exec", "EXEC", "p"), (2, "post", "UNCOMPUTE", "q"),
            (2, "post", "ERASE", "x"), (3, "exec", "EMIT", "p")]
    rep = v(g, rows)
    assert any("HARD boundary" in m for m in rep.violations["I5"])


def test_uncompute_of_input_is_caught_as_missing_inverse():
    g = graph(REVERSIBLE)
    rows = GOOD_REV[:2] + [(2, "post", "UNCOMPUTE", "a")] + GOOD_REV[2:]
    assert any("no producing transform" in m for m in v(g, rows).violations["I4"])


def test_recovery_conflict_frontier_released_before_commit():
    g = graph(RECOVERY)
    rows = [(1, "exec", "EXEC", "s"), (1, "post", "ERASE", "b"), (1, "post", "ERASE", "a"), (2, "exec", "EXEC", "r"),
            (2, "post", "UNCOMPUTE", "s"), (3, "exec", "EMIT", "r")]
    rep = v(g, rows)
    assert any("recovery of region 'guard'" in m for m in rep.violations["I3"])


def test_restore_policy_without_durable_copy_is_caught():
    g = graph("system S { stato a : u8 trasforma inc(a) -> s emit s recupero g { region = [s] policy = restore } }")
    rows = [(1, "exec", "EXEC", "s"), (1, "post", "ERASE", "a"), (2, "exec", "EMIT", "s")]
    assert any("no durable copy of frontier 'a'" in m for m in v(g, rows).violations["I3"])


def test_inconsistent_lifetime_state_needed_by_durata_but_released():
    g = graph("system S { stato a : bit stato t : bit { durata = steps(2) } trasforma copy(a) -> t trasforma copy(a) -> u emit u }")
    rows = [(1, "exec", "EXEC", "t"), (1, "post", "ERASE", "t"), (2, "exec", "EXEC", "u"), (2, "post", "ERASE", "a"),
            (3, "exec", "EMIT", "u")]
    assert any("durata" in m for m in v(g, rows).violations["I2"])


def test_persistent_state_destruction_and_leaks_are_caught():
    from ilc.costs import PROFILES
    CFG = PROFILES["cmos-like"]  # cheap reset: the plan erases its temporaries, so we can remove one
    g = graph(example("recomputation"))
    p = make_plan(g, CFG)
    rows = [(a.slot, a.phase, a.kind, a.state) for a in p.execution.actions]
    assert verify(g, p.execution, CFG).ok and ("ERASE" in [r[2] for r in rows])
    bad = rows + [(g.emit_slot, "post", "ERASE", "a")]
    assert any("persistent" in m for m in v(g, bad, CFG).violations["I6"])
    victim = next(r[3] for r in rows if r[2] == "ERASE" and not g.states[r[3]].is_output)
    leaked = [r for r in rows if not (r[2] == "ERASE" and r[3] == victim)]
    assert any("clean exit" in m for m in v(g, leaked, CFG).violations["I6"])


def test_unsound_recompute_grade_is_caught():
    g = graph(STOCH.replace("ACCEPT", ""))
    cfg = CFG.with_overrides(e_reset=0.3, l_reset=0.2, w_primary=6.0)
    bad = make_plan(g, cfg, Ablation(boundary_typing=False))
    assert any("does not satisfy acceptance" in m for m in verify(g, bad.execution, cfg).violations["I5"])


def test_incomplete_plan_and_constraint_violations():
    g = graph(REVERSIBLE.replace("emit result", "emit result vincolo peak_storage < 1"))
    rep = v(g, GOOD_REV[:3])
    assert rep.violations["P1"]
    assert any("peak_storage" in m for m in v(g, GOOD_REV).violations["C"])


def test_report_formatting_lists_every_check():
    rep = v(graph(REVERSIBLE), GOOD_REV[:1])
    text = rep.format()
    for cid in ("P1", "I2", "I3", "I4", "I5", "I6", "I7", "C"):
        assert cid in text
    assert "FAIL" in text and rep.all_messages()
