"""Operation library for the prototype DSL.

Every `trasforma` names an operation from this registry.  Each operation fixes
its semantics (for the reference interpreter), result-type rule, abstract cost
weight, intrinsic irreversibility boundary and regeneration grade.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Sequence

from .types import EXACT, HARD, NO_BOUNDARY, TYPE_BITS, Boundary, Grade


def mask(bits: int) -> int:
    return (1 << bits) - 1


def _same(types: Sequence[str]) -> str:
    if len(set(types)) != 1:
        raise ValueError(f"operand types differ: {', '.join(types)}")
    return types[0]


def _to_bit(types: Sequence[str]) -> str:
    return "bit"


def _wide(types: Sequence[str]) -> str:
    t = _same(types)
    if TYPE_BITS[t] < 2:
        raise ValueError("needs an operand of at least 2 bits")
    return t


@dataclass(frozen=True)
class Op:
    name: str
    arity: int
    fn: Callable[[Sequence[int], int], int]  # (args, out_bits) -> value
    result_type: Callable[[Sequence[str]], str]
    weight: float  # abstract relative cost per bit
    boundary: Boundary = NO_BOUNDARY
    regen: Grade = EXACT
    doc: str = ""


def _mk(*ops: Op) -> Dict[str, Op]:
    return {o.name: o for o in ops}


OPS: Dict[str, Op] = _mk(
    Op("copy", 1, lambda a, w: a[0], _same, 0.5, doc="y = x (bijective)"),
    Op("not", 1, lambda a, w: ~a[0] & mask(w), _same, 0.5, doc="y = ~x (bijective)"),
    Op("inc", 1, lambda a, w: (a[0] + 1) & mask(w), _same, 1.5, doc="y = x + 1 mod 2^w (bijective)"),
    Op("xor", 2, lambda a, w: a[0] ^ a[1], _same, 1.0, doc="y = a ^ b (many-to-one on (a,b); out-of-place reversible)"),
    Op("and", 2, lambda a, w: a[0] & a[1], _same, 1.0, doc="y = a & b"),
    Op("or", 2, lambda a, w: a[0] | a[1], _same, 1.0, doc="y = a | b"),
    Op("add", 2, lambda a, w: (a[0] + a[1]) & mask(w), _same, 2.0, doc="y = a + b mod 2^w"),
    Op("sub", 2, lambda a, w: (a[0] - a[1]) & mask(w), _same, 2.0, doc="y = a - b mod 2^w"),
    Op(
        "quantize", 1,
        lambda a, w: (a[0] >> (w // 2)) << (w // 2), _wide, 1.0,
        boundary=HARD, doc="drop the low half of the bits: HARD irreversibility boundary",
    ),
    Op(
        "parity", 1,
        lambda a, w: bin(a[0]).count("1") & 1, _to_bit, 1.5,
        boundary=HARD, doc="y = parity(x): many-to-one, HARD irreversibility boundary",
    ),
)
