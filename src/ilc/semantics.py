"""Semantic checker: AST -> validated InfoGraph (or diagnostics).

Independent of the planner: it only decides whether the *program* is
well-formed (types, dependencies, lifetimes, pinned fates, recovery regions).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from .costs import CostConfig
from .diagnostics import Diagnostic
from .fates import static_illegal
from .ir import (Component, Constraint, InfoGraph, Machine, Region, StateNode, TransformNode,
                 default_machine)
from .ops import OPS
from .syntax import (ComponenteDecl, EmitDecl, FlussoDecl, RecuperoDecl, StatoDecl, SystemAst,
                     TrasformaDecl, Value, VincoloDecl)
from .types import (DISTRIBUTIONAL, EXACT, SOURCE_BOUND, TYPE_BITS, Boundary, Fate, Grade, HARD,
                    NO_BOUNDARY, soft, tolerant)

CONSTRAINT_DIMS = ("energy", "storage", "latency", "recovery", "peak_storage")
ROLES = ("primary", "bulk", "durable")


@dataclass
class CheckResult:
    graph: Optional[InfoGraph]
    diagnostics: List[Diagnostic]

    @property
    def ok(self) -> bool:
        return self.graph is not None and not any(d.severity == "error" for d in self.diagnostics)


class _Checker:
    def __init__(self, ast: SystemAst, cfg: Optional[CostConfig]):
        self.ast, self.cfg = ast, cfg or CostConfig()
        self.file = ast.file
        self.diags: List[Diagnostic] = []

    def err(self, code: str, msg: str, loc=None, severity: str = "error"):
        self.diags.append(Diagnostic(code, msg, self.file, getattr(loc, "line", 0), getattr(loc, "col", 0), severity))

    # -- value helpers -------------------------------------------------------
    def grade_of(self, v: Value, what: str) -> Optional[Grade]:
        if v.kind == "ident" and v.name in ("exact", "distributional", "source_bound"):
            return {"exact": EXACT, "distributional": DISTRIBUTIONAL, "source_bound": SOURCE_BOUND}[v.name]
        if v.kind == "call" and v.name == "tolerant" and len(v.args) == 1 and v.args[0].kind == "number" \
                and v.args[0].number > 0:
            return tolerant(v.args[0].number)
        self.err("E-PROP", f"invalid {what}: expected exact, tolerant(eps>0), distributional or source_bound", v.loc)
        return None

    def boundary_of(self, v: Value) -> Optional[Boundary]:
        if v.kind == "ident" and v.name in ("none", "hard"):
            return NO_BOUNDARY if v.name == "none" else HARD
        if v.kind == "call" and v.name == "soft" and len(v.args) == 1 and v.args[0].kind == "number" \
                and 0 < v.args[0].number <= 1:
            return soft(v.args[0].number)
        self.err("E-PROP", "invalid bnd: expected none, soft(eta in (0,1]) or hard", v.loc)
        return None

    # -- passes --------------------------------------------------------------
    def run(self) -> CheckResult:
        items = self.ast.items
        machine = self.machine([i for i in items if isinstance(i, (ComponenteDecl, FlussoDecl))])
        decl: Dict[str, StatoDecl] = {}
        for it in (i for i in items if isinstance(i, StatoDecl)):
            if it.name in decl:
                self.err("E-DUP", f"duplicate declaration of state '{it.name}' (first declared at line "
                                  f"{decl[it.name].loc.line})", it.loc)
                continue
            if it.type_name not in TYPE_BITS:
                self.err("E-TYPE", f"unknown type '{it.type_name}'; expected one of: {', '.join(TYPE_BITS)}",
                         it.type_loc)
            decl[it.name] = it
        tdecls = [i for i in items if isinstance(i, TrasformaDecl)]
        producers: Dict[str, int] = {}
        for step, t in enumerate(tdecls, 1):
            name, loc = t.output
            if name in producers:
                self.err("E-DUP", f"state '{name}' is produced by more than one transform (steps "
                                  f"{producers[name]} and {step}); states are single-assignment", loc)
            else:
                producers[name] = step

        states: Dict[str, StateNode] = {}

        def new_state(name: str, ty: str, loc) -> StateNode:
            node = StateNode(name, ty, TYPE_BITS.get(ty, 1), len(states), "derived" if name in producers else "input",
                             producers.get(name, 0), line=getattr(loc, "line", 0), col=getattr(loc, "col", 0))
            states[name] = node
            return node

        for d in decl.values():
            new_state(d.name, d.type_name, d.loc)

        transforms: List[TransformNode] = []
        for step, t in enumerate(tdecls, 1):
            op = OPS.get(t.op)
            if op is None:
                self.err("E-OP", f"unknown transform '{t.op}'; available: {', '.join(sorted(OPS))}", t.loc)
                continue
            if len(t.inputs) != op.arity:
                self.err("E-ARITY", f"transform '{t.op}' takes {op.arity} input(s), got {len(t.inputs)}", t.loc)
                continue
            ok, in_types = True, []
            for name, loc in t.inputs:
                if name == t.output[0]:
                    self.err("E-DEP", f"state '{name}' depends on itself (cycle)", loc)
                    ok = False
                elif name not in states and name not in producers:
                    self.err("E-UNDEF", f"undefined state '{name}'", loc)
                    ok = False
                elif name in producers and producers[name] >= step:
                    self.err("E-DEP", f"invalid dependency: '{name}' is used at step {step} but produced at "
                                      f"step {producers[name]}", loc)
                    ok = False
                elif name not in states:
                    ok = False  # produced earlier but erroneous
                else:
                    in_types.append(states[name].type_name)
            if not ok:
                continue
            try:
                rtype = op.result_type(in_types)
            except ValueError as e:
                self.err("E-TYPE", f"invalid types for '{t.op}': {e}", t.loc)
                continue
            oname, oloc = t.output
            if oname in states:
                if states[oname].type_name != rtype:
                    self.err("E-TYPE", f"state '{oname}' is declared {states[oname].type_name} but "
                                       f"'{t.op}' produces {rtype}", oloc)
            else:
                new_state(oname, rtype, oloc)
            regen, bnd = op.regen, op.boundary
            for p in t.props:
                if p.key == "regen":
                    g = self.grade_of(p.value, "regen")
                    if g is not None:
                        regen = g
                elif p.key == "bnd":
                    b = self.boundary_of(p.value)
                    if b is not None:
                        if b.weaker_than(op.boundary):
                            self.err("E-BOUNDARY", f"bnd={b} understates the intrinsic irreversibility of "
                                                   f"'{t.op}' ({op.boundary}); a boundary cannot be weakened", p.loc)
                        else:
                            bnd = b
                else:
                    self.err("E-PROP", f"unknown transform property '{p.key}' (allowed: regen, bnd)", p.loc)
            transforms.append(TransformNode(step, op, [n for n, _ in t.inputs], oname, regen, bnd,
                                            t.loc.line, t.loc.col))
        # kind/birth for states created before producers were known are already set via `producers`
        for t in transforms:
            for n in t.inputs:
                if n in states:
                    states[n].uses.append(t.step)
                    states[n].consumers.append(t.output)
        for s in states.values():
            s.uses = sorted(set(s.uses))
        n_steps = len(tdecls)

        for it in (i for i in items if isinstance(i, EmitDecl)):
            for name, loc in it.names:
                if name not in states:
                    self.err("E-UNDEF", f"undefined state '{name}' in emit", loc)
                else:
                    states[name].is_output = True

        for d in decl.values():
            if d.name in states:
                self.state_props(states[d.name], d, states, n_steps)

        graph = InfoGraph(self.ast.name, states, transforms, [], [], machine, self.file)
        graph.regions = self.regions([i for i in items if isinstance(i, RecuperoDecl)], graph)
        for it in (i for i in items if isinstance(i, VincoloDecl)):
            if it.dim not in CONSTRAINT_DIMS:
                self.err("E-CONSTRAINT", f"unknown constraint dimension '{it.dim}'; expected one of: "
                                         f"{', '.join(CONSTRAINT_DIMS)}", it.loc)
            elif it.cmp not in ("<", "<="):
                self.err("E-CONSTRAINT", "only upper bounds (< or <=) are supported in v0.1", it.loc)
            else:
                graph.constraints.append(Constraint(it.dim, it.cmp, it.value, it.loc.line))
        self.check_pins(graph, decl)
        if any(d.severity == "error" for d in self.diags):
            return CheckResult(None, self.diags)
        return CheckResult(graph, self.diags)

    # -- machine -------------------------------------------------------------
    def machine(self, items) -> Machine:
        comps = [i for i in items if isinstance(i, ComponenteDecl)]
        flows = [i for i in items if isinstance(i, FlussoDecl)]
        if not comps and not flows:
            return default_machine()
        by_name: Dict[str, Component] = {}
        by_role: Dict[str, Component] = {}
        for c in comps:
            role, cap = None, None
            for p in c.props:
                if p.key == "role" and p.value.kind == "ident" and p.value.name in ROLES:
                    role = p.value.name
                elif p.key == "capacity" and p.value.kind == "number" and p.value.number >= 0:
                    cap = p.value.number
                else:
                    self.err("E-COMPONENT", f"invalid component property '{p.key}' (allowed: role="
                                            f"{'|'.join(ROLES)}, capacity=<bits>)", p.loc)
            if role is None:
                self.err("E-COMPONENT", f"component '{c.name}' needs role = primary|bulk|durable", c.loc)
                continue
            if role in by_role or c.name in by_name:
                self.err("E-DUP", f"duplicate component or role '{role}' (v0.1 allows one component per role)", c.loc)
                continue
            by_name[c.name] = by_role[role] = Component(c.name, role, cap)
        if "primary" not in by_role:
            self.err("E-COMPONENT", "an explicit machine must declare a 'primary' component", None)
        fl = set()
        for f in flows:
            a, b = f.src[0], f.dst[0]
            for n, loc in (f.src, f.dst):
                if n not in by_name:
                    self.err("E-UNDEF", f"undefined component '{n}' in flusso", loc)
            if a in by_name and b in by_name:
                fl.add((by_name[a].role, by_name[b].role))
        return Machine(by_role, fl, explicit=True)

    # -- state properties ----------------------------------------------------
    def state_props(self, s: StateNode, d: StatoDecl, states: Dict[str, StateNode], n_steps: int):
        emit_slot = n_steps + 1
        for p in d.props:
            v = p.value
            if p.key == "durata":
                if v.kind == "ident" and v.name in ("temporary", "persistent"):
                    s.durata_kind = v.name
                elif v.kind == "call" and v.name == "until" and len(v.args) == 1 and v.args[0].kind == "ident":
                    tgt = v.args[0].name
                    if tgt not in states:
                        self.err("E-DURATA", f"invalid until(...) target: undefined state '{tgt}'", v.args[0].loc)
                    elif tgt == s.name:
                        self.err("E-DURATA", f"until({tgt}): a state cannot be relevant until itself", v.loc)
                    else:
                        s.durata_kind, s.durata_arg, s.durata_end = "until", tgt, states[tgt].birth
                elif v.kind == "call" and v.name == "steps" and len(v.args) == 1 and v.args[0].kind == "number" \
                        and v.args[0].number >= 0 and float(v.args[0].number).is_integer():
                    k = int(v.args[0].number)
                    s.durata_kind, s.durata_arg, s.durata_end = "steps", k, s.birth + k
                    if s.durata_end > emit_slot:
                        self.err("E-LIFETIME", f"impossible lifetime: steps({k}) from birth slot {s.birth} ends at "
                                               f"slot {s.durata_end}, after the program end (slot {emit_slot})", v.loc)
                else:
                    self.err("E-DURATA", "invalid durata: expected temporary, persistent, until(<state>) or "
                                         "steps(<n>)", v.loc)
            elif p.key == "destino":
                if v.kind == "ident" and v.name == "auto":
                    s.declared_destino = None
                elif v.kind == "ident" and v.name in [f.value for f in Fate]:
                    s.declared_destino = Fate(v.name)
                else:
                    shown = v.name if v.name else "<value>"
                    self.err("E-FATE", f"invalid fate '{shown}'; expected auto or one of: "
                                       f"{', '.join(f.value for f in Fate)}", v.loc)
            elif p.key == "accept":
                g = self.grade_of(v, "accept")
                if g is not None:
                    if g.kind == "source_bound":
                        self.err("E-PROP", "accept=source_bound is meaningless: nothing can be regenerated to it", v.loc)
                    else:
                        s.accept = g
            else:
                self.err("E-PROP", f"unknown state property '{p.key}' (allowed: durata, destino, accept)", p.loc)
        if s.durata_end is not None and s.durata_end < s.birth:
            self.err("E-LIFETIME", f"inconsistent lifetime: '{s.name}' is relevant until slot {s.durata_end} but is "
                                   f"born at slot {s.birth}", d.loc)
        if s.durata_end is not None and s.uses and max(s.uses) > s.durata_end:
            self.err("E-USE-AFTER-DEATH", f"use after death: '{s.name}' is used at slot {max(s.uses)} but its "
                                          f"durata ends at slot {s.durata_end}", d.loc)
        if s.durata_end is not None and s.is_output and emit_slot > s.durata_end:
            self.err("E-USE-AFTER-DEATH", f"use after death: output '{s.name}' is emitted at slot {emit_slot} but "
                                          f"its durata ends at slot {s.durata_end}", d.loc)

    # -- recovery regions ----------------------------------------------------
    def regions(self, decls: List[RecuperoDecl], g: InfoGraph) -> List[Region]:
        out: List[Region] = []
        seen = set()
        for r in decls:
            if r.name in seen:
                self.err("E-DUP", f"duplicate recupero region '{r.name}'", r.loc)
                continue
            seen.add(r.name)
            members: List[str] = []
            policy, commit = "replay", None
            props = {p.key: p for p in r.props}
            for k in props:
                if k not in ("region", "policy", "commit"):
                    self.err("E-PROP", f"unknown recupero property '{k}' (allowed: region, policy, commit)", props[k].loc)
            if "region" not in props or props["region"].value.kind != "list":
                self.err("E-RECOVERY", f"recupero '{r.name}' needs region = [state, ...]", r.loc)
                continue
            for item in props["region"].value.args:
                n = item.name if item.kind == "ident" else None
                if n is None or n not in g.states:
                    self.err("E-UNDEF", f"undefined state '{n}' in recupero '{r.name}'", item.loc)
                elif g.states[n].kind != "derived":
                    self.err("E-RECOVERY", f"recovery constraint violation: '{n}' is an input, not produced by a "
                                           f"transform; a region protects computations", item.loc)
                else:
                    members.append(n)
            if not members:
                self.err("E-RECOVERY", f"recupero '{r.name}' protects no computation", r.loc)
                continue
            if "policy" in props:
                v = props["policy"].value
                if v.kind == "ident" and v.name in ("replay", "restore"):
                    policy = v.name
                else:
                    self.err("E-RECOVERY", "invalid policy: expected replay or restore", v.loc)
            members = sorted(set(members), key=lambda n: g.states[n].birth)
            if "commit" in props:
                v = props["commit"].value
                if v.kind == "ident" and v.name in members:
                    commit = v.name
                else:
                    self.err("E-RECOVERY", f"recovery constraint violation: commit must name a region member "
                                           f"({', '.join(members)})", v.loc)
            commit = commit or members[-1]
            inside = set(members)
            frontier: List[str] = []
            for m in members:
                for dep in g.producer(m).inputs:
                    if dep not in inside and dep not in frontier:
                        frontier.append(dep)
            frontier.sort(key=lambda n: g.states[n].index)
            if policy == "restore" and not g.machine.has("durable"):
                self.err("E-RECOVERY", f"recovery constraint violation: recupero '{r.name}' uses policy=restore but "
                                       f"the machine has no durable component", r.loc)
            out.append(Region(r.name, members, policy, commit, g.states[commit].birth, frontier, r.loc.line))
        return out

    # -- pinned destino sanity -------------------------------------------------
    def check_pins(self, g: InfoGraph, decl: Dict[str, StatoDecl]):
        for name, d in decl.items():
            s = g.states.get(name)
            if s is None or s.declared_destino is None:
                continue
            res = static_illegal(g, s, s.declared_destino, self.cfg)
            if res is not None:
                code, reason = res
                self.err(code, f"illegal fate '{s.declared_destino.value}' for '{name}': {reason}", d.loc)


def check(ast: SystemAst, cfg: Optional[CostConfig] = None) -> CheckResult:
    return _Checker(ast, cfg).run()
