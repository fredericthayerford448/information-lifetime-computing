# Semantics

## Meaning of a program (F§6.2)
A program's meaning is its **fate-free reference semantics**: run the transforms in order on bit-vectors (`interpreter.reference_values`).
Fates are optimisation choices. A plan is correct iff its outputs equal the reference (or differ only where a consumer declared a
weaker acceptance grade) and the plan passes the verifier.

## Time (OQ-1)
Slot 0 inputs loaded; slot k transform k; slot N+1 emit. Phases within a slot: `pre`, `exec`, `post`.

## States
Single assignment. A state with no producing transform is an **input** (source-bound: it cannot be regenerated). A state produced by a
transform is **derived**. `emit` marks outputs: they are needed at slot N+1.

## Lifetime
`death(x) = max(birth, every need slot)` where needs are: consuming transforms (`use`), `emit`, the end of `durata`, and recovery
shadow uses. `until(X)` means relevant until X is born; `steps(n)` until birth+n; `persistent` until emit and beyond.
Checks: a use after the declared `durata` end is `E-USE-AFTER-DEATH`; a `durata` ending before birth, or past the program end, is
`E-LIFETIME`; `until(...)` must name a different, defined state (`E-DURATA`).

## Effective death and pins
In a plan, uncompute and recompute need their inputs live at the slot where they run. That adds a **pin** need to each input, so
`eff_death(x)` can exceed `death(x)`. Lifetimes and fates are therefore co-determined: the planner decides dependents first.

## Regeneration and irreversibility
Each transform has a regeneration grade (`exact` > `tolerant(eps)` > `distributional` > `source_bound`) and a boundary
(`none` < `soft(eta)` < `hard`). A regenerated value must satisfy the consumer's `accept` grade. Uncompute is illegal across HARD, across
SOFT with `eta > eps_clean`, and for non-exact producers. Inputs can be neither recomputed nor uncomputed. Mathematical invertibility is not
physical reversibility: the grades are separate properties and `bnd` may only strengthen an operation's intrinsic boundary.

## Recovery
`recupero R { region = [...], policy = replay|restore, commit = s }`. Frontier = states the region consumes from outside it. A shadow
use at the commit slot keeps the frontier available (`replay`: resident; `restore`: durable copy). The interpreter can inject a fault
and repair by the policy.

## Errors versus planner infeasibility
Context-independent problems (types, undefined names, impossible lifetimes, a pinned fate that can never be legal) are semantic errors.
Problems that depend on the plan context (a pinned `recompute` with no idle gap, unsatisfiable constraints) are `E-PLAN` errors from the planner.
