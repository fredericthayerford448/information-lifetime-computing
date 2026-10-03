import pytest

from ilc.diagnostics import ILCError
from ilc.lexer import tokenize
from ilc.parser import parse
from ilc.syntax import RecuperoDecl, StatoDecl, TrasformaDecl, VincoloDecl, EmitDecl


def test_valid_program_produces_ast():
    ast = parse("""system X {
        stato a : bit
        stato tmp : bit { durata = until(result)  destino = uncompute }
        trasforma xor(a, b) -> tmp   # comment
        recupero g { region = [tmp]  policy = replay }
        vincolo energy < 5
        emit tmp
    }""", "x.lang")
    kinds = [type(i) for i in ast.items]
    assert kinds == [StatoDecl, StatoDecl, TrasformaDecl, RecuperoDecl, VincoloDecl, EmitDecl]
    assert ast.name == "X" and ast.file == "x.lang"
    tmp = ast.items[1]
    assert [p.key for p in tmp.props] == ["durata", "destino"]
    assert tmp.props[0].value.kind == "call" and tmp.props[0].value.name == "until"


@pytest.mark.parametrize("src,msg", [
    ("system S { stato a bit }", "expected ':' after state name 'a'"),
    ("system S { stato a : bit", "missing '}'"),
    ("system S { trasforma xor(a b) -> y }", "to close the input list"),
    ("system S { trasforma xor(a, b) y }", "expected '->'"),
    ("system S { recupero g }", "expected '{'"),
    ("system S { vincolo energy 5 }", "expected a comparison"),
    ("system S { banana a }", "unknown declaration 'banana'"),
    ("stato a : bit", "expected 'system'"),
    ("system S { } extra", "after the end of the system"),
    ("system S { stato a : bit { durata } }", "expected '='"),
])
def test_invalid_syntax_gives_located_diagnostic(src, msg):
    with pytest.raises(ILCError) as e:
        parse(src, "bad.lang")
    d = e.value.diagnostics[0]
    assert d.code == "E-SYNTAX" and d.file == "bad.lang" and d.line >= 1 and d.col >= 1
    assert msg in d.message
    assert d.format().startswith("bad.lang:")


def test_lex_error_is_a_diagnostic_not_a_raw_exception():
    with pytest.raises(ILCError) as e:
        tokenize("system S { stato a : bit @ }", "f.lang")
    assert e.value.diagnostics[0].code == "E-LEX" and e.value.diagnostics[0].col == 26


def test_positions_are_tracked_across_lines():
    with pytest.raises(ILCError) as e:
        parse("system S {\n  stato a : bit\n  stato b bit\n}", "p.lang")
    d = e.value.diagnostics[0]
    assert (d.line, d.col) == (3, 11)


def test_properties_accept_commas_and_semicolons():
    ast = parse("system S { stato a : bit { durata = persistent, destino = retain; } }")
    assert [p.key for p in ast.items[0].props] == ["durata", "destino"]
