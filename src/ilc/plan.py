"""Execution plans: the ordered actions that realise a fate assignment."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from .fates import Schedule
from .ir import InfoGraph

PHASES = ("pre", "exec", "post")
_POST_RANK = {"CHECKPOINT_WRITE": 0, "MOVE_OUT": 1, "UNCOMPUTE": 1, "ERASE": 1, "RELEASE": 1}


@dataclass(frozen=True)
class PlanAction:
    idx: int
    slot: int
    phase: str
    kind: str
    state: str
    text: str


@dataclass
class ExecutionPlan:
    actions: List[PlanAction]

    def render(self) -> str:
        w = len(str(len(self.actions)))
        return "\n".join(f"{a.idx:>{w}}. [slot {a.slot} {a.phase:<4}] {a.text}" for a in self.actions)


def describe(g: InfoGraph, kind: str, state: str) -> str:
    p = g.producer(state)
    if kind in ("EXEC", "REGENERATE") and p is not None:
        body = f"{p.op.name}({', '.join(p.inputs)}) -> {state}"
        return body if kind == "EXEC" else f"recompute {body}"
    if kind == "UNCOMPUTE":
        if p is None:
            return f"uncompute {state}: (no producing transform: invalid)"
        return f"uncompute {state}: inverse({p.op.name}) with {', '.join(p.inputs)} live -> remove {state}"
    return {
        "ERASE": f"erase {state}",
        "RELEASE": f"release {state} (reset after drop)",
        "MOVE_OUT": f"move {state}: primary -> bulk",
        "MOVE_IN": f"move {state}: bulk -> primary",
        "CHECKPOINT_WRITE": f"checkpoint {state} -> durable",
        "RESTORE": f"restore {state}: durable -> primary",
        "EMIT": f"emit {state}",
    }[kind]


def assemble(g: InfoGraph, schedules: Dict[str, Schedule]) -> ExecutionPlan:
    """Order actions by slot and phase.  Within `pre`, dependencies come first
    (ascending birth); within `post`, dependents come first (descending birth),
    so inverses run before their dependencies are cleaned up (Bennett order)."""
    by_slot: Dict[Tuple[int, str], List[Tuple[Tuple, str, str]]] = {}
    for st in schedules.values():
        x = g.states[st.state]
        for a in st.acts:
            if a.phase == "pre":
                key = (x.birth, x.index, 0)
            else:
                key = (-x.birth, -x.index, _POST_RANK[a.kind])
            by_slot.setdefault((a.slot, a.phase), []).append((key, a.kind, a.state))
    out: List[PlanAction] = []

    def emit(slot: int, phase: str, kind: str, state: str):
        out.append(PlanAction(len(out) + 1, slot, phase, kind, state, describe(g, kind, state)))

    for slot in range(0, g.emit_slot + 1):
        for key, kind, state in sorted(by_slot.get((slot, "pre"), [])):
            emit(slot, "pre", kind, state)
        if 1 <= slot <= g.n_steps:
            t = g.transforms[slot - 1]
            emit(slot, "exec", "EXEC", t.output)
        if slot == g.emit_slot:
            for s in sorted(g.outputs(), key=lambda s: s.index):
                emit(slot, "exec", "EMIT", s.name)
        for key, kind, state in sorted(by_slot.get((slot, "post"), [])):
            emit(slot, "post", kind, state)
    return ExecutionPlan(out)


def plan_from_tuples(g: InfoGraph, rows: List[Tuple[int, str, str, str]]) -> ExecutionPlan:
    """Build a plan by hand from (slot, phase, kind, state) rows (tests, experiments, negative cases)."""
    return ExecutionPlan([PlanAction(i + 1, s, ph, k, st, describe(g, k, st)) for i, (s, ph, k, st) in enumerate(rows)])
