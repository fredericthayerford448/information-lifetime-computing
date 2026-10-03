# Implementation Notes

## Stack and why
Python 3.9+ standard library only (no runtime dependencies); `pytest` for tests. Rationale: readability for researchers who
are not compiler engineers, deterministic behaviour, trivial installation, no framework dependency. The parser is a
hand-written lexer plus recursive descent (about 250 lines); there is deliberately no parser generator, MLIR or LLVM.

## Naming
The brief's CLI examples used the placeholder name `ourlang`. The package is `ilc` (information-lifetime computing) and the
command is `ilc`; `ourlang` is installed as an alias so the brief's commands work verbatim. Source files use `.lang`.

## What was not changed
`docs/research-foundation-v0.1.md` is a byte-identical copy of the foundation document produced in the previous phase: no
formatting cleanup, no edits. Its claims remain hypotheses; nothing here validates them.

## Module map
| Module | Role |
|---|---|
| `lexer.py`, `parser.py`, `syntax.py` | tokens, AST, located diagnostics |
| `semantics.py` | semantic checker: builds the IR or returns diagnostics |
| `ir.py` | information graph, lifetimes, needs, recovery regions, machine, text rendering |
| `types.py`, `ops.py` | fates, grades, boundaries; operation library |
| `fates.py` | fate calculus: legality + reasons, schedules, per-state costs, ablation switches |
| `costs.py` | cost vector, config, profiles, elementary costs |
| `planner.py`, `plan.py` | search, explanations, plan assembly |
| `verifier.py` | independent plan verifier |
| `interpreter.py` | reference interpreter with fault injection |
| `simulator.py` | abstract simulator (independent re-derivation of costs) |
| `pipeline.py`, `cli.py` | orchestration and command line |

## Design decisions worth knowing
1. **Pins are needs.** Dependency pinning (F§8 I4) and recovery shadow uses (I3) are the same kind of object, a `Need` at a slot.
   Processing states dependents-first lets each state's lifetime be final when it is decided. Costs are additive per state, so
   branch-and-bound is exact.
2. **Two cost implementations.** The planner costs fates from analytic schedules; the simulator re-derives costs by walking the
   plan's actions. `tests/test_simulator.py` asserts they agree for every example, profile and planner.
3. **The verifier is independent.** It uses only the plan and the IR, so it can falsify the planner. Negative plans are built by
   hand in `tests/test_verifier.py`; `experiments/ablation_matrix.py` lets ablated planners generate unsound plans on purpose.
4. **Ablation switches** (`--ablate boundary-typing|recovery-coupling|uncompute`) correspond to the ablation arms of the foundation's
   killer experiment. They make the engine unsound by design.
5. **Explanations are counterfactual.** For each state and legal fate the CLI prints the whole-plan objective if only that
   state used that fate, so "why this fate" is checkable.

## Divergences and deferrals
See `OPEN_QUESTIONS.md` (OQ-1 to OQ-18). Notably: no sequenced fates, no `valid`, no equivalence classes, no photonic/HZO models,
the killer experiment (KE-1) is **not** run, and the Checkmate-style baseline (arm A2) is not implemented.

## Test inventory
Parser, semantics (24 negative programs with expected error codes), IR, fate calculus, cost model, planner (brute-force
cross-check), interpreter (including fault injection and noisy regeneration), verifier (hand-built negative plans), simulator
(cross-check against the planner), CLI, and end-to-end integration across all examples and profiles.
