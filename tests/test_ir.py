from ilc.ir import render_graph, render_lifetimes, render_regions
from helpers import RECOVERY, REVERSIBLE, example, graph


def test_graph_construction_and_dependency_tracking():
    g = graph(REVERSIBLE)
    assert [t.op.name for t in g.transforms] == ["xor", "copy"]
    assert g.states["a"].kind == "input" and g.states["tmp"].kind == "derived"
    assert g.deps("tmp") == ["a", "b"] and g.deps("a") == []
    assert [t.output for t in g.dependents("tmp")] == ["result"]
    assert [s.name for s in g.reverse_topo()][0] == "result"
    assert g.states["tmp"].consumers == ["result"]


def test_lifetime_calculation():
    g = graph(REVERSIBLE)
    tmp = g.lifetime("tmp")
    assert (tmp.birth, tmp.uses, tmp.death) == (1, [2], 2)
    assert tmp.interval == (1, 2)
    a = g.lifetime("a")
    assert (a.birth, a.uses, a.shadow, a.death) == (0, [1], [], 1)
    assert g.lifetime("result").death == g.emit_slot == 3  # output needed at emit


def test_shadow_use_extends_frontier_lifetime():
    g = graph(RECOVERY)
    assert g.lifetime("a").death == 2 and g.lifetime("a").shadow == [2]
    assert g.lifetime("a", recovery=False).death == 1  # without recovery coupling
    r = g.regions[0]
    assert r.frontier == ["a", "b"] and r.commit_slot == 2 and r.members == ["s", "r"]


def test_persistent_state_lives_to_the_end():
    g = graph(example("recomputation"))
    assert g.lifetime("a").death == g.emit_slot and g.states["a"].persistent


def test_renderers_show_the_graph():
    g = graph(REVERSIBLE)
    txt = render_graph(g)
    assert "[1] xor" in txt and "──┐" in txt and "──┘" in txt and "result" in txt and "(output)" in txt
    assert "until(result)" in render_lifetimes(g)
    assert "(no recovery regions)" == render_regions(g)
    assert "guard" in render_regions(graph(RECOVERY)) or "frontier" in render_regions(graph(RECOVERY))


def test_boundary_and_grade_attributes_live_on_transforms():
    g = graph("system S { stato x : u8 trasforma quantize(x) -> q trasforma inc(q) -> r { bnd = soft(0.2), regen = tolerant(0.1) } }")
    q, r = g.transforms
    assert q.boundary.kind == "hard" and r.boundary.kind == "soft" and r.boundary.eta == 0.2
    assert q.regen.kind == "exact" and r.regen.kind == "tolerant" and r.regen.eps == 0.1
