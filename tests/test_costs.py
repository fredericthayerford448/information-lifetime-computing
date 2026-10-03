import json

import pytest

from ilc.costs import PROFILES, CostConfig, CostVector, action_cost, load_config, objective, storage_cost
from ilc.planner import make_plan
from helpers import REVERSIBLE, default_cfg, graph


def test_action_costs_are_transparent_formulas():
    c = default_cfg()
    assert action_cost("ERASE", 0, 8, c) == (24.0, 0.5)         # e_reset * bits
    assert action_cost("EXEC", 2.0, 8, c) == (16.0, 2.0)         # e_exec * weight * bits
    assert action_cost("UNCOMPUTE", 1.0, 1, c) == (1.0, 1.0)     # factor * forward cost
    assert action_cost("MOVE_OUT", 0, 4, c) == (2.0, 1.0)
    assert action_cost("EMIT", 0, 4, c) == (0.0, 0.0)
    assert storage_cost([("primary", 1, 3), ("bulk", 4, 5)], 8, c) == 8 * 3 * 1.0 + 8 * 2 * 0.25


def test_costs_are_deterministic():
    g = graph(REVERSIBLE)
    a, b = make_plan(g, default_cfg()), make_plan(g, default_cfg())
    assert a.cost == b.cost and a.objective == b.objective
    assert a.execution.render() == b.execution.render()


def test_weights_and_coefficients_are_configurable():
    g = graph(REVERSIBLE)
    base = make_plan(g, default_cfg())
    heavy = make_plan(g, default_cfg().with_overrides(weight_energy=10.0))
    assert heavy.objective > base.objective
    free_reset = make_plan(g, default_cfg().with_overrides(e_reset=0.0, l_reset=0.0))
    assert free_reset.fates["tmp"].value == "erase"
    cv = CostVector(1, 2, 3, 4)
    assert objective(cv, default_cfg().with_overrides(weight_energy=0, weight_storage=0, weight_latency=1, weight_recovery=0)) == 3
    assert (cv + cv).latency == 6 and cv.scale(2).recovery == 8


def test_profiles_exist_and_are_labelled_abstract():
    assert {"abstract-default", "cmos-like", "storage-scarce", "fragile", "reversible-hw"} <= set(PROFILES)
    assert all("ABSTRACT" in p.description or "Not a measurement" in p.description for p in PROFILES.values())


def test_profile_changes_the_selected_fate():
    g = graph(REVERSIBLE)
    assert make_plan(g, PROFILES["abstract-default"]).fates["tmp"].value == "uncompute"
    assert make_plan(g, PROFILES["cmos-like"]).fates["tmp"].value == "erase"


def test_load_config_profile_and_json_override(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"e_reset": 9.5, "horizon": 5}))
    c = load_config("cmos-like", str(p))
    assert c.e_reset == 9.5 and c.horizon == 5 and c.name == "cmos-like"
    with pytest.raises(ValueError):
        load_config("no-such-profile")
    p.write_text(json.dumps({"bogus": 1}))
    with pytest.raises(ValueError):
        load_config(None, str(p))
