# Cost model (abstract)

> **All numbers are abstract model units. They are not measurements of any hardware.** (OQ-9)

`CostVector(energy, storage, latency, recovery)`; objective = `weight_energy*energy + weight_storage*storage + weight_latency*latency + weight_recovery*recovery`.

## Elementary costs (`costs.py`)
| Action | Energy | Latency |
|---|---|---|
| `EXEC` / `REGENERATE` | `e_exec * op.weight * bits` | `l_exec * op.weight` |
| `UNCOMPUTE` | `uncompute_factor * (EXEC energy)` | `uncompute_factor * (EXEC latency)` |
| `ERASE` / `RELEASE` | `e_reset * bits` | `l_reset` |
| `MOVE_OUT` / `MOVE_IN` | `e_xfer * bits` | `l_xfer` |
| `CHECKPOINT_WRITE` | `e_ckpt * bits` | `l_ckpt` |
| `RESTORE` | `e_restore * bits` | `l_restore` |

Operation weights: copy 0.5, not 0.5, inc 1.5, xor/and/or/quantize 1, add/sub 2, parity 1.5.

**Storage** = sum over residency windows of `tier_weight * bits * slots` (primary `w_primary`, bulk `w_bulk`, durable `w_durable`). A window is inclusive on both ends.
Values never released stay resident until `END = N+1+horizon`.

**Recovery** = per state `fault_prob_slot * V * R` (V = volatile slots lacking a durable copy; slots up to and including the checkpoint write slot count as exposed;
R = regeneration energy if the producer is exact/tolerant, else `unrecoverable_penalty_bit * bits`) + per region `region_fault_prob * replay_cost`
(`restore` adds the frontier restore energy).

## Profiles (`ilc profiles`)
| Profile | Idea |
|---|---|
| `abstract-default` | reset costs 3x a unit op: regime where reversible clean-up can win (T4) |
| `cmos-like` | reset is cheap: erase wins |
| `storage-scarce` | cheap reset, very scarce primary storage: recompute wins |
| `fragile` | high fault rate: checkpoint wins for source-bound state |
| `reversible-hw` | very expensive erase, cheap ops |

Override any coefficient with `--cost-config file.json` (keys = `CostConfig` fields).

## Consistency
The planner computes costs from analytic schedules; the simulator recomputes them by walking the plan. They must agree exactly (`tests/test_simulator.py`).
`experiments/regime_sweep.py` varies one coefficient and prints which fate wins. That demonstrates the mechanism, **not** the thesis.
