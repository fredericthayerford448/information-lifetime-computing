# Fate calculus (as implemented)

Fates act on a state's materializations at its anchors (birth, need slots, death). An **idle gap** is a pair of consecutive anchors with at
least one slot between them. `END = N + 1 + horizon`.

| Fate | Legal when | Actions (slot, phase) | Residency |
|---|---|---|---|
| **retain** | state is alive at the end (output, persistent, needed at emit) | none | primary from birth to `END` |
| **erase** | not persistent; not a `restore`-region frontier | `ERASE` at (death, post) | primary birth..death |
| **uncompute** | has a producer; producer exact and boundary `none` (or `soft` with eta <= eps_clean); not persistent; not a `restore` frontier | `UNCOMPUTE` at (death, post); pins the producer's inputs at `death` | primary birth..death |
| **recompute** | has a producer; >= 1 idle gap; producer grade satisfies `accept`; not persistent | per gap: `RELEASE` (gap start, post), `REGENERATE` (gap end, pre); final `RELEASE`; pins inputs at each regeneration slot | primary segments only |
| **checkpoint** | durable tier reachable both ways; not persistent | `CHECKPOINT_WRITE` (birth, post); per gap `RELEASE`/`RESTORE`; final `RELEASE` | primary segments + durable birth..`END` |
| **move** | bulk tier reachable both ways; >= 1 idle gap; not persistent | per gap `MOVE_OUT` (start, post), `MOVE_IN` (end, pre); final `RELEASE` | primary segments + bulk across gaps |

Persistent states: only `retain`. Frontier states of a `restore` region: only `checkpoint`. A pinned `destino` restricts the planner to that fate.

## Explanations
`fates.assess` returns `(legal, reason)` for every fate, in the context of the state's final needs. Example reasons:

```text
recompute  no   required source information unavailable: 'a' is a source-bound input and cannot be regenerated
uncompute  no   producer 'quantize' is a HARD irreversibility boundary: no inverse over the reachable domain (foundation I5)
retain     no   dead temporary: retaining it leaks storage past its death (clean-exit rule, OQ-3)
```
`ilc plan` also prints, for each legal fate, the objective of the **whole plan** if only that state used it (counterfactual), and the next-best alternative.

## Search
Reverse topological order (dependents first). For each state: enumerate legal fates, add the fate's pins to its inputs, recurse; prune when the partial
(additive) objective exceeds the incumbent; constraints are checked at leaves; ties are broken by `FATE_PREFERENCE` (retain, erase, move, checkpoint, recompute,
uncompute). Optimal under the abstract model when the node budget (default 200,000) suffices.

## Ablations
`Ablation(boundary_typing, recovery_coupling, allow_uncompute)` turn off one component. With boundary typing off, uncompute across HARD and unsound recompute become legal.
With recovery coupling off, shadow uses and the restore obligation disappear. The verifier and interpreter are expected to catch the consequences (`experiments/ablation_matrix.py`).
