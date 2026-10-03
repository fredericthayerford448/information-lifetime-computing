"""Command-line interface: check | inspect | plan | simulate | run | profiles."""
from __future__ import annotations

import argparse
import sys
from typing import Dict, List, Optional

from . import RELEASE_NAME, __version__
from .costs import PROFILES, CostConfig, load_config
from .diagnostics import Diagnostic, ILCError
from .fates import Ablation
from .interpreter import default_inputs
from .ir import render_graph, render_lifetimes, render_regions
from .pipeline import PipelineResult, analyze_source, run_pipeline
from .types import ALL_FATES

ABLATIONS = {"boundary-typing": "boundary_typing", "recovery-coupling": "recovery_coupling", "uncompute": "allow_uncompute"}
DISCLAIMER = "(abstract model units - not physical measurements)"


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _fmt(x: Optional[float]) -> str:
    return "-" if x is None else f"{x:.2f}"


def _section(title: str) -> str:
    return f"\n{title}"


def _parse_inputs(text: Optional[str]) -> Optional[Dict[str, int]]:
    if not text:
        return None
    out: Dict[str, int] = {}
    for part in text.split(","):
        k, _, v = part.partition("=")
        if not v.strip().lstrip("-").isdigit():
            raise ILCError(Diagnostic("E-USAGE", f"invalid --inputs entry '{part}'; expected name=integer"))
        out[k.strip()] = int(v)
    return out


def _fate_block(res: PipelineResult) -> List[str]:
    g, plan = res.graph, res.plan
    lines: List[str] = []
    for x in g.reverse_topo()[::-1]:
        nd = plan.needs[x.name]
        death = max([x.birth] + [n.slot for n in nd])
        rep = plan.reports[x.name]
        chosen = plan.fates[x.name]
        lines.append(f"  {x.name} : {x.type_name}   birth {x.birth}, effective death {death}"
                     + ("   [pinned destino=" + x.declared_destino.value + "]" if x.declared_destino else ""))
        for a in rep.assessments:
            mark = "*" if a.fate is chosen else " "
            lines.append(f"   {mark} {a.fate.value:<10} {'yes' if a.legal else 'no ':<3} {_fmt(rep.alternatives[a.fate]):>8}  {a.reason}")
        others = sorted((o, f) for f, o in rep.alternatives.items() if o is not None and f is not chosen)
        gap = f"; next best: {others[0][1].value} ({others[0][0]:.2f}, +{others[0][0] - plan.objective:.2f})" if others else "; only legal choice"
        lines.append(f"     selected: {chosen.value}{gap}")
    return lines


def render_plan(res: PipelineResult, cfg: CostConfig) -> str:
    g, plan, ver = res.graph, res.plan, res.verification
    out = [f"Program valid: {g.name} ({g.n_steps} transforms, {len(g.states)} states, {len(g.regions)} recovery region(s))"]
    out.append(_section("Information graph:"))
    out.append(render_graph(g))
    out.append(_section("Lifetime (slot 0 = inputs loaded, 1..N = transforms, N+1 = emit; death includes shadow uses):"))
    out.append(render_lifetimes(g, plan.ablation.recovery_coupling))
    out.append(_section(f"Fate analysis  (profile: {cfg.name}; 'yes/no' = legal; number = whole-plan objective if this state used that fate):"))
    out += _fate_block(res)
    kind = "optimal under the abstract model" if plan.optimal else "NOT guaranteed optimal"
    out.append(_section(f"Selected fates  (planner: {plan.planner}, {kind}; {plan.nodes} search nodes):"))
    for x in g.states.values():
        out.append(f"  {x.name:<10} -> {plan.fates[x.name].value}")
    for n in plan.notes:
        out.append(f"  note: {n}")
    out.append(_section("Execution plan:"))
    out.append(plan.execution.render())
    c = res.simulation.cost
    out.append(_section(f"Cost {DISCLAIMER}:"))
    out.append(f"  energy={c.energy:.2f}  storage={c.storage:.2f}  latency={c.latency:.2f}  recovery={c.recovery:.2f}"
               f"   weighted objective={res.simulation.objective:.2f}")
    out.append(_section("Verification checks (foundation invariants, independent verifier):"))
    out.append(ver.format())
    ex = res.execution
    if ex.ok:
        out.append("  reference interpreter: PASS (outputs match the fate-free reference semantics)")
    else:
        out.append("  reference interpreter: FAIL")
        out += [f"        - {e}" for e in ex.errors]
    out.append(_section("Verification: " + ("PASS" if ver.ok and ex.ok else "FAIL")))
    return "\n".join(out)


def render_sim(res: PipelineResult, cfg: CostConfig) -> str:
    s = res.simulation
    lines = [f"Abstract simulation of '{res.graph.name}'  {DISCLAIMER}", f"  profile: {cfg.name}", "",
             f"  execution steps       {s.steps}", f"  peak storage (bits)   {s.peak_storage}",
             f"  peak temporary (bits) {s.peak_temporary}", f"  estimated energy      {s.cost.energy:.2f}",
             f"  estimated storage     {s.cost.storage:.2f}   (tier-weighted bit-slots)",
             f"  estimated latency     {s.cost.latency:.2f}", f"  expected recovery     {s.cost.recovery:.2f}",
             f"  weighted objective    {s.objective:.2f}", f"  recomputations        {s.counts['recomputations']}",
             f"  checkpoints           {s.counts['checkpoints']}  (restores {s.counts['restores']})",
             f"  uncomputes            {s.counts['uncomputes']}", f"  erasures              {s.counts['erasures']}"
             f"  (releases {s.counts['releases']})", f"  moves                 {s.counts['moves_out']}",
             "", "  primary occupancy per slot (bits): " + " ".join(str(v) for v in s.occupancy[:g_end(res)])]
    return "\n".join(lines)


def g_end(res: PipelineResult) -> int:
    return res.graph.emit_slot + 1


def render_run(res: PipelineResult) -> str:
    ex = res.execution
    lines = ["Reference interpreter trace:"] + ex.trace
    lines.append("")
    for n, v in ex.outputs.items():
        lines.append(f"output {n} = {v}   (reference {ex.reference[n]})")
    lines += [f"note: {n}" for n in ex.notes]
    lines += [f"ERROR: {e}" for e in ex.errors]
    lines.append(f"recoveries performed: {ex.recoveries}")
    lines.append("Result: " + ("PASS" if ex.ok else "FAIL"))
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("file", help="source file (.lang)")
    common.add_argument("--profile", default="abstract-default", help=f"cost profile ({', '.join(PROFILES)})")
    common.add_argument("--cost-config", metavar="JSON", help="JSON file overriding cost coefficients")
    common.add_argument("--planner", default="exhaustive", choices=["exhaustive", "greedy", "conventional"])
    common.add_argument("--ablate", action="append", default=[], choices=list(ABLATIONS),
                        help="disable part of the model (falsification experiments); repeatable")
    common.add_argument("--budget", type=int, default=200_000, help="exhaustive-search node budget")
    common.add_argument("--seed", type=int, default=0)
    common.add_argument("--inputs", metavar="a=1,b=0", help="concrete input values for the interpreter")
    common.add_argument("--inject-fault", metavar="REGION", help="inject a fault into a recupero region at its commit point")
    p = argparse.ArgumentParser(
        prog="ilc",
        description=f"{RELEASE_NAME} v{__version__}: a research prototype of the information-lifetime fate calculus "
                    f"(digital-only; all costs are abstract model units).",
        epilog="Typical session: ilc check F.lang && ilc inspect F.lang && ilc plan F.lang && ilc run F.lang --inject-fault guard")
    p.add_argument("--version", action="version", version=f"ilc {__version__} ({RELEASE_NAME})")
    sub = p.add_subparsers(dest="command", required=True, metavar="command")
    sub.add_parser("check", parents=[common], help="parse and semantically validate a program")
    sub.add_parser("inspect", parents=[common], help="dump the information graph, lifetimes and recovery regions")
    sub.add_parser("plan", parents=[common], help="analyse legal fates, select a plan, verify it")
    sub.add_parser("simulate", parents=[common], help="plan, then report abstract simulator metrics")
    sub.add_parser("run", parents=[common], help="plan, then execute the plan on the reference interpreter")
    sub.add_parser("profiles", help="list cost profiles and what they model")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "profiles":
        for n, c in PROFILES.items():
            print(f"{n:<18} {c.description}")
        return 0
    try:
        try:
            source = _read(args.file)
        except OSError as e:
            print(f"error: cannot read '{args.file}': {e.strerror}", file=sys.stderr)
            return 2
        cfg = load_config(args.profile, args.cost_config)
        if args.command in ("check", "inspect"):
            res = analyze_source(source, args.file, cfg)
            for d in res.diagnostics:
                print(d.format(), file=sys.stderr)
            if not res.ok:
                return 1
            g = res.graph
            if args.command == "check":
                print(f"OK: '{g.name}': {len(g.states)} states, {g.n_steps} transforms, "
                      f"{len(g.regions)} recovery region(s), {len(g.constraints)} constraint(s)")
                return 0
            print(f"System {g.name}")
            print("\nInformation graph:\n" + render_graph(g))
            print("\nLifetimes (base program; recovery shadow uses included):\n" + render_lifetimes(g))
            print("\nRecovery regions:\n" + render_regions(g))
            print("\nConstraints: " + (", ".join(str(c) for c in g.constraints) or "(none)"))
            m = g.machine
            print("Machine: " + ("explicit " if m.explicit else "implicit ") + ", ".join(
                f"{r}={c.name}" + (f"(cap {c.capacity:g})" if c.capacity else "") for r, c in m.components.items()))
            return 0
        abl = Ablation(**{ABLATIONS[a]: False for a in args.ablate})
        res = run_pipeline(source, args.file, cfg, args.planner, abl, args.seed, _parse_inputs(args.inputs),
                           args.inject_fault, args.budget)
        print({"plan": render_plan, "simulate": lambda r, c: render_sim(r, c), "run": lambda r, c: render_run(r)}
              [args.command](res, cfg))
        return 0 if (res.verification.ok and res.execution.ok) else 1
    except ILCError as e:
        for d in e.diagnostics:
            print(d.format(), file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
