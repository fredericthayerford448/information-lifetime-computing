import json
import subprocess
import sys

import pytest

from conftest import EXAMPLES, NEGATIVE
from ilc.cli import main


def run(capsys, *argv):
    code = main(list(argv))
    out = capsys.readouterr()
    return code, out.out, out.err


def test_check_success(capsys):
    code, out, err = run(capsys, "check", str(EXAMPLES / "basic.lang"))
    assert code == 0 and out.startswith("OK: 'Basic'") and err == ""


def test_check_failure_prints_located_diagnostic(capsys):
    code, out, err = run(capsys, "check", str(NEGATIVE / "undefined_state.lang"))
    assert code == 1 and "error[E-UNDEF]" in err and "undefined_state.lang:4:" in err and out == ""


def test_syntax_error_is_user_facing_not_a_traceback(capsys):
    code, out, err = run(capsys, "check", str(NEGATIVE / "syntax_missing_colon.lang"))
    assert code == 1 and "error[E-SYNTAX]" in err and "Traceback" not in err


def test_missing_file(capsys):
    code, out, err = run(capsys, "check", "no/such/file.lang")
    assert code == 2 and "cannot read" in err


def test_inspect_dumps_the_ir(capsys):
    code, out, err = run(capsys, "inspect", str(EXAMPLES / "recovery.lang"))
    assert code == 0
    for needle in ("Information graph", "[1] add", "Lifetimes", "shadow", "Recovery regions", "guard", "frontier=['a', 'b']"):
        assert needle in out


def test_plan_end_to_end_reversible(capsys):
    code, out, err = run(capsys, "plan", str(EXAMPLES / "reversible.lang"))
    assert code == 0
    for needle in ("Program valid", "Information graph", "──┐", "Lifetime", "Fate analysis", "retain", "uncompute",
                   "selected: uncompute", "Selected fates", "tmp        -> uncompute", "Execution plan",
                   "xor(a, b) -> tmp", "copy(tmp) -> result", "uncompute tmp: inverse(xor)", "abstract model units",
                   "Verification: PASS"):
        assert needle in out, needle


def test_plan_profile_flag_changes_the_decision(capsys):
    _, out, _ = run(capsys, "plan", str(EXAMPLES / "reversible.lang"), "--profile", "cmos-like")
    assert "tmp        -> erase" in out and "Verification: PASS" in out


def test_simulate_reports_metrics(capsys):
    code, out, _ = run(capsys, "simulate", str(EXAMPLES / "reversible.lang"))
    assert code == 0
    for needle in ("execution steps", "peak temporary", "estimated energy", "estimated storage", "estimated latency",
                   "recomputations", "checkpoints", "uncomputes", "erasures", "not physical measurements"):
        assert needle in out


def test_run_with_inputs_and_fault_injection(capsys):
    code, out, _ = run(capsys, "run", str(EXAMPLES / "recovery.lang"), "--inputs", "a=3,b=4", "--inject-fault", "guard")
    assert code == 0 and "output r = 8" in out and "recovered region 'guard'" in out and "Result: PASS" in out


def test_ablation_makes_run_fail_with_nonzero_exit(capsys):
    code, out, _ = run(capsys, "run", str(EXAMPLES / "recovery.lang"), "--inject-fault", "guard",
                       "--ablate", "recovery-coupling")
    assert code == 1 and "recovery of region 'guard' failed" in out and "Result: FAIL" in out


def test_ablation_is_flagged_in_plan_output_and_fails_verification(capsys):
    code, out, _ = run(capsys, "plan", str(EXAMPLES / "recovery.lang"), "--ablate", "recovery-coupling")
    assert code == 1 and "ABLATION ACTIVE" in out and "FAIL" in out and "I3" in out


def test_bad_inputs_flag_and_unknown_profile(capsys):
    code, _, err = run(capsys, "run", str(EXAMPLES / "basic.lang"), "--inputs", "a=banana")
    assert code == 1 and "E-USAGE" in err
    code, _, err = run(capsys, "plan", str(EXAMPLES / "basic.lang"), "--profile", "nope")
    assert code == 2 and "unknown profile" in err


def test_profiles_command(capsys):
    code, out, _ = run(capsys, "profiles")
    assert code == 0 and "abstract-default" in out and "cmos-like" in out


def test_help_and_version(capsys):
    with pytest.raises(SystemExit) as e:
        main(["--help"])
    assert e.value.code == 0
    out = capsys.readouterr().out
    for cmd in ("check", "inspect", "plan", "simulate", "run", "profiles"):
        assert cmd in out
    assert "abstract model units" in " ".join(out.split())
    with pytest.raises(SystemExit):
        main(["--version"])
    assert "0.1.0" in capsys.readouterr().out


def test_cost_config_file(capsys, tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"e_reset": 0.0, "l_reset": 0.0}))
    code, out, _ = run(capsys, "plan", str(EXAMPLES / "reversible.lang"), "--cost-config", str(p))
    assert code == 0 and "tmp        -> erase" in out


def test_module_entry_point_runs_as_subprocess():
    r = subprocess.run([sys.executable, "-m", "ilc", "check", str(EXAMPLES / "basic.lang")],
                       capture_output=True, text=True)
    assert r.returncode == 0 and r.stdout.startswith("OK")
