"""Hand-written lexer for the prototype DSL."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .diagnostics import Diagnostic, ILCError


@dataclass(frozen=True)
class Token:
    kind: str  # IDENT | NUMBER | SYM | EOF
    text: str
    line: int
    col: int


_SYMS2 = {"->", "<=", ">="}
_SYMS1 = set("{}()[],:;=<>")


def tokenize(src: str, file: str = "<input>") -> List[Token]:
    toks: List[Token] = []
    i, line, col = 0, 1, 1
    n = len(src)

    def err(msg: str, l: int, c: int):
        raise ILCError(Diagnostic("E-LEX", msg, file, l, c))

    while i < n:
        ch = src[i]
        if ch == "\n":
            i, line, col = i + 1, line + 1, 1
        elif ch in " \t\r":
            i, col = i + 1, col + 1
        elif ch == "#" or src.startswith("//", i):
            while i < n and src[i] != "\n":
                i += 1
        elif ch.isalpha() or ch == "_":
            j = i
            while j < n and (src[j].isalnum() or src[j] == "_"):
                j += 1
            toks.append(Token("IDENT", src[i:j], line, col))
            col += j - i
            i = j
        elif ch.isdigit():
            j = i
            while j < n and src[j].isdigit():
                j += 1
            if j < n and src[j] == "." and j + 1 < n and src[j + 1].isdigit():
                j += 1
                while j < n and src[j].isdigit():
                    j += 1
            toks.append(Token("NUMBER", src[i:j], line, col))
            col += j - i
            i = j
        elif src[i:i + 2] in _SYMS2:
            toks.append(Token("SYM", src[i:i + 2], line, col))
            i, col = i + 2, col + 2
        elif ch in _SYMS1:
            toks.append(Token("SYM", ch, line, col))
            i, col = i + 1, col + 1
        else:
            err(f"unexpected character {ch!r}", line, col)
    toks.append(Token("EOF", "", line, col))
    return toks
