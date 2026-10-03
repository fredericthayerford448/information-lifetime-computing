# Architecture

```text
Language (.lang)
   | lexer.py, parser.py, syntax.py
Parser -> AST
   | semantics.py                     (diagnostics: E-UNDEF, E-DEP, E-LIFETIME, E-FATE-ILLEGAL, ...)
Semantic checker -> Information-Lifetime IR (ir.py)
   | fates.py (needs, gaps, legality + reasons, schedules)
Fate analysis
   | planner.py (exhaustive branch-and-bound | greedy | conventional) + plan.py (assembly)
Planner -> Execution plan
   | verifier.py (independent)        simulator.py (abstract costs)        interpreter.py (values, faults)
Verification / simulation / reference execution
```
`pipeline.py` wires the stages; `cli.py` exposes them as `check | inspect | plan | simulate | run`.

## Research concept -> implementation

| Research concept (foundation) | Implementation |
|---|---|
| Eight primitives (F§7) | AST node types in `syntax.py`; IR in `ir.py` |
| `componente` / `flusso` | `ir.Machine`, `Component`; `flusso` gates `move` and `checkpoint` in `fates.assess` |
| `stato` / information object | `ir.StateNode` (single assignment; input or derived) |
| `trasforma` | `ir.TransformNode` + `ops.Op` (semantics, weight, `regen`, `bnd`) |
| `flusso` as dataflow edge | transform inputs/outputs; `InfoGraph.deps/dependents` |
| `durata` | `StateNode.durata_*` -> a `durata` `Need` at its end slot (`LifetimeSpec` in prose) |
| `destino` | `types.Fate`, `StateNode.declared_destino`, planner decision variable |
| `recupero` | `ir.Region` (frontier, commit, policy) -> shadow `Need`s |
| `vincolo` | `ir.Constraint` + component capacity, checked by planner leaf test and verifier `C` |
| Information lifetime (F§8) | `ir.Lifetime`, `InfoGraph.base_needs`, effective death via pins |
| Release point (F§8 correction) | anchors and idle gaps in `fates.anchors_of/gaps_of` |
| Six fates + legality (F§9) | `fates.assess`, `fates.build_schedule` |
| Regeneration grades (F§6.1) | `types.Grade`, `satisfies`, `Op.regen`, `StateNode.accept` |
| Irreversibility boundary (F§10) | `types.Boundary`; verifier I5; `fates.assess` for uncompute/recompute |
| Recovery as shadow use (F§11) | `Need(kind="shadow")`; verifier I3; `interpreter.inject` |
| Fate calculus as optimisation (F§16-17) | `planner.search_exhaustive` over `fates` + `costs` |
| Cost model (F§17) | `costs.CostVector`, `CostConfig`, profiles |
| Compiler fixpoint (F§16.1) | pins processed dependents-first in `planner`/`planner.evaluate`; placement/routing not modelled |
| Independent verifier (F§16.3) | `verifier.verify` |
| Fate-transparent semantics (F§6.2) | `interpreter.reference_values` vs `run_plan` outputs |
| Ablation arms (F§20.3) | `fates.Ablation`, `--ablate` |

## What the prototype does not model
Photonic domains, HZO, placement and routing, parallel resources, real failure domains, `valid`, equivalence classes, sequenced fates
(see `OPEN_QUESTIONS.md`).
