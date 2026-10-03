"""Fate planner: choose a legal fate for every state under a configurable objective.

Search is over fate assignments in reverse topological order (dependents
first), so dependency pinning (uncompute/recompute extend the lifetimes of
their inputs) is known when each dependency is decided.  Costs are additive
over states, which makes branch-and-bound exact: for graphs within the search
budget the exhaustive planner is optimal *under the abstract model*.  The
greedy planner is myopic and carries no optimality claim.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .costs import CostConfig, CostVector, base_exec_cost, objective
from .diagnostics import Diagnostic, ILCError
from .fates import (Ablation, Assessment, Schedule, assess, build_schedule, candidate_fates, needs_for,
                    state_cost)
from .ir import InfoGraph, Need
from .plan import ExecutionPlan, assemble
from .types import ALL_FATES, FATE_PREFERENCE, Fate

EPS = 1e-9


class SearchBudgetExceeded(Exception):
    pass


@dataclass
class Evaluation:
    fates: Dict[str, Fate]
    schedules: Dict[str, Schedule]
    needs: Dict[str, List[Need]]
    cost: CostVector
    objective: float
    peak_primary: int
    violations: List[str]


@dataclass
class StateReport:
    name: str
    assessments: List[Assessment]
    alternatives: Dict[Fate, Optional[float]]  # counterfactual whole-plan objective (None = infeasible)


@dataclass
class Plan:
    graph: InfoGraph
    cfg: CostConfig
    ablation: Ablation
    fates: Dict[str, Fate]
    schedules: Dict[str, Schedule]
    needs: Dict[str, List[Need]]
    execution: ExecutionPlan
    cost: CostVector
    objective: float
    planner: str
    optimal: bool
    nodes: int
    reports: Dict[str, StateReport]
    notes: List[str] = field(default_factory=list)


def plan_error(msg: str) -> ILCError:
    return ILCError(Diagnostic("E-PLAN", msg))


# -- evaluation ---------------------------------------------------------------
def peak_primary(g: InfoGraph, scheds: Dict[str, Schedule], cfg: CostConfig) -> int:
    end = g.end_slot(cfg.horizon)
    prof = [0] * (end + 1)
    for st in scheds.values():
        bits = g.states[st.state].bits
        for tier, a, b in st.windows:
            if tier == "primary":
                for t in range(a, b + 1):
                    prof[t] += bits
    return max(prof) if prof else 0


def violations(g: InfoGraph, total: CostVector, peak: int) -> List[str]:
    vals = dict(total.as_dict(), peak_storage=float(peak))
    out = [f"constraint '{c}' violated (actual {vals[c.dim]:.4g})" for c in g.constraints if not c.holds(vals[c.dim])]
    cap = g.machine.components.get("primary").capacity if g.machine.has("primary") else None
    if cap is not None and peak > cap:
        out.append(f"primary capacity {cap:g} exceeded (peak {peak})")
    return out


def evaluate(g: InfoGraph, fates: Dict[str, Fate], cfg: CostConfig, abl: Ablation) -> Tuple[Optional[Evaluation], str]:
    """Cost a complete fate assignment. Returns (None, reason) if a fate is illegal."""
    pins: Dict[str, List[Need]] = {}
    scheds: Dict[str, Schedule] = {}
    needs: Dict[str, List[Need]] = {}
    total = base_exec_cost(g, cfg)
    for x in g.reverse_topo():
        nd = needs_for(g, x, pins, abl)
        needs[x.name] = nd
        a = assess(g, x, fates[x.name], nd, cfg, abl)
        if not a.legal:
            return None, f"{x.name}: {fates[x.name].value} is illegal: {a.reason}"
        sch = build_schedule(g, x, fates[x.name], nd, cfg)
        scheds[x.name] = sch
        for dep, need in sch.pins:
            pins.setdefault(dep, []).append(need)
        total = total + state_cost(g, x, sch, cfg)
    peak = peak_primary(g, scheds, cfg)
    return Evaluation(dict(fates), scheds, needs, total, objective(total, cfg), peak,
                      violations(g, total, peak)), ""


# -- planners -----------------------------------------------------------------
def _tie_key(g: InfoGraph, fates: Dict[str, Fate]) -> Tuple[int, ...]:
    return tuple(FATE_PREFERENCE.index(fates[s.name]) for s in g.states.values())


def search_exhaustive(g: InfoGraph, cfg: CostConfig, abl: Ablation, budget: int) -> Tuple[Dict[str, Fate], int]:
    order = g.reverse_topo()
    base = base_exec_cost(g, cfg)
    best: Dict[str, object] = {"obj": float("inf"), "key": None, "fates": None}
    nodes = [0]
    diag: List[str] = []

    def rec(i: int, pins: Dict[str, List[Need]], fates: Dict[str, Fate], scheds: Dict[str, Schedule], acc: CostVector):
        nodes[0] += 1
        if nodes[0] > budget:
            raise SearchBudgetExceeded()
        if i == len(order):
            total = acc + base
            obj = objective(total, cfg)
            viol = violations(g, total, peak_primary(g, scheds, cfg))
            if viol:
                if len(diag) < 3:
                    diag.append("; ".join(viol))
                return
            key = _tie_key(g, fates)
            if obj < best["obj"] - EPS or (abs(obj - best["obj"]) <= EPS and key < best["key"]):
                best.update(obj=obj, key=key, fates=dict(fates))
            return
        x = order[i]
        nd = needs_for(g, x, pins, abl)
        legal_any = False
        cands = candidate_fates(x)
        for f in sorted(cands, key=FATE_PREFERENCE.index):
            a = assess(g, x, f, nd, cfg, abl)
            if not a.legal:
                continue
            legal_any = True
            sch = build_schedule(g, x, f, nd, cfg)
            acc2 = acc + state_cost(g, x, sch, cfg)
            if objective(acc2 + base, cfg) > best["obj"] + EPS:
                continue
            pins2 = dict(pins)
            for dep, need in sch.pins:
                pins2[dep] = pins2.get(dep, []) + [need]
            fates[x.name] = f
            scheds[x.name] = sch
            rec(i + 1, pins2, fates, scheds, acc2)
            del fates[x.name], scheds[x.name]
        if not legal_any and len(diag) < 3:
            why = "; ".join(f"{f.value}: {assess(g, x, f, nd, cfg, abl).reason}" for f in cands)
            diag.append(f"no legal fate for '{x.name}' ({why})")

    rec(0, {}, {}, {}, CostVector())
    if best["fates"] is None:
        raise plan_error("no legal plan exists. " + (" | ".join(diag) if diag else "all fate combinations are illegal"))
    return best["fates"], nodes[0]  # type: ignore[return-value]


def search_greedy(g: InfoGraph, cfg: CostConfig, abl: Ablation) -> Dict[str, Fate]:
    pins: Dict[str, List[Need]] = {}
    fates: Dict[str, Fate] = {}
    for x in g.reverse_topo():
        nd = needs_for(g, x, pins, abl)
        options = []
        for f in candidate_fates(x):
            if assess(g, x, f, nd, cfg, abl).legal:
                sch = build_schedule(g, x, f, nd, cfg)
                options.append((objective(state_cost(g, x, sch, cfg), cfg), FATE_PREFERENCE.index(f), f, sch))
        if not options:
            raise plan_error(f"no legal fate for '{x.name}'")
        _, _, f, sch = min(options, key=lambda o: (o[0], o[1]))
        fates[x.name] = f
        for dep, need in sch.pins:
            pins.setdefault(dep, []).append(need)
    return fates


def conventional_fates(g: InfoGraph) -> Dict[str, Fate]:
    """Baseline: keep outputs/persistent states, erase everything else at death."""
    return {s.name: Fate.RETAIN if (s.is_output or s.persistent) else Fate.ERASE for s in g.states.values()}


# -- public entry point -------------------------------------------------------
def make_plan(g: InfoGraph, cfg: CostConfig, abl: Ablation = Ablation(), planner: str = "exhaustive",
              budget: int = 200_000) -> Plan:
    notes: List[str] = []
    nodes, optimal = 0, False
    used = planner
    if planner == "exhaustive":
        try:
            fates, nodes = search_exhaustive(g, cfg, abl, budget)
            optimal = True
        except SearchBudgetExceeded:
            notes.append(f"exhaustive search exceeded its budget ({budget} nodes); fell back to greedy "
                         f"(NOT guaranteed optimal)")
            fates, used = search_greedy(g, cfg, abl), "greedy"
    elif planner == "greedy":
        fates = search_greedy(g, cfg, abl)
    elif planner == "conventional":
        fates = conventional_fates(g)
        for s in g.states.values():
            if s.declared_destino is not None:
                fates[s.name] = s.declared_destino
    else:
        raise plan_error(f"unknown planner '{planner}' (exhaustive, greedy, conventional)")
    ev, why = evaluate(g, fates, cfg, abl)
    if ev is None:
        raise plan_error(f"planner '{used}' produced an illegal assignment: {why}")
    if ev.violations:
        raise plan_error(f"planner '{used}': " + "; ".join(ev.violations))
    reports = explain(g, ev, cfg, abl)
    if abl.names():
        notes.append("ABLATION ACTIVE (" + ", ".join(abl.names()) + "): the model is deliberately unsound; "
                     "run the verifier/interpreter to see the consequences")
    return Plan(g, cfg, abl, ev.fates, ev.schedules, ev.needs, assemble(g, ev.schedules), ev.cost, ev.objective,
                used, optimal, nodes, reports, notes)


def explain(g: InfoGraph, ev: Evaluation, cfg: CostConfig, abl: Ablation) -> Dict[str, StateReport]:
    """Per state and fate: legality + reason, and the whole-plan objective if only that state's fate changed."""
    reports: Dict[str, StateReport] = {}
    for x in g.states.values():
        nd = ev.needs[x.name]
        assessments = [assess(g, x, f, nd, cfg, abl) for f in ALL_FATES]
        alts: Dict[Fate, Optional[float]] = {}
        for a in assessments:
            if not a.legal:
                alts[a.fate] = None
                continue
            trial = dict(ev.fates)
            trial[x.name] = a.fate
            e2, _ = evaluate(g, trial, cfg, abl)
            alts[a.fate] = e2.objective if (e2 is not None and not e2.violations) else None
        reports[x.name] = StateReport(x.name, assessments, alts)
    return reports
