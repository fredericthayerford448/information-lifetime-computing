"""Core vocabulary: fates, regeneration grades, irreversibility boundaries, types.

Research definitions: docs/research-foundation-v0.1.md sections 6.1, 9, 10.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

TYPE_BITS = {"bit": 1, "u8": 8, "u16": 16, "u32": 32}


class Fate(str, Enum):
    RETAIN = "retain"
    MOVE = "move"
    CHECKPOINT = "checkpoint"
    RECOMPUTE = "recompute"
    UNCOMPUTE = "uncompute"
    ERASE = "erase"


ALL_FATES = list(Fate)
# Deterministic tie-break among equal-objective plans: simplest mechanism first.
FATE_PREFERENCE = [Fate.RETAIN, Fate.ERASE, Fate.MOVE, Fate.CHECKPOINT, Fate.RECOMPUTE, Fate.UNCOMPUTE]

_GRADE_RANK = {"exact": 3, "tolerant": 2, "distributional": 1, "source_bound": 0}


@dataclass(frozen=True)
class Grade:
    """Regeneration grade: EXACT > TOLERANT(eps) > DISTRIBUTIONAL > SOURCE_BOUND."""

    kind: str
    eps: Optional[float] = None

    @property
    def rank(self) -> int:
        return _GRADE_RANK[self.kind]

    def __str__(self) -> str:
        return f"tolerant({self.eps:g})" if self.kind == "tolerant" else self.kind


EXACT = Grade("exact")
DISTRIBUTIONAL = Grade("distributional")
SOURCE_BOUND = Grade("source_bound")


def tolerant(eps: float) -> Grade:
    return Grade("tolerant", float(eps))


def satisfies(provided: Grade, required: Grade) -> bool:
    """Does a regenerated value of grade `provided` meet acceptance grade `required`?"""
    if provided.rank != required.rank:
        return provided.rank > required.rank
    if provided.kind == "tolerant":
        return (provided.eps or 0.0) <= (required.eps or 0.0)
    return provided.kind != "source_bound"


_BND_RANK = {"none": 0, "soft": 1, "hard": 2}


@dataclass(frozen=True)
class Boundary:
    """Irreversibility grade of a transform: NONE < SOFT(eta) < HARD."""

    kind: str = "none"
    eta: float = 0.0

    @property
    def rank(self) -> int:
        return _BND_RANK[self.kind]

    def weaker_than(self, other: "Boundary") -> bool:
        """True if self claims *less* irreversibility than `other` (a dishonest weakening)."""
        if self.rank != other.rank:
            return self.rank < other.rank
        return self.kind == "soft" and self.eta < other.eta

    def __str__(self) -> str:
        return f"soft({self.eta:g})" if self.kind == "soft" else self.kind


NO_BOUNDARY = Boundary("none")
HARD = Boundary("hard")


def soft(eta: float) -> Boundary:
    return Boundary("soft", float(eta))
