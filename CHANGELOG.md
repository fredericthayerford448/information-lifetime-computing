# Changelog

## 0.1.0 - Digital Fate Calculus Prototype

First executable version of the research foundation (`docs/research-foundation-v0.1.md`).

- DSL with `stato`, `trasforma`, `durata`, `destino`, `recupero`, `vincolo`, `componente`, `flusso`, `emit`.
- Lexer, parser, semantic checker with located diagnostics.
- Information-Lifetime IR: lifetimes, shadow uses, regeneration grades, irreversibility boundaries.
- Fate calculus engine (six fates, legality with reasons), abstract cost model with named profiles.
- Exhaustive branch-and-bound planner (optimal under the abstract model), greedy and conventional baselines.
- Independent plan verifier (invariants P1, I2-I7, constraints), reference interpreter with fault injection,
  abstract simulator.
- Ablation switches (boundary typing, recovery coupling, uncompute) for falsification experiments.
- CLI: `ilc check | inspect | plan | simulate | run | profiles`.

Not implemented: physical photonics, HZO device models, production backend, validation of any thesis claim.
