"""Abstract execution simulator: walks an ExecutionPlan and reports model costs.

It reconstructs residency windows from the plan's actions alone, independently
of the planner's analytic schedule costs; tests assert the two agree.
Outputs are MODEL numbers in abstract units, not physical measurements.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .costs import CostConfig, CostVector, action_cost, base_exec_cost, exposure_cost, objective, storage_cost
from .costs import Window
from .ir import InfoGraph
from .plan import ExecutionPlan

COUNT_KEYS = {"EXEC": "executions", "REGENERATE": "recomputations", "CHECKPOINT_WRITE": "checkpoints",
              "RESTORE": "restores", "UNCOMPUTE": "uncomputes", "ERASE": "erasures", "RELEASE": "releases",
              "MOVE_OUT": "moves_out", "MOVE_IN": "moves_in", "EMIT": "emits"}


@dataclass
class SimReport:
    steps: int
    cost: CostVector
    objective: float
    peak_storage: int
    peak_temporary: int
    counts: Dict[str, int]
    occupancy: List[int] = field(default_factory=list)  # primary bits per slot


def simulate(g: InfoGraph, plan: ExecutionPlan, cfg: CostConfig) -> SimReport:
    end = g.end_slot(cfg.horizon)
    opened: Dict[str, int] = {s.name: 0 for s in g.states.values() if s.kind == "input"}
    bulk_open: Dict[str, int] = {}
    windows: Dict[str, List[Window]] = {n: [] for n in g.states}
    durable_start: Dict[str, Optional[int]] = {n: None for n in g.states}
    energy = latency = 0.0
    counts = {v: 0 for v in COUNT_KEYS.values()}

    for a in plan.actions:
        x = g.states[a.state]
        p = g.producer(a.state)
        w = p.op.weight if p else 0.0
        e, l = action_cost(a.kind, w, x.bits, cfg)
        energy, latency = energy + e, latency + l
        counts[COUNT_KEYS[a.kind]] += 1
        k = a.kind
        if k in ("EXEC", "REGENERATE", "RESTORE"):
            opened[a.state] = a.slot
        elif k == "MOVE_IN":
            opened[a.state] = a.slot
            if a.state in bulk_open:  # tolerate malformed plans: the verifier reports them
                windows[a.state].append(("bulk", bulk_open.pop(a.state), a.slot - 1))
        elif k in ("ERASE", "RELEASE", "UNCOMPUTE"):
            if a.state in opened:
                windows[a.state].append(("primary", opened.pop(a.state), a.slot))
        elif k == "MOVE_OUT":
            if a.state in opened:
                windows[a.state].append(("primary", opened.pop(a.state), a.slot))
            bulk_open[a.state] = a.slot + 1
        elif k == "CHECKPOINT_WRITE":
            windows[a.state].append(("durable", a.slot, end))
            durable_start[a.state] = a.slot
    for name, start in opened.items():
        windows[name].append(("primary", start, end))

    storage = recovery = 0.0
    occ = [0] * (end + 1)
    temp = [0] * (end + 1)
    for name, ws in windows.items():
        x = g.states[name]
        storage += storage_cost(ws, x.bits, cfg)
        recovery += exposure_cost(g, x, ws, durable_start[name], cfg)
        for tier, s, e in ws:
            if tier == "primary":
                for t in range(s, e + 1):
                    occ[t] += x.bits
                    if x.kind == "derived" and not x.is_output:
                        temp[t] += x.bits
    base = base_exec_cost(g, cfg)  # recovery-region constants only; execution energy is walked above
    cv = CostVector(energy, storage, latency, recovery + base.recovery)
    return SimReport(len(plan.actions), cv, objective(cv, cfg), max(occ), max(temp), counts, occ)
