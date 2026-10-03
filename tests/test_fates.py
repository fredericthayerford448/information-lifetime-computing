import pytest

from ilc.fates import Ablation, assess, build_schedule, gaps_of, anchors_of, needs_for
from ilc.types import ALL_FATES, Fate, satisfies, tolerant, EXACT, DISTRIBUTIONAL, SOURCE_BOUND
from helpers import BOUNDARY, RECOVERY, REVERSIBLE, STOCH, default_cfg, example, graph

CFG = default_cfg()


def legal(g, name, abl=Ablation(), pins=None):
    x = g.states[name]
    nd = needs_for(g, x, pins or {}, abl)
    return {f: assess(g, x, f, nd, CFG, abl) for f in ALL_FATES}


def test_every_fate_gets_a_verdict_and_a_reason():
    g = graph(REVERSIBLE)
    for name in g.states:
        res = legal(g, name)
        assert set(res) == set(ALL_FATES)
        assert all(a.reason for a in res.values())


def test_reversible_temporary_fates():
    r = legal(graph(REVERSIBLE), "tmp")
    assert r[Fate.UNCOMPUTE].legal and "H(x|deps)=0" in r[Fate.UNCOMPUTE].reason
    assert r[Fate.ERASE].legal and r[Fate.CHECKPOINT].legal
    assert not r[Fate.RETAIN].legal and "dead temporary" in r[Fate.RETAIN].reason
    assert not r[Fate.RECOMPUTE].legal and "no idle gap" in r[Fate.RECOMPUTE].reason
    assert not r[Fate.MOVE].legal


def test_input_cannot_be_uncomputed_or_recomputed():
    r = legal(graph(REVERSIBLE), "a")
    assert not r[Fate.UNCOMPUTE].legal and "no producing transform" in r[Fate.UNCOMPUTE].reason
    assert not r[Fate.RECOMPUTE].legal and "source information unavailable" in r[Fate.RECOMPUTE].reason


def test_output_may_be_retained():
    r = legal(graph(REVERSIBLE), "result")
    assert r[Fate.RETAIN].legal and r[Fate.ERASE].legal


def test_hard_boundary_blocks_uncompute_but_not_erase():
    g = graph(BOUNDARY)
    r = legal(g, "q")
    assert not r[Fate.UNCOMPUTE].legal and "HARD" in r[Fate.UNCOMPUTE].reason
    assert r[Fate.ERASE].legal


def test_soft_boundary_threshold_is_eps_clean():
    src = "system S { stato a : u8 trasforma inc(a) -> y { bnd = soft(%s) } }"
    assert not legal(graph(src % "0.2"), "y")[Fate.UNCOMPUTE].legal
    assert legal(graph(src % "0.01"), "y")[Fate.UNCOMPUTE].legal
    assert "eps_clean" in legal(graph(src % "0.2"), "y")[Fate.UNCOMPUTE].reason


def test_regeneration_grade_gates_recompute():
    acc = lambda a: STOCH.replace("ACCEPT", a)
    strict = legal(graph(acc("")), "y")[Fate.RECOMPUTE]
    assert not strict.legal and "does not satisfy acceptance" in strict.reason
    assert legal(graph(acc("accept = distributional")), "y")[Fate.RECOMPUTE].legal
    # ablation: dropping boundary typing silently allows the unsound recompute
    assert legal(graph(acc("")), "y", Ablation(boundary_typing=False))[Fate.RECOMPUTE].legal


def test_non_exact_producer_blocks_uncompute():
    r = legal(graph(STOCH.replace("ACCEPT", "")), "y")
    assert not r[Fate.UNCOMPUTE].legal and "not exact" in r[Fate.UNCOMPUTE].reason


def test_grade_ordering():
    assert satisfies(EXACT, tolerant(0.1)) and satisfies(tolerant(0.1), DISTRIBUTIONAL)
    assert not satisfies(DISTRIBUTIONAL, tolerant(0.1)) and not satisfies(tolerant(0.2), tolerant(0.1))
    assert satisfies(tolerant(0.05), tolerant(0.1)) and not satisfies(SOURCE_BOUND, DISTRIBUTIONAL)


def test_persistent_states_can_only_be_retained():
    r = legal(graph(example("recomputation")), "a")
    assert [f for f, a in r.items() if a.legal] == [Fate.RETAIN]


def test_restore_policy_forces_checkpoint_of_frontier():
    src = "system S { stato a : u8 trasforma inc(a) -> s emit s recupero g { region = [s] policy = restore } }"
    g = graph(src)
    r = legal(g, "a")
    assert [f for f, a in r.items() if a.legal] == [Fate.CHECKPOINT]
    assert "policy=restore" in r[Fate.ERASE].reason
    # ablating recovery coupling removes the obligation
    assert legal(g, "a", Ablation(recovery_coupling=False))[Fate.ERASE].legal


def test_uncompute_ablation_switch():
    assert not legal(graph(REVERSIBLE), "tmp", Ablation(allow_uncompute=False))[Fate.UNCOMPUTE].legal


def test_gap_detection():
    assert gaps_of([0, 1, 2]) == [] and gaps_of([1, 2, 5]) == [(2, 5)] and gaps_of([0, 2, 3, 6]) == [(0, 2), (3, 6)]


def test_machine_without_bulk_makes_move_illegal():
    r = legal(graph(example("recomputation")), "t")
    assert not r[Fate.MOVE].legal and "no bulk component" in r[Fate.MOVE].reason
    assert r[Fate.RECOMPUTE].legal and r[Fate.CHECKPOINT].legal


def test_schedules_describe_what_each_fate_does():
    g = graph(example("recomputation"))
    t = g.states["t"]
    nd = needs_for(g, t, {}, Ablation())
    rec = build_schedule(g, t, Fate.RECOMPUTE, nd, CFG)
    kinds = [(a.slot, a.phase, a.kind) for a in rec.acts]
    assert (2, "post", "RELEASE") in kinds and (5, "pre", "REGENERATE") in kinds and (5, "post", "RELEASE") in kinds
    assert {d for d, _ in rec.pins} == {"a", "b"} and all(n.slot == 5 for _, n in rec.pins)
    assert [w for w in rec.windows if w[0] == "primary"] == [("primary", 1, 2), ("primary", 5, 5)]
    ck = build_schedule(g, t, Fate.CHECKPOINT, nd, CFG)
    assert ck.durable_start == 1 and any(a.kind == "RESTORE" for a in ck.acts)
    unc = build_schedule(g, g.states["u"], Fate.UNCOMPUTE, needs_for(g, g.states["u"], {}, Ablation()), CFG)
    assert unc.pins[0][0] == "t" and unc.pins[0][1].kind == "pin-uncompute"


def test_pins_extend_dependencies_and_change_their_fate_context():
    g = graph(REVERSIBLE)
    from ilc.ir import Need
    pins = {"a": [Need(2, "pin-uncompute")]}
    x = g.states["a"]
    assert anchors_of(x, needs_for(g, x, pins, Ablation())) == [0, 1, 2]
