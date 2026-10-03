"""AST node types for the prototype DSL (produced by parser.py)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class Loc:
    line: int
    col: int


@dataclass
class Value:
    """A property value: identifier, call `f(a, b)`, number, or list `[a, b]`."""
    kind: str  # 'ident' | 'call' | 'number' | 'list'
    loc: Loc
    name: Optional[str] = None
    args: List["Value"] = field(default_factory=list)
    number: Optional[float] = None


@dataclass
class Prop:
    key: str
    value: Value
    loc: Loc


@dataclass
class StatoDecl:
    name: str
    type_name: str
    props: List[Prop]
    loc: Loc
    type_loc: Loc


@dataclass
class TrasformaDecl:
    op: str
    inputs: List[Tuple[str, Loc]]
    output: Tuple[str, Loc]
    props: List[Prop]
    loc: Loc


@dataclass
class ComponenteDecl:
    name: str
    props: List[Prop]
    loc: Loc


@dataclass
class FlussoDecl:
    src: Tuple[str, Loc]
    dst: Tuple[str, Loc]
    loc: Loc


@dataclass
class RecuperoDecl:
    name: str
    props: List[Prop]
    loc: Loc


@dataclass
class VincoloDecl:
    dim: str
    cmp: str
    value: float
    loc: Loc


@dataclass
class EmitDecl:
    names: List[Tuple[str, Loc]]
    loc: Loc


@dataclass
class SystemAst:
    name: str
    items: list
    file: str = "<input>"
