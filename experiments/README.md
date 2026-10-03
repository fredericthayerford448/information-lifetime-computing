# Experiments

**Status: no experiment in this directory validates the research thesis.** They are model-only (abstract cost units, no hardware). The
foundation's killer experiment KE-1 (`docs/research-foundation-v0.1.md` §20) is **not run**: it needs a Checkmate-style baseline, real
workloads, calibrated digital measurements and a pre-registered decision rule.

| Script | Purpose |
|---|---|
| `regime_sweep.py` | Vary one coefficient and print which fate wins (mechanism demo) |
| `ablation_matrix.py` | Plan with parts of the model disabled; show what the independent verifier/interpreter catch (soundness) |
| `programs/` | Programs used only by experiments |

Run: `python experiments/regime_sweep.py [--csv experiments/results/sweep.csv]`, `python experiments/ablation_matrix.py`
(results directories are git-ignored).

## How to add an experiment
1. State the question and the foundation claim it relates to (T1-T5, F1-F7) in the script's docstring.
2. Say what outcome would **falsify** it before running; for KE-1 style comparisons freeze thresholds first (F§20.7-20.8).
3. Use only public APIs: `ilc.pipeline.run_pipeline`, `ilc.planner.make_plan`, `ilc.verifier.verify`, `ilc.simulator.simulate`.
4. Match conditions across arms (same program, inputs/seeds, fault process, constraints). Compare planners with `--planner exhaustive|greedy|conventional`.
5. Label every number as abstract-model output unless it was measured; never commit invented results.
6. Add programs under `programs/`; add a soundness check (verifier + interpreter) for every plan you compare.

Natural next experiments: a Checkmate-style recompute/offload planner as arm A2 (planner without uncompute, boundary typing, recovery coupling);
the RevNet-style positive control on real hardware; the all-HARD negative control (zero uncompute fates; `examples/boundary.lang` is a start).
