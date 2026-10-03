import pytest

from conftest import NEGATIVE
from ilc.pipeline import analyze_source, compile_source
from ilc.diagnostics import ILCError
from helpers import graph


def codes(src):
    return [d.code for d in analyze_source(src, "t.lang").diagnostics]


NEG_FILES = sorted(NEGATIVE.glob("*.lang"))


@pytest.mark.parametrize("path", NEG_FILES, ids=[p.stem for p in NEG_FILES])
def test_negative_programs_fail_for_the_documented_reason(path):
    text = path.read_text()
    expect = text.splitlines()[0].replace("// expect:", "").strip()
    res = analyze_source(text, path.name)
    assert not res.ok
    assert expect in [d.code for d in res.diagnostics], [d.format() for d in res.diagnostics]
    assert all(d.file == path.name for d in res.diagnostics)


def test_there_are_enough_negative_cases():
    assert len(NEG_FILES) >= 20


def test_undefined_symbol_has_location():
    res = analyze_source("system S {\n stato a : bit\n trasforma xor(a, ghost) -> y\n}", "u.lang")
    d = res.diagnostics[0]
    assert d.code == "E-UNDEF" and "ghost" in d.message and d.line == 3


def test_illegal_dependency_message_names_both_steps():
    d = analyze_source("system S { stato a : bit\n trasforma copy(late) -> early\n trasforma copy(a) -> late }").diagnostics[0]
    assert d.code == "E-DEP" and "step 1" in d.message and "step 2" in d.message


def test_self_dependency_is_a_cycle():
    assert "E-DEP" in codes("system S { stato a : bit trasforma xor(a, y) -> y }")


def test_implicit_output_type_is_inferred():
    g = graph("system S { stato a : u8 stato b : u8 trasforma add(a, b) -> s trasforma parity(s) -> p }")
    assert g.states["s"].type_name == "u8" and g.states["p"].type_name == "bit"


def test_valid_until_and_steps_set_durata_end():
    g = graph("""system S { stato a : bit
        stato t : bit { durata = until(u) }
        stato k : bit { durata = steps(1) }
        trasforma copy(a) -> t trasforma copy(t) -> u trasforma copy(a) -> k emit u }""")
    assert g.states["t"].durata_end == 2 and g.states["k"].durata_end == 4


def test_emit_of_undefined_state():
    assert "E-UNDEF" in codes("system S { stato a : bit emit nope }")


def test_machine_validation():
    assert "E-COMPONENT" in codes("system S { componente x }")
    assert "E-UNDEF" in codes("system S { componente p { role = primary } flusso p -> ghost }")
    assert "E-DUP" in codes("system S { componente p { role = primary } componente q { role = primary } }")


def test_region_validation():
    base = "system S { stato a : u8 trasforma inc(a) -> s trasforma inc(s) -> r "
    assert "E-RECOVERY" in codes(base + "recupero g { region = [s, r] commit = a } }")
    assert "E-RECOVERY" in codes(base + "recupero g { region = [s] policy = teleport } }")
    assert "E-DUP" in codes(base + "recupero g { region = [s] } recupero g { region = [r] } }")
    ok = analyze_source(base + "recupero g { region = [s, r] } }")
    assert ok.ok and ok.graph.regions[0].commit == "r"


def test_multiple_errors_are_collected():
    cs = codes("system S { stato a : u9 stato a : bit trasforma nope(a) -> y }")
    assert {"E-TYPE", "E-DUP", "E-OP"} <= set(cs)


def test_compile_source_raises_with_all_diagnostics():
    with pytest.raises(ILCError) as e:
        compile_source("system S { stato a : u9 }", "x.lang")
    assert e.value.diagnostics[0].code == "E-TYPE"
