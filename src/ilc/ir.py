"""Information-Lifetime IR: the information graph and lifetime metadata.

Research concepts (foundation sections 6, 8, 15): information objects with
identity, transforms with determinism/inverse/boundary grades, recovery regions
whose frontiers create *shadow uses*, and lifetimes (birth, uses, death).

Time model ("slots"): slot 0 = inputs loaded; slot k (1..N) = transform k
executes; slot N+1 = emit (outputs delivered).  A state's `death` is the last
slot at which anything needs it; fates act at its *release point* after death.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from .ops import Op
from .types import EXACT, Boundary, Fate, Grade


@dataclass(frozen=True)
class Need:
    """Something that requires a state to be available at `slot`.

    kind: use | shadow | durata | emit | pin-uncompute | pin-regen
    """
    slot: int
    kind: str
    accept: Grade = EXACT
    src: str = ""


@dataclass
class StateNode:
    name: str
    type_name: str
    bits: int
    index: int
    kind: str  # 'input' | 'derived'
    birth: int
    declared_destino: Optional[Fate] = None  # None means auto
    accept: Grade = EXACT
    durata_kind: str = "temporary"  # temporary | persistent | until | steps
    durata_arg: Optional[object] = None
    durata_end: Optional[int] = None
    is_output: bool = False
    uses: List[int] = field(default_factory=list)  # slots of consuming transforms
    consumers: List[str] = field(default_factory=list)  # output names of consumers
    line: int = 0
    col: int = 0

    @property
    def persistent(self) -> bool:
        return self.durata_kind == "persistent"


@dataclass
class TransformNode:
    step: int
    op: Op
    inputs: List[str]
    output: str
    regen: Grade  # regeneration grade of this transform's output
    boundary: Boundary  # irreversibility grade
    line: int = 0
    col: int = 0


@dataclass
class Region:
    """A recovery region (`recupero`): protects the computation of `members`."""
    name: str
    members: List[str]
    policy: str  # replay | restore
    commit: str
    commit_slot: int
    frontier: List[str]  # states consumed from outside the region
    line: int = 0


@dataclass
class Constraint:
    dim: str
    cmp: str
    value: float
    line: int = 0

    def holds(self, x: float) -> bool:
        return {"<": x < self.value, "<=": x <= self.value,
                ">": x > self.value, ">=": x >= self.value}[self.cmp]

    def __str__(self) -> str:
        return f"{self.dim} {self.cmp} {self.value:g}"


@dataclass
class Component:
    name: str
    role: str  # primary | bulk | durable
    capacity: Optional[float] = None


@dataclass
class Machine:
    components: Dict[str, Component]  # role -> component
    flows: Set[Tuple[str, str]]  # (src_role, dst_role)
    explicit: bool = False

    def has(self, role: str) -> bool:
        return role in self.components

    def flow(self, a: str, b: str) -> bool:
        return (a, b) in self.flows


def default_machine() -> Machine:
    comps = {r: Component(r, r) for r in ("primary", "bulk", "durable")}
    flows = {("primary", "bulk"), ("bulk", "primary"), ("primary", "durable"), ("durable", "primary")}
    return Machine(comps, flows, explicit=False)


@dataclass
class Lifetime:
    name: str
    birth: int
    uses: List[int]
    shadow: List[int]
    durata_end: Optional[int]
    death: int

    @property
    def interval(self) -> Tuple[int, int]:
        return (self.birth, self.death)


@dataclass
class InfoGraph:
    name: str
    states: Dict[str, StateNode]
    transforms: List[TransformNode]
    regions: List[Region]
    constraints: List[Constraint]
    machine: Machine
    file: str = "<input>"

    # -- structure ---------------------------------------------------------
    @property
    def n_steps(self) -> int:
        return len(self.transforms)

    @property
    def emit_slot(self) -> int:
        return self.n_steps + 1

    def end_slot(self, horizon: int) -> int:
        return self.emit_slot + horizon

    def producer(self, name: str) -> Optional[TransformNode]:
        for t in self.transforms:
            if t.output == name:
                return t
        return None

    def dependents(self, name: str) -> List[TransformNode]:
        return [t for t in self.transforms if name in t.inputs]

    def deps(self, name: str) -> List[str]:
        p = self.producer(name)
        return list(p.inputs) if p else []

    def reverse_topo(self) -> List[StateNode]:
        """Dependents before dependencies (descending birth)."""
        return sorted(self.states.values(), key=lambda s: (-s.birth, -s.index))

    def outputs(self) -> List[StateNode]:
        return [s for s in self.states.values() if s.is_output]

    # -- lifetime ----------------------------------------------------------
    def base_needs(self, x: StateNode, *, recovery: bool = True) -> List[Need]:
        """Needs implied by the program itself (uses, emit, durata, shadow uses)."""
        needs = [Need(u, "use", x.accept, "transform") for u in x.uses]
        if x.is_output:
            needs.append(Need(self.emit_slot, "emit", x.accept, "emit"))
        if x.durata_kind == "persistent":
            needs.append(Need(self.emit_slot, "durata", x.accept, "persistent"))
        elif x.durata_end is not None:
            needs.append(Need(x.durata_end, "durata", x.accept, x.durata_kind))
        if recovery:
            for r in self.regions:
                if x.name in r.frontier:
                    needs.append(Need(r.commit_slot, "shadow", x.accept, r.name))
        return needs

    def lifetime(self, name: str, *, recovery: bool = True) -> Lifetime:
        x = self.states[name]
        needs = self.base_needs(x, recovery=recovery)
        shadow = sorted({n.slot for n in needs if n.kind == "shadow"})
        death = max([x.birth] + [n.slot for n in needs])
        return Lifetime(name, x.birth, sorted(x.uses), shadow, x.durata_end, death)


# -- text rendering --------------------------------------------------------
def render_graph(g: InfoGraph) -> str:
    """ASCII rendering: one block per transform, inputs joined by brackets."""
    lines: List[str] = []
    width = max([len(n) for n in g.states] + [1])
    for t in g.transforms:
        out = g.states[t.output]
        tag = "  (output)" if out.is_output else ""
        op = f"[{t.step}] {t.op.name}"
        if t.boundary.kind != "none":
            op += f" {{bnd={t.boundary}}}"
        tail = f"{op} ──> {t.output}{tag}"
        n = len(t.inputs)
        if n == 0:
            lines.append(f"{' ' * width}   {tail}")
        elif n == 1:
            lines.append(f"{t.inputs[0].ljust(width)} ─── {tail}")
        else:
            half = (n + 1) // 2
            for i, name in enumerate(t.inputs):
                joint = "┐" if i == 0 else ("┘" if i == n - 1 else "┤")
                lines.append(f"{name.ljust(width)} ──{joint}")
                if i == half - 1:
                    lines.append(f"{' ' * width}   ├─ {tail}")
        lines.append("")
    inputs = [s.name for s in g.states.values() if s.kind == "input"]
    head = f"inputs: {', '.join(inputs) if inputs else '(none)'}"
    return head + "\n" + "\n".join(lines).rstrip()


def render_lifetimes(g: InfoGraph, recovery: bool = True) -> str:
    rows = [("state", "type", "kind", "birth", "uses", "shadow", "durata", "death")]
    for s in g.states.values():
        lt = g.lifetime(s.name, recovery=recovery)
        d = s.durata_kind
        if s.durata_kind == "until":
            d = f"until({s.durata_arg})"
        elif s.durata_kind == "steps":
            d = f"steps({s.durata_arg})"
        extra = " (output)" if s.is_output else ""
        rows.append((s.name, s.type_name, s.kind + extra, str(lt.birth), str(lt.uses),
                     str(lt.shadow), d, str(lt.death)))
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    return "\n".join("  ".join(c.ljust(w) for c, w in zip(r, widths)).rstrip() for r in rows)


def render_regions(g: InfoGraph) -> str:
    if not g.regions:
        return "(no recovery regions)"
    out = []
    for r in g.regions:
        out.append(f"{r.name}: policy={r.policy} members={r.members} commit={r.commit}@slot {r.commit_slot}"
                   f" frontier={r.frontier} (shadow uses at slot {r.commit_slot})")
    return "\n".join(out)
