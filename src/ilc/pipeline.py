"""End-to-end pipeline: source -> parse -> check -> IR -> plan -> verify -> simulate -> interpret."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from .costs import CostConfig
from .diagnostics import Diagnostic, ILCError
from .fates import Ablation
from .interpreter import ExecutionResult, run_plan
from .ir import InfoGraph
from .parser import parse
from .planner import Plan, make_plan
from .semantics import CheckResult, check
from .simulator import SimReport, simulate
from .verifier import VerificationReport, verify


def analyze_source(source: str, file: str = "<input>", cfg: Optional[CostConfig] = None) -> CheckResult:
    """Parse + semantic check; syntax errors become diagnostics instead of exceptions."""
    try:
        return check(parse(source, file), cfg)
    except ILCError as e:
        return CheckResult(None, e.diagnostics)


def compile_source(source: str, file: str = "<input>", cfg: Optional[CostConfig] = None) -> InfoGraph:
    res = analyze_source(source, file, cfg)
    if not res.ok:
        raise ILCError(res.diagnostics)
    return res.graph


@dataclass
class PipelineResult:
    graph: InfoGraph
    plan: Plan
    verification: VerificationReport
    simulation: SimReport
    execution: ExecutionResult


def run_pipeline(source: str, file: str, cfg: CostConfig, planner: str = "exhaustive",
                 ablation: Ablation = Ablation(), seed: int = 0, inputs: Optional[Dict[str, int]] = None,
                 fault: Optional[str] = None, budget: int = 200_000) -> PipelineResult:
    g = compile_source(source, file, cfg)
    plan = make_plan(g, cfg, ablation, planner, budget)
    return PipelineResult(g, plan, verify(g, plan.execution, cfg), simulate(g, plan.execution, cfg),
                          run_plan(g, plan.execution, inputs, seed, fault))
