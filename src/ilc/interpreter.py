"""Reference interpreter: executes a plan on concrete bit-vector values and
checks it against the fate-free reference semantics (foundation 6.2).

It tracks three tiers (primary, bulk, durable), refuses to read what is not
resident, executes inverses for `uncompute`, and can inject a fault into a
recovery region to test replay / restore (recovery coupling).
Non-exact transforms (regen != exact) get seeded noise on every *execution*,
so a regenerated value really differs from the original.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .ir import InfoGraph, Region, TransformNode
from .ops import mask
from .plan import ExecutionPlan
from .types import Grade


def _noise(seed: int, state: str, count: int, bits: int) -> int:
    h = hashlib.sha256(f"{seed}:{state}:{count}".encode()).digest()
    return int.from_bytes(h[:8], "big") & mask(bits)


def default_inputs(g: InfoGraph, seed: int = 0) -> Dict[str, int]:
    return {s.name: _noise(seed, "input:" + s.name, 0, s.bits) for s in g.states.values() if s.kind == "input"}


def apply_op(g: InfoGraph, t: TransformNode, args: List[int], seed: int, count: int) -> int:
    bits = g.states[t.output].bits
    v = t.op.fn(args, bits) & mask(bits)
    if t.regen.kind == "exact":
        return v
    n = _noise(seed, t.output, count, bits)
    return n if t.regen.kind == "source_bound" else v ^ (n & 1)


def reference_values(g: InfoGraph, inputs: Dict[str, int], seed: int = 0) -> Dict[str, int]:
    vals = dict(inputs)
    for t in g.transforms:
        vals[t.output] = apply_op(g, t, [vals[i] for i in t.inputs], seed, 0)
    return vals


def acceptable(old: int, new: int, accept: Grade, bits: int) -> bool:
    if old == new or accept.kind == "distributional":
        return True
    if accept.kind == "tolerant":
        return abs(old - new) <= accept.eps * mask(bits)
    return False


@dataclass
class ExecutionResult:
    outputs: Dict[str, int]
    reference: Dict[str, int]
    errors: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    trace: List[str] = field(default_factory=list)
    recoveries: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors


class _Machine:
    def __init__(self, g: InfoGraph, inputs: Dict[str, int], seed: int):
        self.g, self.seed = g, seed
        self.primary: Dict[str, int] = dict(inputs)
        self.bulk: Dict[str, int] = {}
        self.durable: Dict[str, int] = {}
        self.count: Dict[str, int] = {}
        self.last: Dict[str, int] = {}
        self.res = ExecutionResult({}, {})
        self.diverged = False

    def err(self, idx: int, msg: str):
        self.res.errors.append(f"plan step {idx}: {msg}")

    def execute(self, state: str) -> int:
        t = self.g.producer(state)
        c = self.count.get(state, 0)
        self.count[state] = c + 1
        return apply_op(self.g, t, [self.primary[i] for i in t.inputs], self.seed, c)

    def need(self, idx: int, names: List[str], what: str) -> bool:
        missing = [n for n in names if n not in self.primary]
        if missing:
            self.err(idx, f"{what} needs {', '.join(missing)} resident in primary storage, but it was already "
                          f"released (use after release / lost dependency)")
        return not missing

    def regenerate(self, idx: int, state: str, why: str):
        t = self.g.producer(state)
        if not self.need(idx, t.inputs, why):
            return
        v = self.execute(state)
        old = self.last.get(state)
        if old is not None and not acceptable(old, v, self.g.states[state].accept, self.g.states[state].bits):
            self.err(idx, f"regenerated '{state}' differs from its original ({old} -> {v}) but acceptance grade "
                          f"is {self.g.states[state].accept}: unsound regeneration")
        elif old is not None and old != v:
            self.diverged = True
            self.res.notes.append(f"'{state}' regenerated with accepted divergence ({old} -> {v})")
        self.primary[state] = self.last[state] = v

    def inject(self, idx: int, r: Region):
        g = self.g
        corrupted = [m for m in r.members if m in self.primary]
        for m in corrupted:
            del self.primary[m]
        self.res.trace.append(f"   !! fault injected into region '{r.name}': corrupted {corrupted or 'nothing resident'}")
        local: Dict[str, int] = {}

        def obtain(n: str) -> int:
            if n in local:
                return local[n]
            if n in self.primary:
                return self.primary[n]
            if r.policy == "restore" and n in self.durable:
                return self.durable[n]
            if n in r.members:
                t = g.producer(n)
                args = [obtain(i) for i in t.inputs]
                c = self.count.get(n, 0)
                self.count[n] = c + 1
                local[n] = apply_op(g, t, args, self.seed, c)
                return local[n]
            raise LookupError(n)

        try:
            for m in corrupted:
                self.primary[m] = self.last[m] = obtain(m)
            self.res.recoveries += 1
            self.res.trace.append(f"   ok recovered region '{r.name}' by {r.policy}")
        except LookupError as e:
            self.err(idx, f"recovery of region '{r.name}' failed ({r.policy}): input {e} is not available at the "
                          f"commit point (frontier was released: recovery obligation not covered)")


def run_plan(g: InfoGraph, plan: ExecutionPlan, inputs: Optional[Dict[str, int]] = None, seed: int = 0,
             fault: Optional[str] = None) -> ExecutionResult:
    inputs = inputs or default_inputs(g, seed)
    m = _Machine(g, inputs, seed)
    m.last.update(inputs)
    ref = reference_values(g, inputs, seed)
    m.res.reference = {s.name: ref[s.name] for s in g.outputs()}
    region = next((r for r in g.regions if r.name == fault), None) if fault else None
    if fault and region is None:
        m.err(0, f"no recovery region named '{fault}'")
    for a in plan.actions:
        k, x = a.kind, a.state
        if k == "EXEC":
            t = g.producer(x)
            if m.need(a.idx, t.inputs, f"{t.op.name}"):
                v = m.execute(x)
                m.primary[x] = m.last[x] = v
            m.res.trace.append(f"{a.idx:>3}. {a.text}   = {m.primary.get(x)}")
            if region is not None and region.commit == x and region.commit_slot == a.slot:
                m.inject(a.idx, region)
            continue
        if k == "REGENERATE":
            m.regenerate(a.idx, x, f"recompute of {x}")
        elif k == "UNCOMPUTE":
            t = g.producer(x)
            if x not in m.primary:
                m.err(a.idx, f"uncompute of '{x}' but it is not resident")
            elif m.need(a.idx, t.inputs, f"inverse({t.op.name})"):
                again = m.execute(x)
                if again != m.primary[x]:
                    m.err(a.idx, f"uncompute of '{x}' left residual garbage: re-executing '{t.op.name}' does not "
                                 f"reproduce {m.primary[x]} (got {again}); the inverse is not exact")
                del m.primary[x]
        elif k in ("ERASE", "RELEASE"):
            if x in m.primary:
                del m.primary[x]
            else:
                m.err(a.idx, f"{k.lower()} of '{x}' but it is not resident")
        elif k == "MOVE_OUT":
            if x in m.primary:
                m.bulk[x] = m.primary.pop(x)
            else:
                m.err(a.idx, f"move of '{x}' but it is not resident")
        elif k == "MOVE_IN":
            if x in m.bulk:
                m.primary[x] = m.bulk.pop(x)
            else:
                m.err(a.idx, f"fetch of '{x}' but it is not in bulk storage")
        elif k == "CHECKPOINT_WRITE":
            if x in m.primary:
                m.durable[x] = m.primary[x]
            else:
                m.err(a.idx, f"checkpoint of '{x}' but it is not resident")
        elif k == "RESTORE":
            if x in m.durable:
                m.primary[x] = m.durable[x]
            else:
                m.err(a.idx, f"restore of '{x}' but no durable copy exists")
        elif k == "EMIT":
            if x in m.primary:
                m.res.outputs[x] = m.primary[x]
            else:
                m.err(a.idx, f"emit of '{x}' but it is not resident")
        m.res.trace.append(f"{a.idx:>3}. {a.text}")
    # compare against fate-free reference semantics
    for name, want in m.res.reference.items():
        got = m.res.outputs.get(name)
        if got is None:
            if not any(f"emit of '{name}'" in e for e in m.res.errors):
                m.res.errors.append(f"output '{name}' was never emitted")
        elif got != want:
            msg = f"output '{name}' = {got} differs from the fate-free reference {want}"
            if m.diverged:
                m.res.notes.append(msg + " (accepted: an upstream regeneration declared a weaker acceptance grade)")
            else:
                m.res.errors.append(msg)
    return m.res
