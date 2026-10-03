# Falsification-oriented design

The foundation (F§14, F§20-21) defines how the thesis can fail. This prototype does **not** run those experiments; it provides the executable
pieces and a structure for negative cases, so that a failure would be visible.

## What the software can already falsify
| Question | Mechanism | Where |
|---|---|---|
| Is the legality calculus sound? | Independent verifier + interpreter on every planner output, all examples x profiles | `tests/test_integration.py` |
| Does each illegal case fail for an explicit reason? | 24 negative programs with expected error codes; hand-built negative plans | `tests/negative/`, `tests/test_verifier.py` |
| Is the planner optimal under its own model? | Brute-force cross-check on small graphs | `tests/test_planner.py` |
| Do the two cost implementations agree? | Planner vs simulator | `tests/test_simulator.py` |
| Is boundary typing necessary (foundation T2)? | Ablate it; the verifier/interpreter flag the unsound plans | `experiments/ablation_matrix.py` |
| Does recovery coupling matter (T3)? | Ablate it; fault injection fails | same; `ilc run examples/recovery.lang --inject-fault guard --ablate recovery-coupling` |
| Is uncompute ever selected, and when (T4)? | Regime sweep over coefficients (mechanism only) | `experiments/regime_sweep.py` |

## Negative-case catalogue (all implemented)
Illegal uncompute (HARD boundary): `tests/negative/illegal_uncompute_hard.lang`, verifier I5. Missing inverse (input): `illegal_uncompute_input.lang`.
Lost dependency: `recompute_source_bound.lang`; verifier I4 (inverse input released). Premature erase: `premature_erase_persistent.lang`; verifier I2 (use after release).
Recovery conflict: `recovery_conflict.lang`; verifier I3. Inconsistent lifetime: `inconsistent_lifetime.lang`, `use_after_death.lang`, `impossible_lifetime.lang`.

## What is NOT tested (and why this is not evidence)
- No hardware, no photonics, no HZO: foundation F1 and F4 are untested.
- No Checkmate-style baseline (arm A2), no real workloads, no energy measurement: KE-1's decision rule (F§20.8) has not been applied.
- The regime sweep shows that coefficients change the answer, which is true by construction.
- Cost coefficients are arbitrary (OQ-9). Any statement "uncompute wins" is conditional on a chosen profile.

## Adding a negative case
1. Program-level: add `tests/negative/<name>.lang` whose first line is `// expect: <CODE>`; `tests/test_semantics.py` picks it up automatically.
2. Plan-level: build rows with `ilc.plan.plan_from_tuples` and assert on `verify(...).violations[...]` in `tests/test_verifier.py`.
3. Model-level: add a program under `experiments/programs/` and rerun `experiments/ablation_matrix.py`.
