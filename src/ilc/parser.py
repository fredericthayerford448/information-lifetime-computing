"""Recursive-descent parser: tokens -> AST.  Stops at the first syntax error
and reports it as a Diagnostic (file, line, column, code, message)."""
from __future__ import annotations

from typing import List, NoReturn, Tuple

from .diagnostics import Diagnostic, ILCError
from .lexer import Token, tokenize
from .syntax import (ComponenteDecl, EmitDecl, FlussoDecl, Loc, Prop, RecuperoDecl,
                     StatoDecl, SystemAst, TrasformaDecl, Value, VincoloDecl)

KEYWORDS = ("stato", "trasforma", "componente", "flusso", "recupero", "vincolo", "emit")


class Parser:
    def __init__(self, toks: List[Token], file: str):
        self.toks, self.pos, self.file = toks, 0, file

    # -- helpers -----------------------------------------------------------
    def peek(self) -> Token:
        return self.toks[self.pos]

    def advance(self) -> Token:
        t = self.toks[self.pos]
        if t.kind != "EOF":
            self.pos += 1
        return t

    def fail(self, msg: str, tok: Token = None, code: str = "E-SYNTAX") -> NoReturn:
        t = tok or self.peek()
        raise ILCError(Diagnostic(code, msg, self.file, t.line, t.col))

    @staticmethod
    def describe(t: Token) -> str:
        return "end of input" if t.kind == "EOF" else f"'{t.text}'"

    def is_sym(self, s: str) -> bool:
        t = self.peek()
        return t.kind == "SYM" and t.text == s

    def accept_sym(self, s: str) -> bool:
        if self.is_sym(s):
            self.advance()
            return True
        return False

    def expect_sym(self, s: str, ctx: str = "") -> Token:
        if not self.is_sym(s):
            self.fail(f"expected '{s}'{(' ' + ctx) if ctx else ''}, found {self.describe(self.peek())}")
        return self.advance()

    def expect_ident(self, what: str) -> Token:
        t = self.peek()
        if t.kind != "IDENT":
            self.fail(f"expected {what}, found {self.describe(t)}")
        return self.advance()

    def loc(self, t: Token) -> Loc:
        return Loc(t.line, t.col)

    # -- grammar -----------------------------------------------------------
    def parse_system(self) -> SystemAst:
        t = self.peek()
        if not (t.kind == "IDENT" and t.text == "system"):
            self.fail(f"expected 'system', found {self.describe(t)}")
        self.advance()
        name = self.expect_ident("a system name").text
        self.expect_sym("{", "after the system name")
        items = []
        while not self.is_sym("}"):
            if self.peek().kind == "EOF":
                self.fail("unexpected end of input: missing '}' to close the system")
            items.append(self.parse_item())
        self.advance()
        if self.peek().kind != "EOF":
            self.fail(f"unexpected {self.describe(self.peek())} after the end of the system")
        return SystemAst(name, items, self.file)

    def parse_item(self):
        t = self.peek()
        if t.kind != "IDENT":
            self.fail(f"expected a declaration ({', '.join(KEYWORDS)}), found {self.describe(t)}")
        if t.text not in KEYWORDS:
            self.fail(f"unknown declaration '{t.text}'; expected one of: {', '.join(KEYWORDS)}")
        self.advance()
        return getattr(self, "p_" + t.text)(t)

    def p_stato(self, kw: Token) -> StatoDecl:
        name = self.expect_ident("a state name")
        self.expect_sym(":", f"after state name '{name.text}'")
        ty = self.expect_ident("a type (bit, u8, u16, u32)")
        return StatoDecl(name.text, ty.text, self.parse_props(), self.loc(name), self.loc(ty))

    def p_trasforma(self, kw: Token) -> TrasformaDecl:
        op = self.expect_ident("an operation name")
        self.expect_sym("(", f"after operation '{op.text}'")
        inputs: List[Tuple[str, Loc]] = []
        if not self.is_sym(")"):
            while True:
                t = self.expect_ident("an input state name")
                inputs.append((t.text, self.loc(t)))
                if not self.accept_sym(","):
                    break
        self.expect_sym(")", "to close the input list")
        self.expect_sym("->", "before the output state")
        out = self.expect_ident("an output state name")
        return TrasformaDecl(op.text, inputs, (out.text, self.loc(out)), self.parse_props(), self.loc(op))

    def p_componente(self, kw: Token) -> ComponenteDecl:
        name = self.expect_ident("a component name")
        return ComponenteDecl(name.text, self.parse_props(), self.loc(name))

    def p_flusso(self, kw: Token) -> FlussoDecl:
        a = self.expect_ident("a source component")
        self.expect_sym("->", "in a flusso declaration")
        b = self.expect_ident("a destination component")
        return FlussoDecl((a.text, self.loc(a)), (b.text, self.loc(b)), self.loc(kw))

    def p_recupero(self, kw: Token) -> RecuperoDecl:
        name = self.expect_ident("a recovery region name")
        if not self.is_sym("{"):
            self.fail(f"expected '{{' to open the properties of recupero '{name.text}', found {self.describe(self.peek())}")
        return RecuperoDecl(name.text, self.parse_props(), self.loc(name))

    def p_vincolo(self, kw: Token) -> VincoloDecl:
        dim = self.expect_ident("a constraint dimension (energy, latency, ...)")
        t = self.peek()
        if not (t.kind == "SYM" and t.text in ("<", "<=", ">", ">=")):
            self.fail(f"expected a comparison (<, <=, >, >=), found {self.describe(t)}")
        self.advance()
        n = self.peek()
        if n.kind != "NUMBER":
            self.fail(f"expected a number, found {self.describe(n)}")
        self.advance()
        return VincoloDecl(dim.text, t.text, float(n.text), self.loc(kw))

    def p_emit(self, kw: Token) -> EmitDecl:
        names = []
        while True:
            t = self.expect_ident("a state name to emit")
            names.append((t.text, self.loc(t)))
            if not self.accept_sym(","):
                break
        return EmitDecl(names, self.loc(kw))

    def parse_props(self) -> List[Prop]:
        props: List[Prop] = []
        if not self.accept_sym("{"):
            return props
        while not self.is_sym("}"):
            if self.peek().kind == "EOF":
                self.fail("unexpected end of input: missing '}' in property block")
            k = self.expect_ident("a property name")
            self.expect_sym("=", f"after property '{k.text}'")
            props.append(Prop(k.text, self.parse_value(), self.loc(k)))
            if not (self.accept_sym(",") or self.accept_sym(";")):
                pass
        self.advance()
        return props

    def parse_value(self) -> Value:
        t = self.peek()
        if t.kind == "NUMBER":
            self.advance()
            return Value("number", self.loc(t), number=float(t.text))
        if t.kind == "IDENT":
            self.advance()
            if self.accept_sym("("):
                args: List[Value] = []
                if not self.is_sym(")"):
                    while True:
                        args.append(self.parse_value())
                        if not self.accept_sym(","):
                            break
                self.expect_sym(")", f"to close '{t.text}(...)'")
                return Value("call", self.loc(t), name=t.text, args=args)
            return Value("ident", self.loc(t), name=t.text)
        if self.accept_sym("["):
            items: List[Value] = []
            if not self.is_sym("]"):
                while True:
                    items.append(self.parse_value())
                    if not self.accept_sym(","):
                        break
            self.expect_sym("]", "to close the list")
            return Value("list", self.loc(t), args=items)
        self.fail(f"expected a value, found {self.describe(t)}")


def parse(source: str, file: str = "<input>") -> SystemAst:
    return Parser(tokenize(source, file), file).parse_system()
