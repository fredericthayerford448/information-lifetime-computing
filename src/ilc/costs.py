"""Abstract cost model (docs/cost-model.md).

ALL NUMBERS ARE ABSTRACT MODEL UNITS.  They are not measurements of any
hardware.  Profiles exist to expose *regimes* (which fate wins when), not to
claim any regime is realistic.  See OPEN_QUESTIONS.md (OQ-9).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, fields, replace
from typing import Dict, List, Optional, Tuple

from .ir import InfoGraph, Region, StateNode
from .types import Grade

Window = Tuple[str, int, int]  # (tier, first_slot, last_slot) inclusive


@dataclass(frozen=True)
class CostVector:
    energy: float = 0.0
    storage: float = 0.0
    latency: float = 0.0
    recovery: float = 0.0

    def __add__(self, o: "CostVector") -> "CostVector":
        return CostVector(self.energy + o.energy, self.storage + o.storage,
                          self.latency + o.latency, self.recovery + o.recovery)

    def scale(self, k: float) -> "CostVector":
        return CostVector(self.energy * k, self.storage * k, self.latency * k, self.recovery * k)

    def as_dict(self) -> Dict[str, float]:
        return {"energy": self.energy, "storage": self.storage,
                "latency": self.latency, "recovery": self.recovery}

    def close_to(self, o: "CostVector", tol: float = 1e-9) -> bool:
        return all(abs(a - b) <= tol for a, b in zip(self.as_dict().values(), o.as_dict().values()))


@dataclass(frozen=True)
class CostConfig:
    name: str = "abstract-default"
    description: str = ("ABSTRACT units. Irreversible reset costs 3x a unit operation: a regime where "
                        "reversible clean-up can win (hypothesis T4). Not a measurement.")
    # dynamic energy (per bit unless noted)
    e_exec: float = 1.0          # x op.weight x bits
    e_reset: float = 3.0         # clean-up of a released primary cell (erase / release)
    e_xfer: float = 0.5          # one-way primary<->bulk transfer
    e_ckpt: float = 1.0          # durable write
    e_restore: float = 1.0       # durable read-back
    uncompute_factor: float = 1.0  # energy/latency of inverse relative to forward
    # latency (abstract steps)
    l_exec: float = 1.0          # x op.weight
    l_reset: float = 0.5
    l_xfer: float = 1.0
    l_ckpt: float = 2.0
    l_restore: float = 2.0
    # storage: tier-weighted bit-slots
    w_primary: float = 1.0
    w_bulk: float = 0.25
    w_durable: float = 0.1
    # reliability exposure
    fault_prob_slot: float = 0.01        # per state per volatile slot without a durable copy
    unrecoverable_penalty_bit: float = 5.0  # loss cost per bit of a non-regenerable state
    region_fault_prob: float = 0.05      # per recovery region
    # objective weights
    weight_energy: float = 1.0
    weight_storage: float = 0.5
    weight_latency: float = 0.5
    weight_recovery: float = 1.0
    # structural parameters
    horizon: int = 3             # extra slots a never-released value occupies after emit
    eps_clean: float = 0.05      # max SOFT residual (eta) tolerated by uncompute

    def with_overrides(self, **kw) -> "CostConfig":
        return replace(self, **kw)

    def as_dict(self) -> Dict[str, object]:
        return {f.name: getattr(self, f.name) for f in fields(self)}


_BASE = CostConfig()
PROFILES: Dict[str, CostConfig] = {
    "abstract-default": _BASE,
    "cmos-like": replace(_BASE, name="cmos-like", e_reset=0.3, l_reset=0.2,
                         description="ABSTRACT: cheap reset (erase is nearly free relative to compute)."),
    "storage-scarce": replace(_BASE, name="storage-scarce", e_reset=0.3, l_reset=0.2, w_primary=6.0,
                              description="ABSTRACT: cheap reset, very scarce primary storage."),
    "fragile": replace(_BASE, name="fragile", fault_prob_slot=0.25, region_fault_prob=0.2,
                       description="ABSTRACT: high fault rate; unrecoverable loss is expensive."),
    "reversible-hw": replace(_BASE, name="reversible-hw", e_reset=8.0, e_exec=0.5,
                             description="ABSTRACT: erase is very expensive, forward/inverse ops cheap."),
}


def load_config(profile: Optional[str] = None, path: Optional[str] = None) -> CostConfig:
    """Resolve a profile name and/or a JSON file of overrides into a CostConfig."""
    cfg = PROFILES.get(profile or "abstract-default")
    if cfg is None:
        raise ValueError(f"unknown profile '{profile}'; available: {', '.join(PROFILES)}")
    if path:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        valid = {f.name for f in fields(CostConfig)}
        bad = sorted(set(data) - valid)
        if bad:
            raise ValueError(f"unknown cost-config keys: {', '.join(bad)}")
        cfg = replace(cfg, **data)
    return cfg


# -- elementary costs --------------------------------------------------------
def exec_energy(weight: float, bits: int, cfg: CostConfig) -> float:
    return cfg.e_exec * weight * bits


def exec_latency(weight: float, cfg: CostConfig) -> float:
    return cfg.l_exec * weight


def action_cost(kind: str, weight: float, bits: int, cfg: CostConfig) -> Tuple[float, float]:
    """(energy, latency) of one plan action."""
    if kind in ("EXEC", "REGENERATE"):
        return exec_energy(weight, bits, cfg), exec_latency(weight, cfg)
    if kind == "UNCOMPUTE":
        return (cfg.uncompute_factor * exec_energy(weight, bits, cfg),
                cfg.uncompute_factor * exec_latency(weight, cfg))
    if kind in ("ERASE", "RELEASE"):
        return cfg.e_reset * bits, cfg.l_reset
    if kind in ("MOVE_OUT", "MOVE_IN"):
        return cfg.e_xfer * bits, cfg.l_xfer
    if kind == "CHECKPOINT_WRITE":
        return cfg.e_ckpt * bits, cfg.l_ckpt
    if kind == "RESTORE":
        return cfg.e_restore * bits, cfg.l_restore
    return 0.0, 0.0  # EMIT


def tier_weight(tier: str, cfg: CostConfig) -> float:
    return {"primary": cfg.w_primary, "bulk": cfg.w_bulk, "durable": cfg.w_durable}[tier]


def storage_cost(windows: List[Window], bits: int, cfg: CostConfig) -> float:
    return sum(tier_weight(t, cfg) * bits * (e - s + 1) for t, s, e in windows)


def regen_loss_cost(g: InfoGraph, x: StateNode, cfg: CostConfig) -> float:
    """Cost of re-obtaining x after a fault when no durable copy exists."""
    p = g.producer(x.name)
    if p is not None and p.regen.rank >= 2:  # exact or tolerant: regenerable
        return exec_energy(p.op.weight, x.bits, cfg)
    return cfg.unrecoverable_penalty_bit * x.bits


def exposure_cost(g: InfoGraph, x: StateNode, windows: List[Window], durable_start: Optional[int],
                  cfg: CostConfig) -> float:
    """Expected fault loss: p x (volatile slots lacking a durable copy) x loss cost."""
    slots = 0
    for tier, s, e in windows:
        if tier == "durable":
            continue
        if durable_start is None:
            slots += e - s + 1
        else:
            slots += max(0, min(e, durable_start) - s + 1)
    return cfg.fault_prob_slot * slots * regen_loss_cost(g, x, cfg)


def region_recovery_cost(g: InfoGraph, r: Region, cfg: CostConfig) -> float:
    """Expected replay overhead of a recovery region (independent of fates)."""
    replay = sum(exec_energy(g.producer(m).op.weight, g.states[m].bits, cfg) for m in r.members)
    if r.policy == "restore":
        replay += sum(g.states[f].bits * cfg.e_restore for f in r.frontier)
    return cfg.region_fault_prob * replay


def objective(cv: CostVector, cfg: CostConfig) -> float:
    return (cfg.weight_energy * cv.energy + cfg.weight_storage * cv.storage
            + cfg.weight_latency * cv.latency + cfg.weight_recovery * cv.recovery)


def base_exec_cost(g: InfoGraph, cfg: CostConfig) -> CostVector:
    """Fate-independent cost: the first execution of every transform."""
    e = sum(exec_energy(t.op.weight, g.states[t.output].bits, cfg) for t in g.transforms)
    l = sum(exec_latency(t.op.weight, cfg) for t in g.transforms)
    rec = sum(region_recovery_cost(g, r, cfg) for r in g.regions)
    return CostVector(energy=e, latency=l, recovery=rec)
