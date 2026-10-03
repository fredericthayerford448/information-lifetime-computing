import pytest

from ilc.costs import PROFILES
from ilc.planner import make_plan
from ilc.simulator import simulate
from helpers import REVERSIBLE, default_cfg, example, graph

EXAMPLES = ["basic", "reversible", "recomputation", "checkpoint", "recovery", "boundary"]


@pytest.mark.parametrize("name", EXAMPLES)
@pytest.mark.parametrize("profile", list(PROFILES))
def test_simulator_agrees_with_planner_cost_model(name, profile):
    """Two independent implementations of the cost model (planner: analytic schedules;
    simulator: walks the plan's actions) must agree exactly."""
    g, cfg = graph(example(name)), PROFILES[profile]
    for planner in ("exhaustive", "greedy", "conventional"):
        p = make_plan(g, cfg, planner=planner)
        s = simulate(g, p.execution, cfg)
        assert s.cost.close_to(p.cost), (name, profile, planner, s.cost, p.cost)
        assert s.objective == pytest.approx(p.objective)


def test_simulator_reports_counts_and_peaks():
    g = graph(REVERSIBLE)
    p = make_plan(g, default_cfg())
    s = simulate(g, p.execution, default_cfg())
    assert s.steps == len(p.execution.actions) == 6
    assert s.counts["uncomputes"] == 1 and s.counts["erasures"] == 2 and s.counts["recomputations"] == 0
    assert s.peak_storage == 4 and s.peak_temporary == 1  # a, b, tmp, result in primary at slot 2; tmp is the only temporary derived state
    assert len(s.occupancy) == g.end_slot(default_cfg().horizon) + 1


def test_recompute_and_checkpoint_counts():
    g = graph(example("recomputation"))
    s = simulate(g, make_plan(g, PROFILES["storage-scarce"]).execution, PROFILES["storage-scarce"])
    assert s.counts["recomputations"] == 1
    g2 = graph(example("checkpoint"))
    s2 = simulate(g2, make_plan(g2, PROFILES["fragile"]).execution, PROFILES["fragile"])
    assert s2.counts["checkpoints"] == 1 and s2.counts["restores"] == 1
