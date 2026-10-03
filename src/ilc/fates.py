"""Fate calculus engine: which fates are legal for a state, why, and what each
fate *does* (its schedule of actions and residency windows).

Research definitions: foundation sections 8-10 (release points, legality
preconditions, invariants I1-I7).  Every assessment carries a human-readable
reason so the planner is never a black box.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .costs import (CostConfig, CostVector, Window, action_cost, exposure_cost, storage_cost)
from .ir import InfoGraph, Need, Region, StateNode
from .types import ALL_FATES, EXACT, Fate, satisfies


@dataclass(frozen=True)
class Ablation:
    """Switches that disable one part of the model (for falsification experiments).
    With a switch off the engine becomes *unsound by design*; the verifier and
    interpreter are expected to catch the resulting violations."""
    boundary_typing: bool = True
    recovery_coupling: bool = True
    allow_uncompute: bool = True

    def names(self) -> List[str]:
        out = []
        if not self.boundary_typing:
            out.append("boundary-typing")
        if not self.recovery_coupling:
            out.append("recovery-coupling")
        if not self.allow_uncompute:
            out.append("uncompute")
        return out


@dataclass(frozen=True)
class Assessment:
    fate: Fate
    legal: bool
    reason: str
    gap_dependent: bool = False  # legality depends on idle gaps (not a static property)


@dataclass(frozen=True)
class Act:
    slot: int
    phase: str  # pre | exec | post
    kind: str   # CHECKPOINT_WRITE RELEASE RESTORE REGENERATE MOVE_OUT MOVE_IN UNCOMPUTE ERASE
    state: str


@dataclass
class Schedule:
    state: str
    fate: Fate
    acts: List[Act] = field(default_factory=list)
    windows: List[Window] = field(default_factory=list)
    pins: List[Tuple[str, Need]] = field(default_factory=list)  # (dependency, need) induced
    durable_start: Optional[int] = None


# -- need / gap analysis ---------------------------------------------------
def needs_for(g: InfoGraph, x: StateNode, pins: Dict[str, List[Need]], abl: Ablation) -> List[Need]:
    return g.base_needs(x, recovery=abl.recovery_coupling) + list(pins.get(x.name, []))


def anchors_of(x: StateNode, needs: List[Need]) -> List[int]:
    return [x.birth] + sorted({n.slot for n in needs if n.slot > x.birth})


def gaps_of(anchors: List[int]) -> List[Tuple[int, int]]:
    """Idle gaps: consecutive anchors with at least one interior slot."""
    return [(anchors[i - 1], anchors[i]) for i in range(1, len(anchors)) if anchors[i] - anchors[i - 1] >= 2]


def alive_at_end(g: InfoGraph, x: StateNode) -> bool:
    return x.persistent or x.is_output or any(n.slot == g.emit_slot for n in g.base_needs(x))


def restore_region(g: InfoGraph, x: StateNode, abl: Ablation) -> Optional[Region]:
    if not abl.recovery_coupling:
        return None
    for r in g.regions:
        if r.policy == "restore" and x.name in r.frontier:
            return r
    return None


# -- legality ---------------------------------------------------------------
def assess(g: InfoGraph, x: StateNode, fate: Fate, needs: List[Need], cfg: CostConfig,
           abl: Ablation = Ablation()) -> Assessment:
    anc = anchors_of(x, needs)
    death, gps = anc[-1], gaps_of(anc)
    prod = g.producer(x.name)
    m = g.machine

    def no(r: str, gap: bool = False) -> Assessment:
        return Assessment(fate, False, r, gap)

    def yes(r: str) -> Assessment:
        return Assessment(fate, True, r)

    if x.persistent and fate is not Fate.RETAIN:
        return no("persistent state must stay resident across invocations; only retain keeps it in place")
    rr = restore_region(g, x, abl)
    if rr is not None and fate is not Fate.CHECKPOINT:
        return no(f"recupero '{rr.name}' (policy=restore) requires a durable checkpoint of frontier state '{x.name}'")

    if fate is Fate.RETAIN:
        if alive_at_end(g, x):
            return yes(f"value stays resident to the end of the plan (needed until slot {death})")
        return no("dead temporary: retaining it leaks storage past its death (clean-exit rule, OQ-3); "
                  "dispose it with erase or uncompute")

    if fate is Fate.ERASE:
        why = f"no need after slot {death}: reset after slot {death}"
        if prod is not None and prod.regen.kind == "exact" and prod.boundary.kind == "none":
            why += " (x is a deterministic function of its dependencies: information-free in principle, but pays the reset cost)"
        return yes(why)

    if fate is Fate.UNCOMPUTE:
        if not abl.allow_uncompute:
            return no("uncompute disabled by ablation")
        if prod is None:
            return no(f"no producing transform: '{x.name}' is a source-bound input; there is no inverse to execute")
        if abl.boundary_typing:
            b = prod.boundary
            if b.kind == "hard":
                return no(f"producer '{prod.op.name}' is a HARD irreversibility boundary: no inverse over the "
                          f"reachable domain (foundation I5)")
            if b.kind == "soft" and b.eta > cfg.eps_clean:
                return no(f"producer '{prod.op.name}' is SOFT(eta={b.eta:g}); residual exceeds eps_clean="
                          f"{cfg.eps_clean:g}, uncompute would leave garbage (I6)")
            if prod.regen.kind != "exact":
                return no(f"re-executing '{prod.op.name}' is not exact (grade {prod.regen}); it cannot cancel '{x.name}'")
        return yes(f"{x.name} = {prod.op.name}({', '.join(prod.inputs)}) is deterministic and non-lossy "
                   f"(H(x|deps)=0); inverse = re-execution of {prod.op.name}; deps {prod.inputs} pinned live "
                   f"through slot {death}")

    if fate is Fate.RECOMPUTE:
        if prod is None:
            return no(f"required source information unavailable: '{x.name}' is a source-bound input and "
                      f"cannot be regenerated")
        if not gps:
            return no("no idle gap: needed in consecutive slots (or never again), so there is nothing to regenerate", True)
        if abl.boundary_typing and not satisfies(prod.regen, x.accept):
            return no(f"regeneration grade {prod.regen} of '{prod.op.name}' does not satisfy acceptance {x.accept}")
        return yes(f"regenerable at slot(s) {[b for _, b in gps]} from {prod.inputs} (pinned live there); "
                   f"grade {prod.regen}")

    if fate is Fate.CHECKPOINT:
        if not (m.has("durable") and m.flow("primary", "durable") and m.flow("durable", "primary")):
            return no("no durable component reachable by flusso in both directions")
        tail = (f"restored at slot(s) {[b for _, b in gps]}" if gps
                else "no idle gap: insurance only (primary stays resident)")
        return yes(f"durable copy written after slot {x.birth}; {tail}")

    if fate is Fate.MOVE:
        if not (m.has("bulk") and m.flow("primary", "bulk") and m.flow("bulk", "primary")):
            return no("no bulk component reachable by flusso in both directions")
        if not gps:
            return no("no idle gap: nothing to relocate across", True)
        return yes(f"relocated to bulk across gap(s) {gps}, fetched back before use")
    raise AssertionError(fate)


def static_illegal(g: InfoGraph, x: StateNode, fate: Fate, cfg: CostConfig,
                   abl: Ablation = Ablation()) -> Optional[Tuple[str, str]]:
    """Context-independent illegality of a *pinned* fate -> (code, reason) or None."""
    a = assess(g, x, fate, g.base_needs(x, recovery=abl.recovery_coupling), cfg, abl)
    if a.legal or a.gap_dependent:
        return None
    code = "E-RECOVERY-CONFLICT" if "recupero" in a.reason else "E-FATE-ILLEGAL"
    return code, a.reason


def candidate_fates(x: StateNode) -> List[Fate]:
    return [x.declared_destino] if x.declared_destino is not None else list(ALL_FATES)


# -- schedules ---------------------------------------------------------------
def build_schedule(g: InfoGraph, x: StateNode, fate: Fate, needs: List[Need], cfg: CostConfig) -> Schedule:
    """The actions and residency windows a fate implies for x, given its needs."""
    anc = anchors_of(x, needs)
    birth, death, gps = anc[0], anc[-1], gaps_of(anc)
    end = g.end_slot(cfg.horizon)
    prod = g.producer(x.name)
    s = Schedule(x.name, fate)
    if fate is Fate.RETAIN:
        s.windows = [("primary", birth, end)]
        return s
    if fate is Fate.ERASE:
        s.windows = [("primary", birth, death)]
        s.acts = [Act(death, "post", "ERASE", x.name)]
        return s
    if fate is Fate.UNCOMPUTE:
        s.windows = [("primary", birth, death)]
        s.acts = [Act(death, "post", "UNCOMPUTE", x.name)]
        s.pins = [(d, Need(death, "pin-uncompute", EXACT, x.name)) for d in prod.inputs]
        return s
    segs, start = [], birth
    for gs, ge in gps:
        segs.append((start, gs))
        start = ge
    segs.append((start, death))
    s.windows = [("primary", a, b) for a, b in segs]
    if fate is Fate.CHECKPOINT:
        s.acts.append(Act(birth, "post", "CHECKPOINT_WRITE", x.name))
        s.windows.append(("durable", birth, end))
        s.durable_start = birth
    for gs, ge in gps:
        if fate is Fate.RECOMPUTE:
            s.acts += [Act(gs, "post", "RELEASE", x.name), Act(ge, "pre", "REGENERATE", x.name)]
            s.pins += [(d, Need(ge, "pin-regen", EXACT, x.name)) for d in prod.inputs]
        elif fate is Fate.CHECKPOINT:
            s.acts += [Act(gs, "post", "RELEASE", x.name), Act(ge, "pre", "RESTORE", x.name)]
        elif fate is Fate.MOVE:
            s.acts += [Act(gs, "post", "MOVE_OUT", x.name), Act(ge, "pre", "MOVE_IN", x.name)]
            s.windows.append(("bulk", gs + 1, ge - 1))
    s.acts.append(Act(death, "post", "RELEASE", x.name))
    return s


def state_cost(g: InfoGraph, x: StateNode, s: Schedule, cfg: CostConfig) -> CostVector:
    prod = g.producer(x.name)
    w = prod.op.weight if prod else 0.0
    e = l = 0.0
    for a in s.acts:
        ae, al = action_cost(a.kind, w, x.bits, cfg)
        e, l = e + ae, l + al
    return CostVector(e, storage_cost(s.windows, x.bits, cfg), l,
                      exposure_cost(g, x, s.windows, s.durable_start, cfg))
