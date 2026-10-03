import itertools

import pytest

from ilc.costs import PROFILES, CostConfig
from ilc.diagnostics import ILCError
from ilc.fates import Ablation
from ilc.planner import evaluate, make_plan
from ilc.types import ALL_FATES, Fate
from helpers import REVERSIBLE, default_cfg, example, graph

EXAMPLES = ["basic", "reversible", "recomputation", "checkpoint", "recovery", "boundary"]


def test_candidate_enumeration_reports_all_six_fates():
    p = make_plan(graph(REVERSIBLE), default_cfg())
    for name, rep in p.reports.items():
        assert [a.fate for a in rep.assessments] == ALL_FATES
        assert all(a.reason for a in rep.assessments)
        # illegal fates have no counterfactual cost; legal ones normally do
        for a in rep.assessments:
            assert (rep.alternatives[a.fate] is None) or a.legal


def test_selected_plan_for_reversible_example():
    p = make_plan(graph(REVERSIBLE), default_cfg())
    assert p.fates["tmp"] is Fate.UNCOMPUTE and p.optimal and p.planner == "exhaustive"
    texts = [a.text for a in p.execution.actions]
    assert texts[0] == "xor(a, b) -> tmp" and texts[1] == "copy(tmp) -> result"
    assert texts[2].startswith("uncompute tmp") and "emit result" in texts[-1]
    # the chosen fate is the minimum of its legal counterfactuals
    alts = {f: o for f, o in p.reports["tmp"].alternatives.items() if o is not None}
    assert alts[Fate.UNCOMPUTE] == min(alts.values()) == pytest.approx(p.objective)


def test_pinned_destino_is_honoured():
    src = REVERSIBLE.replace("durata = until(result)", "durata = until(result)  destino = erase")
    assert make_plan(graph(src), default_cfg()).fates["tmp"] is Fate.ERASE


def test_tie_handling_is_deterministic_and_prefers_simpler_fates():
    zero = CostConfig(e_exec=0, e_reset=0, e_xfer=0, e_ckpt=0, e_restore=0, l_exec=0, l_reset=0, l_xfer=0,
                      l_ckpt=0, l_restore=0, w_primary=0, w_bulk=0, w_durable=0, fault_prob_slot=0,
                      region_fault_prob=0)
    g = graph("system S { stato a : bit trasforma copy(a) -> y emit y }")
    p1, p2 = make_plan(g, zero), make_plan(g, zero)
    assert p1.fates == p2.fates
    assert p1.fates["a"] is Fate.ERASE and p1.fates["y"] is Fate.RETAIN  # retain > erase > ... > uncompute


@pytest.mark.parametrize("name", ["reversible", "recovery", "boundary"])
@pytest.mark.parametrize("profile", ["abstract-default", "cmos-like", "fragile"])
def test_exhaustive_planner_matches_brute_force(name, profile):
    cfg = PROFILES[profile]
    g = graph(example(name))
    best = float("inf")
    order = list(g.states)
    for combo in itertools.product(ALL_FATES, repeat=len(order)):
        ev, _ = evaluate(g, dict(zip(order, combo)), cfg, Ablation())
        if ev is not None and not ev.violations:
            best = min(best, ev.objective)
    assert make_plan(g, cfg).objective == pytest.approx(best)


@pytest.mark.parametrize("name", EXAMPLES)
@pytest.mark.parametrize("profile", list(PROFILES))
def test_greedy_and_conventional_never_beat_exhaustive(name, profile):
    g, cfg = graph(example(name)), PROFILES[profile]
    ex = make_plan(g, cfg)
    for other in ("greedy", "conventional"):
        o = make_plan(g, cfg, planner=other)
        assert o.objective >= ex.objective - 1e-9
        assert not o.optimal


def test_conventional_baseline_erases_temporaries_and_retains_outputs():
    p = make_plan(graph(REVERSIBLE), default_cfg(), planner="conventional")
    assert p.fates["tmp"] is Fate.ERASE and p.fates["result"] is Fate.RETAIN


def test_regime_dependence_is_visible():
    g = graph(example("recomputation"))
    assert make_plan(g, PROFILES["storage-scarce"]).fates["t"] is Fate.RECOMPUTE
    assert make_plan(g, PROFILES["abstract-default"]).fates["t"] is not Fate.RECOMPUTE
    assert make_plan(graph(example("checkpoint")), PROFILES["fragile"]).fates["sample"] is Fate.CHECKPOINT


def test_unsatisfiable_constraint_gives_a_plan_error():
    src = REVERSIBLE.replace("emit result", "emit result vincolo energy < 1")
    with pytest.raises(ILCError) as e:
        make_plan(graph(src), default_cfg())
    assert e.value.diagnostics[0].code == "E-PLAN" and "violated" in str(e.value)


def test_capacity_constraint_steers_the_plan():
    src = """system S { componente m { role = primary capacity = 3 }
        stato a : u8 trasforma inc(a) -> b trasforma inc(b) -> c emit c }"""
    with pytest.raises(ILCError):
        make_plan(graph(src), default_cfg())   # 8-bit values cannot fit in 3 bits
    ok = src.replace("capacity = 3", "capacity = 16")
    assert make_plan(graph(ok), default_cfg()).execution.actions


def test_search_budget_falls_back_to_greedy_and_says_so():
    p = make_plan(graph(example("recovery")), default_cfg(), budget=1)
    assert p.planner == "greedy" and not p.optimal and any("budget" in n for n in p.notes)


def test_no_legal_plan_is_reported_with_reasons():
    # recompute needs an idle gap; tmp has none, so the pinned fate is only illegal in context (planner level)
    src = REVERSIBLE.replace("durata = until(result)", "durata = until(result)  destino = recompute")
    g = graph(src)  # passes the static check: legality depends on gaps
    with pytest.raises(ILCError) as e:
        make_plan(g, default_cfg())
    assert "E-PLAN" in str(e.value) and "no legal fate for 'tmp'" in str(e.value) and "no idle gap" in str(e.value)


def test_unknown_planner_name():
    with pytest.raises(ILCError):
        make_plan(graph(REVERSIBLE), default_cfg(), planner="oracle")
