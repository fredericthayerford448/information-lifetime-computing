"""Independent plan verifier (foundation 16.3: 'the verifier is the first thing to build').

It checks an ExecutionPlan against the IR using only the plan's actions - it
does not use the planner's schedules or legality functions.  Checks map to the
foundation invariants:

  P1  plan completeness (every transform executed once, in order; outputs emitted)
  I2  coverage (every read finds a resident materialization; durata needs met;
      premature erase / use after release)
  I3  recovery closure (frontier of every recupero region available at its commit slot)
  I4  dependency pinning (inverse / regeneration steps find their inputs live)
  I5  boundary respect (uncompute / recompute legality: HARD, SOFT residual, grade)
  I6  accounting (persistent state never destroyed; clean exit: no leaked temporaries)
  I7  restores only read durable copies that were written
  C   program constraints and machine capacity
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Set, Tuple

from .costs import CostConfig
from .ir import InfoGraph
from .plan import ExecutionPlan
from .simulator import simulate
from .types import satisfies

TITLES = {
    "P1": "plan completeness", "I2": "coverage (no use after release / premature erase)",
    "I3": "recovery closure (frontier available at commit)", "I4": "dependency pinning (inverse/regeneration inputs live)",
    "I5": "boundary respect (uncompute/recompute legality)", "I6": "accounting (persistent kept, clean exit)",
    "I7": "restores read durable copies", "C": "program constraints",
}
ORDER = ["P1", "I2", "I3", "I4", "I5", "I6", "I7", "C"]


@dataclass
class VerificationReport:
    violations: Dict[str, List[str]]

    @property
    def ok(self) -> bool:
        return not any(self.violations.values())

    def format(self) -> str:
        lines = []
        for cid in ORDER:
            v = self.violations[cid]
            lines.append(f"  {cid:<3} {TITLES[cid]:<58} {'PASS' if not v else 'FAIL'}")
            lines += [f"        - {m}" for m in v]
        return "\n".join(lines)

    def all_messages(self) -> List[str]:
        return [f"{cid}: {m}" for cid in ORDER for m in self.violations[cid]]


def verify(g: InfoGraph, plan: ExecutionPlan, cfg: CostConfig) -> VerificationReport:
    V: Dict[str, List[str]] = {cid: [] for cid in ORDER}
    resident: Set[str] = {s.name for s in g.states.values() if s.kind == "input"}
    bulk: Set[str] = set()
    durable: Set[str] = set()
    removed: Dict[str, Tuple[str, int]] = {}
    snap: Dict[int, Tuple[Set[str], Set[str]]] = {}
    execs: List[str] = []
    emits: List[str] = []

    def take(slot: int):
        snap.setdefault(slot, (set(resident), set(durable)))

    prev_slot = 0
    for a in plan.actions:
        if a.slot != prev_slot:
            take(prev_slot)
            prev_slot = a.slot
        if a.phase == "post":
            take(a.slot)
        x, k = a.state, a.kind
        st = g.states[x]
        prod = g.producer(x)
        # reads ---------------------------------------------------------
        if k in ("EXEC", "REGENERATE", "UNCOMPUTE"):
            if prod is None:
                V["I4"].append(f"step {a.idx}: {k} of '{x}' which has no producing transform")
            else:
                for i in prod.inputs:
                    if i not in resident:
                        why = f" (it was {removed[i][0].lower()}d at step {removed[i][1]})" if i in removed else ""
                        V["I2" if k == "EXEC" else "I4"].append(
                            f"step {a.idx}: {k} of '{x}' needs '{i}' resident{why}")
        if k in ("UNCOMPUTE", "ERASE", "RELEASE", "MOVE_OUT", "CHECKPOINT_WRITE", "EMIT") and x not in resident:
            V["I2"].append(f"step {a.idx}: {k} of '{x}' but it is not resident")
        if k == "RESTORE" and x not in durable:
            V["I7"].append(f"step {a.idx}: RESTORE of '{x}' but no durable copy was written")
        if k == "MOVE_IN" and x not in bulk:
            V["I2"].append(f"step {a.idx}: MOVE_IN of '{x}' but it is not in bulk storage")
        if k in ("REGENERATE", "EXEC") and x in resident and k == "REGENERATE":
            V["I2"].append(f"step {a.idx}: REGENERATE of '{x}' while a materialization is already resident")
        # boundary ------------------------------------------------------------
        if k == "UNCOMPUTE" and prod is not None:
            if prod.boundary.kind == "hard":
                V["I5"].append(f"step {a.idx}: uncompute of '{x}' crosses a HARD boundary ('{prod.op.name}')")
            elif prod.boundary.kind == "soft" and prod.boundary.eta > cfg.eps_clean:
                V["I5"].append(f"step {a.idx}: uncompute of '{x}' across SOFT(eta={prod.boundary.eta:g}) > "
                               f"eps_clean={cfg.eps_clean:g}")
            if prod.regen.kind != "exact":
                V["I5"].append(f"step {a.idx}: uncompute of '{x}' via non-exact '{prod.op.name}' (grade {prod.regen})")
        if k == "REGENERATE" and prod is not None and not satisfies(prod.regen, st.accept):
            V["I5"].append(f"step {a.idx}: recompute of '{x}': grade {prod.regen} does not satisfy acceptance {st.accept}")
        if k in ("UNCOMPUTE", "ERASE", "RELEASE", "MOVE_OUT") and st.persistent:
            V["I6"].append(f"step {a.idx}: persistent state '{x}' is destroyed by {k}")
        # effects -------------------------------------------------------------
        if k == "EXEC":
            execs.append(x)
            resident.add(x)
        elif k == "EMIT":
            emits.append(x)
        elif k in ("REGENERATE", "RESTORE"):
            resident.add(x)
        elif k == "MOVE_IN":
            bulk.discard(x)
            resident.add(x)
        elif k == "MOVE_OUT":
            resident.discard(x)
            bulk.add(x)
        elif k in ("ERASE", "RELEASE", "UNCOMPUTE"):
            resident.discard(x)
            removed[x] = (k, a.idx)
        elif k == "CHECKPOINT_WRITE":
            durable.add(x)
    for s in range(0, g.emit_slot + 1):
        take(s)
    # needs: durata and shadow uses (reads by transforms/emit were checked above)
    for x in g.states.values():
        for n in g.base_needs(x, recovery=True):
            if n.kind not in ("durata", "shadow"):
                continue
            res, dur = snap[n.slot]
            region = next((r for r in g.regions if r.name == n.src), None)
            if n.kind == "shadow" and region is not None and region.policy == "restore":
                if x.name not in dur:
                    V["I3"].append(f"region '{region.name}' (restore): no durable copy of frontier '{x.name}' by commit slot {n.slot}")
            elif x.name not in res:
                how = f" ({removed[x.name][0].lower()}d at step {removed[x.name][1]})" if x.name in removed else ""
                tgt = "I3" if n.kind == "shadow" else "I2"
                what = f"recovery of region '{n.src}'" if n.kind == "shadow" else f"durata ({n.src})"
                V[tgt].append(f"'{x.name}' is needed at slot {n.slot} for {what} but is not resident{how}: "
                              f"premature release")
    # completeness -----------------------------------------------------------
    want = [t.output for t in g.transforms]
    if execs != want:
        V["P1"].append(f"transforms executed as {execs}, expected {want}")
    if sorted(emits) != sorted(s.name for s in g.outputs()):
        V["P1"].append(f"emitted {sorted(emits)}, expected {sorted(s.name for s in g.outputs())}")
    # clean exit ----------------------------------------------------------------
    for name in sorted(resident):
        s = g.states[name]
        if not (s.is_output or s.persistent):
            V["I6"].append(f"clean exit violated: temporary '{name}' is still resident at the end (leak)")
    # constraints -----------------------------------------------------------------
    rep = simulate(g, plan, cfg)
    vals = dict(rep.cost.as_dict(), peak_storage=float(rep.peak_storage))
    for c in g.constraints:
        if not c.holds(vals[c.dim]):
            V["C"].append(f"constraint '{c}' violated (actual {vals[c.dim]:.4g})")
    cap = g.machine.components["primary"].capacity if g.machine.has("primary") else None
    if cap is not None and rep.peak_storage > cap:
        V["C"].append(f"primary capacity {cap:g} exceeded (peak {rep.peak_storage})")
    return VerificationReport(V)
