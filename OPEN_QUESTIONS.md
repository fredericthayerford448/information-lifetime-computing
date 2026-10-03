# Open Questions and Prototype Assumptions

Where the research foundation (`docs/research-foundation-v0.1.md`) is underspecified, or implementation exposed
an ambiguity, the prototype chose the smallest behaviour that keeps it moving. **None of these changes the
foundation's thesis or core definitions.** Each entry says what the foundation says, what the code does, and what
would resolve it. Code comments and diagnostics cite these ids.

| Id | Topic |
|---|---|
| OQ-1 | Discrete slot time instead of physical time |
| OQ-2 | One fate per state; no sequenced fates (e.g. uncompute then recompute) |
| OQ-3 | Clean-exit rule: `retain` is illegal for dead temporaries |
| OQ-4 | `uncompute` and HARD but deterministic operations (reading of I5) |
| OQ-5 | Nested regeneration and composition of tolerance contracts |
| OQ-6 | "Release = clean-up": there is no free drop |
| OQ-7 | Recovery model: fault point, replay vs restore, commit |
| OQ-8 | Fault-exposure term and the unrecoverable-loss penalty |
| OQ-9 | Abstract cost coefficients and profiles |
| OQ-10 | Checkpoint semantics (no consistent cut, no failure-domain model) |
| OQ-11 | `move` semantics |
| OQ-12 | `valid` (staleness) omitted |
| OQ-13 | Information-equivalence classes omitted |
| OQ-14 | Persistent state is retain-only (no endurance/write model) |
| OQ-15 | Machine model: one component per role |
| OQ-16 | Conditional-entropy criterion approximated structurally |
| OQ-17 | Planner scalability and optimality scope |
| OQ-18 | Deviation of the brief's sample output from the foundation's rules |

## OQ-1 Discrete slot time
*Foundation:* semantic time is a partial order plus validity windows; physical time is a schedule (F§6.3).
*Prototype:* transforms run in textual order, one per slot; slot 0 loads inputs, slot N+1 emits. `death` is inclusive:
the last slot at which anything needs the state; the release action runs in the `post` phase of that slot.
*Resolves with:* a real scheduler with parallel resources and a latency-aware model.

## OQ-2 One fate per state
*Foundation:* fates can be sequenced over a state's life (F§9); `destino` elaborates to a fate *schedule*.
*Prototype:* each state gets one fate from the six, applied uniformly to all its idle gaps and to its final release.
The Bennett-style "uncompute at gap start, recompute later" is therefore not expressible.
*Resolves with:* making the decision variable a fate per (state, gap), at the price of a larger search space.

## OQ-3 Clean-exit rule
*Foundation:* `retain` has capacity/retention preconditions only (F§9); for a dead state "only erase and uncompute
remain meaningful" (F§8).
*Prototype:* `retain` is legal only for states alive at the end of the program (outputs, `persistent`, anything needed at the
emit slot). Otherwise retaining a dead temporary is a leak, and a cheap bulk tier would make "park the garbage forever"
look optimal under a reset-heavy profile, which is a model artefact. The verifier enforces the same rule (I6).
*Consequence:* in `abstract-default` a temporary's legal fates are erase, uncompute, checkpoint, plus move/recompute when
it has an idle gap.

## OQ-4 Uncompute and HARD-but-deterministic operations
*Foundation:* F§9/I5 forbid an uncompute path across a HARD edge; F§10.1 notes `x -> (x, f(x))` is injective on the reachable
set even if `f` is many-to-one.
*Tension:* for a deterministic many-to-one digital operation (e.g. `quantize`) with live inputs, Bennett out-of-place
uncompute is logically possible. The foundation's HARD class mixes that case with entropy-injecting hardware (detector, ADC),
where re-execution gives a different realisation.
*Prototype:* follows I5 literally: uncompute is illegal when the producer is HARD, and also when it is not `regen=exact`.
*Resolves with:* splitting HARD into deterministic-lossy and entropy-injecting, as a foundation revision.

## OQ-5 Nested regeneration and tolerance composition
*Prototype:* a regeneration or uncompute adds a "pin" need (always `exact`) on each input at that slot; the input's own fate
then satisfies it, so regeneration chains arise naturally (see `ilc plan examples/recomputation.lang`). Pins are always
`exact`, so no looser contract is composed through a chain. *Foundation:* composition of (eps, delta) contracts is open
(F§22.2). *Resolves with:* a calculus for composing tolerance grades.

## OQ-6 Release = clean-up
*Foundation:* I6, every information-destroying step is an explicit erase event; erase costs a reset (F§9, F§17.2).
*Prototype:* every release of a primary materialization (erase, final release, release at a gap start for recompute/checkpoint) pays
`e_reset * bits`, except `uncompute` (pays the inverse) and `move` (relocation). There is no free "drop". This is what makes
the regimes in OQ-9 meaningful.

## OQ-7 Recovery model
*Foundation:* regions, replay frontier, commit, shadow uses, consistent cuts (F§11).
*Prototype:* a `recupero` names member states (outputs of transforms), a policy and a commit state. The frontier is the set of
states consumed from outside the region. Each frontier state gets a shadow need at the commit slot. `replay` requires them
resident; `restore` requires a durable copy (hence `checkpoint` is the only legal fate). The injected fault corrupts
the region's resident outputs right after the commit state is produced; repair re-executes the needed transforms in order.
No node/link/drift faults, no partial failures, no silent faults (RLC5).

## OQ-8 Fault exposure
*Foundation:* expected recovery cost enters the objective (F§17.2); checkpoint wins for source-bound/exposed states (F§9).
*Prototype:* each state pays `fault_prob_slot * (volatile slots lacking a durable copy) * R`, where `R` is the regeneration energy
if the producer is exact/tolerant, else `unrecoverable_penalty_bit * bits`. Each region adds `region_fault_prob *` its replay cost.
The form is invented for the prototype.

## OQ-9 Abstract cost coefficients
Every coefficient is an abstract unit with **no physical meaning**. `abstract-default` sets reset to 3x a unit operation so that
the regime where reversible clean-up can win (hypothesis T4) is visible in the shipped examples; `cmos-like` flips it.
This shows the planner responds to the regime. It is not evidence that any real machine sits in either regime (F§10.5 argues
Landauer-scale accounting is not the business case). Profiles are listed by `ilc profiles`.

## OQ-10 Checkpoint semantics
*Foundation:* consistent cut, durable component outside the failure domain, precision (F§9, I7).
*Prototype:* a single durable tier assumed independent; the copy is written right after birth and kept until the end of the
plan (durable hold cost); no cut consistency across states.

## OQ-11 Move
Relocation between primary and bulk across idle gaps only (transfer cost each way, bulk hold cost). Domain conversion is out of
scope (F§9 says a conversion is a `trasforma`). The final release after the last use is a reset.

## OQ-12 Validity (`valid`)
F§8 distinguishes `valid(x)` (staleness) from liveness. Omitted; `durata` is the only lifetime declaration.

## OQ-13 Information-equivalence classes
Choosing which member of an invertible pair to retain (F§14.4, F§22.8) is not implemented.

## OQ-14 Persistent state
`durata = persistent` is retain-only. No write cost, endurance or retention model (HZO is out of scope for Stage 0).

## OQ-15 Machine model
One component per role (primary/bulk/durable); capacity is enforced only for primary (peak bits). Flows are by role.

## OQ-16 Conditional-entropy criterion
F§10.4: uncompute is legal when `H(x | surviving state) = 0`. The prototype approximates this structurally: the producer is
exact, deterministic and has boundary `none` (or `soft` within `eps_clean`), and its inputs can be kept live.
Erase reasons mention the criterion; no entropy is computed.

## OQ-17 Planner scope
Exhaustive branch-and-bound over fate assignments (dependents first). It is optimal *under the abstract model* when it finishes
within the node budget; otherwise it falls back to greedy and says so. Complexity of the general fate game is open (F§22.1).

## OQ-18 Brief's sample output vs. the foundation
The project brief's sample shows `retain/move/checkpoint/recompute` legal and `erase` illegal for the reversible example's
`tmp`. Under the foundation's own rules (F§8-9) a dead temporary may be erased or uncomputed, cannot usefully be retained,
and has no idle gap to move/recompute across. The prototype follows the foundation; its output differs from the sample
accordingly (see `ilc plan examples/reversible.lang`). The sample was labelled approximate.
