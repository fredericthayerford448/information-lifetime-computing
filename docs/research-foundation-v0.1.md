# Information-Lifetime Computing
## 0→1 Research Foundation (v0.1)

*30 September 2026. Audience: language researchers, compiler architects, photonics engineers, computer architects, reliability engineers. Nature: a research object for hand-off, not a product plan or pitch.*

**Evidence tags used throughout**

| Tag | Meaning |
|---|---|
| **[E]** | Established concept (published, widely accepted) |
| **[H]** | Hypothesis of this project; may be false |
| **[A]** | Engineering assumption; must be replaced by a sourced or measured value |
| **[Q]** | Open research question |
| **[I]** | Implementation choice; replaceable without changing the idea |

---

## Headline findings (read first)

1. **The thesis as literally worded is not novel.** Every individual fate already has a mature literature: retain/move (memory hierarchies, spilling), recompute (rematerialization, Halide-style recompute-vs-store), checkpoint (fault-tolerance runtimes, gradient checkpointing), uncompute (Bennett, reversible pebbling, quantum-language uncomputation), erase (deallocation, RAII, zeroization). "First-class information lifetime" describes liveness analysis, ownership types and rematerialization planners taken together.
2. **What survives the prior-art test is narrower and sharper:** a *fate calculus*, meaning legality conditions plus a cost model over six fates, on an information graph that (i) types where the machine physically destroys information, (ii) types whether a regenerated value is exact, tolerance-equivalent, statistical, or impossible, and (iii) lets fault-recovery obligations extend lifetimes. It is formalizable as a generalized pebble game (§8–§10, §17).
3. **The largest technical risk is `uncompute`.** In digital CMOS, running an inverse rarely beats recomputing forward and then erasing. Landauer-scale costs sit roughly nine orders of magnitude below realistic per-bit costs (§10). Uncompute has to earn its place on capacity, endurance, or domain-re-entry grounds, not thermodynamic ones. The killer experiment is built so that failure degrades the model to five fates instead of killing it.
4. **The hardware motivation is real but must be stated carefully.** Published analyses of integrated photonic accelerators put the dominant costs at domain conversion and memory movement (one survey reports these can exceed 80% of system energy), not at the optical linear transform. That is exactly where lifecycle decisions live.
5. **Two premises of the brief are corrected.** (a) "After `death(x)`, select a fate" conflates two events: semantic death, and the release of one materialization at one place. (b) The compiler pipeline is a fixpoint, not a line, because fate, lifetime, placement and recovery determine one another (§8, §16).
6. **The eight primitives are kept.** Each passes a deletion test, but `flusso` and `destino` are the two whose independence depends on stated conditions (§7).

---

## 1. Executive Definition

**Definition.** A programming model and compiler architecture for classical, heterogeneous (photonic + CMOS) dataflow computers in which every piece of information is a named `stato` with an explicit lifecycle (birth, validity, use, death). At each *release point* the compiler, not the programmer, chooses among six fates (retain, move, checkpoint, recompute, uncompute, erase) by solving a constrained optimization over energy, latency, storage, bandwidth, precision and reliability. The legality of each fate is decided by a typed calculus that knows:

- which transforms are invertible over the *reachable* domain,
- where the machine physically destroys information (irreversibility boundaries),
- whether a regenerated value is exact, tolerance-equivalent, statistical, or unobtainable,
- which states fault recovery still needs.

**In one sentence:** the compiler treats "what to do with information when it is no longer needed *here*" as an optimization variable whose legal values are constrained by physics and recovery obligations.

| This project **is** | This project **is not** |
|---|---|
| A fate calculus + cost model + IR for information lifecycle | A new syntax |
| Compiler-centred; the language exposes it progressively | A reversible computer, or a claim that everything should be reversible |
| Motivated by a photonic-CMOS dataflow machine | A generic photonic accelerator proposal |
| Falsifiable by a small simulation-plus-measurement experiment | A quantum-computing project |
| Explicit about irreversibility and noise | A claim that photonics or reversibility saves energy by default |

---

## 2. Problem

Derivation path required by the brief: physical problem → semantic need → language abstraction → compiler consequence → measurable hypothesis.

| # | Physical problem | Semantic need | Abstraction | Compiler consequence | Hypothesis |
|---|---|---|---|---|---|
| P1 | Domain conversion (DAC/modulator in, detector/ADC out) and memory movement dominate system energy in photonic accelerators | Know which information crosses domains, how often, and whether it must be recreated | `stato` with lifetime; conversions as `trasforma` with boundary grade | Choose fates that minimize crossings and traffic | T1 |
| P2 | Optical fields cannot be stored for long; retention means converting to an electronic representation | Retention is a priced decision, never a default | `destino` as decision variable | Retain vs regenerate solved per state | T1 |
| P3 | Analog noise, loss and calibration error make regeneration inexact | Contract on how "equal" a regenerated value must be | Regeneration grade in the type of `stato`/`trasforma` | Recompute/uncompute legality check | T2 |
| P4 | Drift, link and node faults require replay, which needs surviving inputs | Recovery obligations extend lifetimes | `recupero` + shadow uses | Joint lifecycle/recovery planning | T3 |
| P5 | Persistent optical state (HZO) has limited write endurance and non-trivial write cost | Distinguish persistent from transient; budget writes | `duration = persistent` + endurance property | Master-copy discipline; write-aware fates | T1 |
| P6 | Erasure and reversibility only have physical meaning if hardware is physically reversible; most of this machine is not | Separate logical, numerical and physical invertibility | Boundary grade on transforms | Uncompute justified by resource accounting, not slogans | T4 |

**Why existing layers do not address this jointly [H].** Rematerialization planners in ML compilers (Checkmate, DTR) trade recompute against store under a memory cap, largely for one memory level and deterministic operators. Checkpoint runtimes decide recovery separately. Reversible-language and quantum-uncomputation work treats uncomputation as a correctness device applied to a dataflow that is already fixed. Publicly visible photonic compiler efforts (for example MLIR-based stacks at commercial vendors) describe lowering operators to hardware; I found no public source treating lifecycle, irreversibility and recovery as one optimization. This is absence of evidence from a limited search, not proof of absence (§19).

---

## 3. Core Thesis

**Main thesis [H].** For workloads that have (a) intermediates reused at long distance, (b) a mix of invertible and irreversible transforms, (c) bounded fast memory, and (d) nonzero fault rates, a compiler that solves the fate problem with typed legality conditions finds plans that dominate every fixed strategy, and dominate rematerialization/offload planners *lacking uncompute, boundary typing and recovery coupling*, on the energy–latency–storage–reliability frontier at matched quality, by more than the uncertainty of the cost model.

Decomposed into separately falsifiable sub-hypotheses:

| ID | Sub-hypothesis [H] |
|---|---|
| T1 | **Fate non-dominance.** No single fixed fate is within 5% of the auto plan across realistic workloads and plausible device parameters. |
| T2 | **Boundary typing is necessary.** Without it, planners either violate quality contracts (unsound) or forgo legal savings (conservative). |
| T3 | **Recovery coupling pays.** Joint planning of lifecycle and recovery lowers expected cost versus independently tuned policies. |
| T4 | **Uncompute is non-empty.** A plausible-parameter region exists where uncompute is strictly optimal for some states. |
| T5 | **Progressive disclosure works.** Level-1 programs (no annotations) capture at least 80% of the gain of Level-3 programs. |

**Non-claims.** Not every computation should be reversible. Reversibility does not automatically save energy. Optics is not automatically more efficient. Topology cannot recover information physically destroyed by absorption, scattering, noise or quantization.

---

## 4. What Is Actually Being Invented

| # | Component | Status |
|---|---|---|
| C1 | **Fate calculus**: six fates with explicit legality preconditions, unified as a generalized pebble game with heterogeneous memories | Unification is the contribution; each ingredient is [E] |
| C2 | **Irreversibility boundary + regeneration grade** as typed properties, giving machine-checkable recompute/uncompute legality across analog–digital crossings | [H] novel in combination |
| C3 | **Recovery as shadow use**: fault-recovery obligations extend semantic lifetime; a consistency check joins lifetime and recovery plans | [H] novel in combination |
| C4 | **Uncompute vs erase via conditional entropy**: uncompute is legal only when the victim is a reversible function of surviving state; otherwise only erase/retain/checkpoint remain | Physics [E]; use as a compiler legality rule [H] |
| C5 | **Information-lifetime IR** separating identity-carrying information objects from their materializations | Design [I] |
| C6 | **Wall-plug cost model** with domain-crossing, retention, endurance and recovery terms | Engineering [A] |

**Not invented:** the eight names, the hardware stack, reversible computing, checkpointing, rematerialization, pebbling.

---

## 5. Hardware-Originated Motivation

| Layer | Role in this machine | Lifecycle consequence |
|---|---|---|
| Silicon | Photonic/CMOS integration substrate | Hosts control, ADC/DAC, ECC, thermal tuning: the irreversible side. All digital fates execute here |
| Silicon nitride | Low-loss waveguides | Fields can wait only briefly (delay lines are long and lossy) [A]. Movement is cheap; optical storage is essentially unavailable beyond ns–µs |
| Lithium niobate | High-speed electro-optic modulation | The entry to the optical domain. **Re-entry cost** (DAC + modulator) is paid each time digital state is re-injected |
| HZO | Persistent optical configuration | Not RAM. Reported: non-volatile phase shift on an SiN waveguide with persistence beyond 10⁴ s (preprint), and a ferrophotonic microring with 3.5 dB contrast at ~40 pJ switching energy at ±8 V. Writes are costly and endurance-limited [A]; multi-year retention is not shown in the sources I found |
| Germanium | Photodetection | Start of the first HARD irreversibility boundary |
| SRAM | Transient/local digital state | Cheap, fast, volatile, capacity-bound |
| HBM | Bulk digital state | Cheap capacity, comparatively expensive access [A]; natural checkpoint and master-copy tier |

**Six asymmetries that generate the semantics**

- **A1. Conversion dominates.** One survey of photonic-electronic accelerators reports that digital/analog transitions plus associated memory movement can exceed 80% of system energy. A published ADC estimate is ~15 fJ per conversion step at 1 GS/s (~50 fJ at 10 GS/s), scaling roughly with 2^ENOB, so an 8-bit sample costs on the order of 4–13 pJ [derived, A].
- **A2. Retention is neither free nor uniform.** SRAM, HBM, HZO and delay lines have different hold cost, capacity, endurance and failure modes.
- **A3. Loss compounds in dB.** Required laser power grows exponentially with path loss in dB, and roughly exponentially with target bit precision in noise-limited detection [E physics, A parameters]. A round trip through a mesh of loss L dB costs 2L dB: 3 dB → 4× laser power, not 2×.
- **A4. Noise makes regeneration inexact.** Re-running an optical transform yields a new noise realization.
- **A5. Persistent optical state is scarce and write-limited.**
- **A6. Fault classes differ in whether information is destroyed.** Rerouting recovers a link; nothing recovers an absorbed photon.

Nothing above assumes photonics wins. That claim is tested by F1 (§21).

---

## 6. Semantic Model

### 6.1 Objects

```text
Information object  x = (id, τ, π, κ, V)
   τ  type/shape           π  quality/precision contract
   κ  provenance class ∈ { EXACT, TOLERANT(ε), DISTRIBUTIONAL, SOURCE_BOUND }
   V  validity predicate (time or version staleness bound)
Materialization     m = (x, c, r, [t0, t1])      c = component, r = representation
Transform           t = (dom, cod, det, inv, bnd, real, err, cost)
   det ∈ { DET, STOCH(ε,δ), EXTERNAL }
   inv = partial inverse g_t over the *reachable* domain R_t, or ⊥
   bnd ∈ { NONE, SOFT(η), HARD }        (irreversibility grade)
Information graph   G = (X, T, Flows, Components, RecoveryRegions, Constraints)
Plan                Π = (fate schedule, placement, routes, recovery plan)
```

**Regeneration grades.**
- EXACT: bit-exact regenerable from surviving dependencies (deterministic digital).
- TOLERANT(ε): regenerable within ε with probability ≥ 1−δ (calibrated analog/optical linear transforms).
- DISTRIBUTIONAL: regeneration draws a fresh sample from the same distribution (e.g. an ADC noise realization); acceptable only to consumers whose contract is statistical.
- SOURCE_BOUND: depends on a one-shot external event; cannot be regenerated, only retained, checkpointed, or replayed from the source.

Each use `u` declares an *acceptance grade* `a(u)`. A regeneration path is legal for `u` iff its grade meets `a(u)`.

### 6.2 Fate-transparent semantics

The meaning of a program is defined **without** fates. A plan is *correct* iff every delivered output is within its quality contract of the fate-free reference semantics under the declared fault model. Fates are optimization choices, like a Halide schedule: the algorithm/schedule separation becomes a **computation/lifecycle separation**. Pinned fates (`destino = erase` with zeroization) are constraints on the plan; where erasure is externally observable (security), it is a contract.

### 6.3 Two time notions

*Semantic time*: partial order of the program plus validity windows. *Physical time*: the schedule. Lifetimes are stated semantically; residency is decided physically.

### 6.4 Perspective conflicts and their resolution

| Conflict | Resolution |
|---|---|
| PL researcher wants a small sound calculus; architect wants cost realism | Legality (cost-free, checkable) is separated from optimality (cost-driven). Legality ⊂ feasibility |
| Compiler engineer wants static plans; reliability engineer wants adaptive recovery | Static plan plus pre-computed contingency plans for enumerated faults; runtime switches among them [Q] |
| Photonics engineer: noise is continuous; compiler wants discrete legality | Discrete grades with parameterized thresholds (SOFT(η), TOLERANT(ε)), tolerances explicit |
| Reversible-computing researcher: reversibility everywhere; systems engineer: control and nonlinearity are irreversible | Reversibility is a per-transform property; boundaries are explicit; no universal claim |
| Physicist: Landauer governs; engineer: circuit dissipation dominates by orders of magnitude | Landauer kept as a floor and as the *criterion separating erase from uncompute*, not as the cost |
| Builder: annotation burden; expert: control | Progressive disclosure, with T5 as the test |

---

## 7. The 8 Core Primitives

### 7.1 Definitions and deletion test

| Primitive | Denotes | Type-level shape | Deletion test: what is lost |
|---|---|---|---|
| `componente` | Physical/logical resource with capabilities, capacity, failure domain | Resource | No place for materializations; no fate availability |
| `stato` | Information with identity, type, shape, precision, provenance, validity | Information object | Nothing to keep or dispose |
| `trasforma` | Action producing/consuming information; carries det/inv/bnd | Info* → Info* | No regeneration or boundary semantics |
| `flusso` | Movement relation among states/components/transforms, with channel semantics | Relation over (state ∪ component) | Topology and `move` cannot be stated |
| `durata` | Interval/predicate of semantic relevance | Interval or predicate | No `death`, no staleness |
| `destino` | Release-point decision ∈ {retain, move, checkpoint, recompute, uncompute, erase, auto} | Decision variable | No optimization variable |
| `recupero` | Permitted responses to faults | Policy over component/flow | No shadow uses; no fault semantics |
| `vincolo` | Predicate over plan metrics | Constraint | Nothing to optimize against |

**Design pressure (stated honestly).**
- `flusso` is independent of `trasforma` **iff** channels have semantics beyond identity (bandwidth, multicast, ordering, fault domain, topology). In this machine they do: the optical network is part of the computational and reliability model. If a backend had only passive point-to-point wires, `flusso` could be folded into `trasforma`.
- `destino` is independent of `durata` **iff** fate is a decision variable rather than derived. `durata` says *when*; `destino` says *what*; `auto` requires both.
- No required concept in this document needed a ninth primitive. *Materialization*, *boundary grade* and *regeneration grade* are compiler objects or properties, not source primitives.

### 7.2 What is deliberately not a primitive

| Concept | Decision | Reason |
|---|---|---|
| Location/placement | Property of `stato`/`componente` (`home`, `pin`); compiler-decided by default | Placement is a result of fate + routing |
| Precision | Type parameter + contract `π` | Belongs in the type; drives legality |
| Ownership | Type/analysis | Serves single-writer safety, orthogonal to fate |
| Topology | Property of `componente`/`flusso`; backend attribute | Structure, not a semantic category |
| Optical/electrical | Backend attribute of `componente`/`trasforma` (`real`) | Realization choice |
| Energy, latency, bandwidth | Metrics in `vincolo` | Constraints and objectives |
| Reversibility | Property of `trasforma` (`inv`) | A property, not an action |
| Irreversibility boundary | Property `bnd` on `trasforma`; derived by analysis | Checkable and inferable |
| Calibration | `recupero` action + component property | It is recovery from drift |
| Determinism, validity, zeroization | Properties/contracts on `stato` | Drive legality |

Principle: *keep the semantic core small; express detail through properties, types, contracts and analyses.*

---

## 8. Information-Lifetime Model

**Definitions** (per information object `x`):
- `birth(x)`: event at which x's value is first determined.
- `valid(x)`: interval or predicate during which x may be consumed (staleness contract).
- `use(x)`: set U(x) of consumption events; each has a time, a place and an acceptance grade.
- `dependency(x)`: sets of states/transforms from which x derives (deps) and which derive from x (dependents).
- `death(x)`: earliest time after which x carries no obligation.

**Correction to the brief.** The brief selects fates "after death(x)". If x is semantically dead, only erase and uncompute remain meaningful. Fates such as move, checkpoint, recompute and retain apply when x is *still needed somewhere but not at its current place or time*. So:

- **Semantic death** `death(x)`: no remaining obligation anywhere.
- **Release point** `release(m)`: end of the need for materialization `m` at its component. Fates act at release points. For a live x, fates create or schedule other materializations; for a dead x, they dispose of the last one.

**Invariants** (the compiler-checkable core):

| ID | Invariant |
|---|---|
| I1 | Temporal well-formedness: `birth(x) ≤ t_u ≤ death(x)` for every use, and `t_u ≤ expiry_V(x)`. (The brief's invariant.) |
| I2 | Coverage: at every use time a materialization of adequate precision exists at the consumer's place, or a regeneration completes before it. |
| I3 | Recovery closure: U(x) includes **shadow uses**, meaning replays that a recovery policy may perform until the protected region commits. |
| I4 | Dependency pinning: if y is to be recomputed or uncomputed at time t_y, every input that step needs is covered at t_y; regeneration dependencies are acyclic. |
| I5 | Boundary respect: no uncompute path crosses a HARD edge; recompute across HARD/SOURCE_BOUND obeys the grade rule; SOFT residuals stay within tolerance. |
| I6 | Accounting: every information-destroying step is an explicit erase event with a bound on bits destroyed; every uncompute has a residual bound, and residue above tolerance is followed by an accounted erase. |
| I7 | Failure-domain independence: a checkpoint or replica insures a fault class only if it lies outside that class's failure domain. |

**Effective death.** `eff_death(x | Π) = max( last normal use, last shadow use, max over dependents y with fate(y) ∈ {recompute, uncompute} of the regeneration time of y )`.

**Consequence.** Lifetimes are not an input to fate selection. Fate of y changes the lifetime of x, and lifetime of x changes what is legal and cheap for y. This mutual recursion is why the problem is a co-determination and not a liveness dataflow fixpoint over a fixed program: fates *rewrite* the program being analysed.

---

## 9. Fate Model

A fate is applied at a release point of a materialization. Fates can be **sequenced** over a state's life (e.g. checkpoint → erase → recompute), so a `destino` value denotes a policy that elaborates to a fate *schedule*.

| Fate | Meaning | Legality preconditions | Main cost terms | Failure mode |
|---|---|---|---|---|
| **retain** | Keep the materialization in place | Capacity at c over Δt; retention technology adequate (hold power, ECC, endurance); reliability ≥ requirement | write + hold(Δt) + read (+ refresh/ECC) | Capacity exhaustion; retention error |
| **move** | Relocate representation-preservingly | Path exists with bandwidth; no domain conversion (a conversion is a `trasforma`) | per-hop energy (optical loss → laser), latency | Bandwidth contention; link fault |
| **checkpoint** | Materialize a recoverable representation at a durable place | Consistent cut over the dataflow (Chandy–Lamport style); durable component outside the insured failure domain; precision ≥ requirement | serialization + durable write + amortized expected restore | Inconsistent cut; same-domain checkpoint |
| **recompute** | Drop now; regenerate later from surviving dependencies | Deps covered at regeneration time (I4); regeneration grade meets consumers' acceptance grades; no SOURCE_BOUND ancestor without a retained/logged source | exec(t) + re-fetch/re-inject deps + **extra dependency holding** + quality risk | Cyclic dependence; grade violation |
| **uncompute** | Remove x by executing a valid inverse | x live; inverse `g_t` defined over the reachable domain; deps live; no HARD edge on the path; residual ≤ ε_clean (else residue erased and accounted); freed resource returns to a defined clean state | exec(t⁻¹) + dependency holding + residual erase + quality risk | Residual garbage; noise accumulation; loss (dB doubles) |
| **erase** | Intentionally destroy | No remaining uses, including shadow uses (I3); not a member of a needed replay frontier | reset/overwrite (+ zeroization, endurance wear) | Erasing something recovery needed |
| **auto** | Solve the fate problem | All of the above | (see §17) | Solver misestimation |

**No fate dominates.** Illustrative regimes [H]:

- *retain* wins with short reuse distance, cheap hold (SRAM), expensive regeneration, high fault cost.
- *recompute* wins with long reuse distance, cheap transform, dependencies retained anyway (pinning cost ≈ 0).
- *checkpoint* wins for SOURCE_BOUND or expensive, fault-exposed states.
- *move* wins when storage is cheaper elsewhere and bandwidth is idle.
- *uncompute* is hypothesized to win where erase or domain re-entry is expensive (endurance-limited persistent state; keeping a field coherent to avoid a DAC+modulator round trip) and the transform is invertible and SOFT.
- *erase* wins when state is dead, unneeded by recovery, and reset is cheap.

**Break-even sketch.** With `λ_S` the shadow price of storage at c (a Lagrange multiplier from the capacity constraint):

```text
retain iff  E_w(c) + E_hold(c,Δt) + E_r(c) + λ_S·size·Δt  ≤  E_exec(t) + E_reinject(deps) + E_pin(deps) + E_risk
```

When capacity binds, `λ_S > 0` and greedy local decisions are wrong; a global solver is required. This is the compiler's job in `destino = auto`.

---

## 10. Reversibility and Irreversibility

### 10.1 Terms that must not be conflated

| Term | What it is | Kind | Acts on | Requires |
|---|---|---|---|---|
| **Reversible transformation** | `t` has an inverse `g` over the *relevant (reachable) domain*: `g(t(a)) = a` for all reachable `a` | Property of a transformation | Transform | Domain knowledge, not injectivity over the whole type |
| **Reversibility** | The property above (and its numerical/physical variants, §10.2) | Property | Transform | — |
| **Uncompute** | *Executing* `g` to remove x (garbage/ancilla) and return its resource to a clean state | Action | State | x live; deps live; `g` legal on the path |
| **Uncomputation** | The lifetime/fate *strategy* of using uncompute for a state | Fate | State at release point | I4, I5, I6 |
| **Recompute** | Regenerating a dropped x *forward* from surviving deps | Action | State | Deps covered at regeneration time |
| **Erase** | Destroying x without regard to correlations with survivors | Action | State | No remaining uses (incl. shadow) |

Uncompute and recompute use the same dependencies in opposite temporal roles. Recompute *creates* x after it is gone. Uncompute *destroys* x using an inverse while its inputs are live. Erase needs no inverse and no live dependencies, which is why it can destroy information.

The domain point matters: `x → (x, f(x))` is injective on the reachable set even if `f` is not injective on its type. Reversibility is relative to the *reachable* domain, so the compiler needs reachability facts (shape, range, provenance), not just type signatures.

### 10.2 Mathematical invertibility ≠ physical reversibility

Each transform carries three separate attributes:

| Tier | Question | Example: optical unitary mesh | Example: photodetection + ADC |
|---|---|---|---|
| **L (logical)** | Does an inverse exist over the reachable domain? | Yes (adjoint of a unitary) | No: phase discarded in direct detection; quantization is many-to-one |
| **N (numerical)** | Is `g∘t ≈ id` within ε at finite precision? | Bounded by phase-control precision and calibration | No |
| **P (physical)** | What fraction η of information (or SNR) is lost per traversal? | η > 0: attenuation, scattering, noise | η = 1 for the lost parts; fresh noise added |

`bnd(t)`: **NONE** (digital reversible kernel), **SOFT(η)** (lossy/noisy but approximately invertible with quantified SNR cost), **HARD** (many-to-one or entropy-injecting: quantization, photodetection, ReLU-type nonlinearities, argmax).

### 10.3 The irreversibility boundary

```text
optical field E ──mesh──▶ E'  ──photodetect──▶ photocurrent I ──ADC──▶ quantized q
 κ = TOLERANT(ε)   SOFT(η)    HARD #1 (phase lost)               HARD #2 (quantized)   κ = SOURCE_BOUND / DISTRIBUTIONAL
```

**Compiler rules.**
1. An uncompute path may not contain a HARD edge.
2. It may contain SOFT edges only if accumulated residual (1−η_total) ≤ ε_clean; otherwise the residue is erased and accounted (I6).
3. Recompute across a HARD edge yields a *different realization* (fresh noise): the regeneration grade drops to DISTRIBUTIONAL or SOURCE_BOUND.
4. States after the boundary can be **checkpointed exactly** (digital, ECC) but never uncomputed back to the optical field.

### 10.4 Uncompute vs erase: the conditional-entropy criterion

Landauer's bound for resetting an unknown bit is k_B·T·ln 2. With access to correlated side information M, the minimal work to reset register X generalizes to k_B·T·ln 2·H(X|M) [E; thermodynamics of information, e.g. del Rio et al. 2011 and review literature]. Applied to compilation:

- If X is a deterministic, invertible function of surviving state (H(X|M) = 0), a dissipation-free reset exists in principle: run the inverse. **Uncompute is legal.**
- If X carries fresh entropy relative to survivors (an ADC noise realization, a sensor sample), H(X|M) > 0. No reversible clean-up exists. Legal fates: retain, checkpoint, move, erase.

Compiler proxy: static functional dependence. X ∈ FD(surviving states) through transforms with defined inverses.

### 10.5 Landauer is not the business case [E + A]

k_B·T·ln 2 ≈ 2.9 zJ at 300 K. Realistic per-bit costs here are fJ to pJ (conversion, SRAM, HBM) [A], i.e. 6–9 orders of magnitude above the floor. Therefore the case for uncompute **cannot** rest on thermodynamics. It must rest on:

1. **Capacity–time trade** (reversible pebbling: space reduced at the price of extra operations).
2. **Endurance/write cost** of persistent state (HZO).
3. **Domain re-entry avoidance** (staying coherent instead of paying ADC + DAC + modulator).
4. **Adiabatic/reversible CMOS partners**, if they materialize. Company-reported proof-of-concept results for adiabatic reversible logic (about 30% less energy than a conventional chip on a test task, from press coverage) show the hardware class exists; whether it changes fate economics here is [Q].

---

## 11. Recovery Model

### 11.1 Fault taxonomy

| Fault | Information destroyed? | Detection | Topology/recovery response | Lifetime requirement it creates |
|---|---|---|---|---|
| Link failure | In-flight data on that link | Missing light/heartbeat, BER | Reroute via spare path; remap flows | Sender keeps source materialization until acknowledged |
| Node failure | All materializations at the node | Heartbeat, ECC | Remap to spare; restore checkpoint; replay from frontier | Checkpoint or regenerable upstream, in an independent failure domain |
| Token/packet corruption | Corrupted bits | CRC/ECC | Retry/retransmit; replay | Retain until verified |
| Phase/thermal drift | None directly, but the realized transform is wrong and the error is **silent** | Pilot tones, residual monitoring | Recalibrate (control loop), then replay the affected window | Outputs since the last verified calibration stay *uncommitted*, so their inputs live until verification |
| Photon loss/excess attenuation | **Yes**: SNR physically lost | Power monitors, SNR estimate | Only re-execution from an upstream surviving materialization, or lower-loss routing for the future | Upstream input must survive until downstream is validated |
| Memory failure (SRAM/HBM/HZO) | Bits in failed cells | ECC, scrubbing | ECC, remap, restore, replica; HZO weights re-programmed from HBM master | HBM master copy acts as checkpoint of HZO state |
| ADC error | **Yes**: bad digital state at a HARD boundary | Range checks, calibration, redundancy | Re-run optical stage from retained modulated input; redundant conversion | Optical-stage input retained until ADC output validated |

### 11.2 Division of responsibility

> **Topology handles recovery of computation and dataflow. Reversible computing (the lifetime machinery) handles the lifetime and disposal of information.**

They meet at one interface:

- Recovery **consumes survival guarantees**: replay needs a *replay frontier* of materializations (or regenerable states) that outlive the fault window.
- Lifetime **consumes recovery obligations** as shadow uses (I3).

Topology cannot recover what physics destroyed (absorption, scattering, noise, quantization). Such recovery always comes from an *earlier* surviving materialization, which is a lifetime decision.

### 11.3 Recovery–lifetime consistency rules

| Rule | Statement |
|---|---|
| RLC1 | Every replay frontier member has `eff_death` ≥ commit time of its region |
| RLC2 | Recompute-based recovery requires regeneration grade ≥ consumers' acceptance grade, or replay changes results |
| RLC3 | A checkpoint outside the failure domain of the insured fault class (I7) |
| RLC4 | Replicas and redundancy count as materializations in storage, energy and bandwidth |
| RLC5 | Silent faults (drift) require *delayed commit* windows, which lengthen lifetimes |

Prior art on the underlying tradeoff includes lineage-based versus checkpoint-based recovery in dataflow systems, optimal periodic checkpoint intervals (Young/Daly), and consistent snapshots (Chandy–Lamport) [E, from background knowledge; citations to verify].

---

## 12. Constraint Model

`vincolo` is a predicate over plan metrics. A plan satisfies it when the metric holds under the backend's characterization uncertainty at a stated confidence.

| Class | Examples | Kind | Model supplied by |
|---|---|---|---|
| Resource | SRAM/HBM capacity, bandwidth, laser budget | Hard | Component description |
| Performance | latency, throughput, tail latency | Hard or soft | Cost model |
| Energy/thermal | wall-plug energy, power cap, thermal limit | Hard or objective | Cost model + backend |
| Quality | precision, SNR, max error | Hard or probabilistic | Backend noise/error model |
| Reliability | `P(error > ε) < δ`, MTTF, recovery time | Probabilistic | Fault model |
| Physical | optical loss budget, drift budget, endurance budget | Hard | Backend |

Objectives are soft `vincolo` (`vincolo minimize energy`), so no tenth concept is needed. Backends export **characterization models with uncertainty intervals**, and the compiler can plan in *expected* or *conservative* mode.

---

## 13. Language Philosophy

### 13.1 Progressive disclosure

| Level | Who | What they write | What the compiler does |
|---|---|---|---|
| 1 | Ordinary builder | Familiar dataflow code, no lifecycle words | Elaborates each value to `stato { duration = inferred, destino = auto }`, infers `trasforma`, `flusso`, defaults for `recupero` |
| 2 | Advanced builder | `duration`, `destino` hints, `vincolo`, `recupero` policies, precision | Respects constraints and pins; explains plan |
| 3 | Expert | Topology, placement, explicit inverses, boundary and grade declarations, pinned fates | Verifies legality; refuses illegal pins with reasons |

### 13.2 Design rules

1. **Fate-transparent semantics** (§6.2).
2. **Defaults work**: Level 1 must capture most of the gain (T5).
3. **Explain plan**: the compiler reports each fate, cost breakdown and the reason the alternatives lost (like SQL `EXPLAIN`). Builders will not trust `auto` without it.
4. **Illegal pins are compile errors** with a stated physical reason.
5. **Familiar surface**: Rust/Python/Halide-like; the Italian names appear as canonical primitive keywords and IR node names, while everything around them stays English. Nothing in the formal core depends on the language of the names.

### 13.3 Philosophy filter

Rule: *if a metaphor cannot produce a machine-checkable mechanism, it stays outside the formal core.*

| Idea | Mechanism extracted (if any) | Verdict |
|---|---|---|
| Aristotle, potentiality/actuality | Regenerable-but-absent (potential) vs materialized (actual): separates information object from materialization | **Used** (§6) |
| Bergson, duration vs clock time | Validity as semantic staleness (version distance, change), not only wall-clock liveness | **Used** (`valid`) |
| Cybernetics, feedback | Calibration/drift loops as `recupero` with stability and latency bounds | **Used** (§11) |
| Leibniz, identity by sufficient reason | Identity by lineage: `id(x) = hash(transform, input ids)`, enabling equivalence of regenerated values | **Candidate** [I] |
| Heraclitus, flux | Versioned immutable information objects | Already SSA; no new mechanism, **decorative** |
| Stoicism, accepting what is not in our power | "Do not plan recovery through destroyed information" | Already physics; **decorative** |
| Daoist flow, music, choreography, film, improvisation, phenomenology | None found | **Excluded** from the formal core |
| Pragmatism | Truth tested by measurable effect | Methodology: it is §20–§21, not syntax |

---

## 14. Example Programs

Syntax is illustrative, not final.

### 14.1 Level 1: no lifecycle words

```text
system Beamformer(fabric: Fabric) {
    signal   = sensor.read<tensor<f16>>()
    weights  = load("weights.bin")
    result   = beamform(dft(signal), weights)
    emit result
}
```

The compiler infers every `stato`, `trasforma` and `flusso`; sets `destino = auto`; applies platform-default `recupero`; no `vincolo` means best effort.

### 14.2 Level 2: lifecycle and constraints

```text
system Beamformer {
    componente sensor
    componente optical_fabric
    componente sram
    componente hbm

    stato signal   : tensor<f16> { duration = window(4us), destino = auto }
    stato weights  : tensor<f16> { duration = persistent, precision >= 6b }
    stato spectrum : tensor<c16> { destino = auto }          // reused by adaptive update 3 windows later

    trasforma dft(signal) -> spectrum
    trasforma beamform(spectrum, weights) -> result

    flusso sensor -> optical_fabric
    flusso hbm -> optical_fabric
    flusso optical_fabric -> sram

    recupero optical_fabric = reroute then replay
    vincolo latency < 10us
    vincolo energy < 1mJ        // wall-plug
    vincolo snr >= 20dB
}
```

### 14.3 Level 3: expert declarations

```text
componente fabric   : optical_mesh<SiN, LN> { loss_db = 3.5, wdm = 8 }
componente hzo_bank : hzo_weights { endurance = <measured>, retention = <measured> }

stato signal   : tensor<f16,[64,1024]> { destino = auto, provenance = source_bound }
stato weights  : tensor<f16,[64,64]>   { duration = persistent, home = hzo_bank, master = hbm }

trasforma dft(signal) -> spectrum {
    inverse = idft, bnd = soft(snr_loss_db = 0.8), det = stoch(eps = 1e-2)
}
trasforma detect(result) -> samples { bnd = hard }       // photodetection + ADC

recupero fabric  = reroute(spare_paths = 2) then replay(from = checkpoint)
recupero weights = recalibrate(every = 10ms)
```

### 14.4 What the compiler reports (illustrative numbers, not results)

```text
PLAN beamformer   latency 8.7us < 10us   energy 0.62mJ < 1mJ   snr 21.4dB >= 20dB
state     fate          why
signal    checkpoint    SOURCE_BOUND (sensor sample); needed for replay frontier until window commit;
                        checkpoint to HBM (independent failure domain)
spectrum  recompute     dep `signal` retained by checkpoint; one optical DFT pass cheaper than
                        SRAM hold + two transfers; {signal, spectrum} are one information-equivalence class
weights   retain@hzo    master copy in HBM; rewrite budget respected
result    move->sram    consumed by `detect` (HARD); no regeneration across boundary
samples   retain, then erase after commit   SOURCE_BOUND (ADC realization)
```

### 14.5 What the compiler refuses

```text
error[F-017]: destino = uncompute is illegal for `samples`
   stato samples { destino = uncompute }
   = `samples` is produced by `detect`, a HARD irreversibility boundary (photodetection + ADC)
   = uncompute needs an inverse of `detect` over the reachable domain; none exists
   = legal fates: retain, move, checkpoint, erase (after commit)
```

---

## 15. Intermediate Representation

### 15.1 Structure

| Node/edge | Content |
|---|---|
| **State** | id (lineage-derived), τ, π, κ, V |
| **Transform** | dom/cod, det, `inv` (partial inverse + reachable-domain predicate), `bnd`, realizations, error model, cost functions |
| **Component** | capabilities, capacity, hold/write/read costs, endurance, failure domain, **fate-availability row** (§18) |
| **Flow** | channel, bandwidth, multicast, ordering, loss, fault domain |
| **Materialization** | (state, component, representation, interval): the object fates act on |
| **Fate event** | release-point decision with legality witness |
| **Recovery region** | subgraph, policy, frontier, commit point |
| **Constraint** | predicate over metrics, with scope and confidence |
| **Equivalence class** | states related by invertible transforms (retain any one, derive the others) |

Lowering levels: L0 fate-free semantic graph → L1 lifetime-annotated → L2 fate-decided → L3 placed and routed → L4 execution plan. A small **independent plan verifier** checks I1–I7 on L2–L4.

### 15.2 What this IR represents that conventional IRs do not make first-class

| Concept | SSA/LLVM | Dataflow graph | MLIR + bufferization | Halide/TVM schedule | Ownership/linear types | This IR |
|---|---|---|---|---|---|---|
| Value identity independent of location | Yes (values), no places | Yes | Tensor yes; memref conflates | Partial | Ownership ≈ identity | Yes |
| Several materializations of one value | No | No | No | Partial (`cache_read/write`) | No | **Yes** |
| Recompute vs store as a decision | No | No | No | **Yes** (`compute_at`/`store_at`) | No | Yes, **with legality** |
| Regeneration legality (determinism, provenance grade) | No | No | No | No | No | **Yes** |
| Inverse on the *reachable* domain; uncompute | No | No | No | No | No | **Yes** |
| Irreversibility boundary (information destroyed) | No | No | No | No | No | **Yes** |
| Recovery obligations as uses | No | No | No | No | No | **Yes** |
| Failure domain of storage | No | No | No | No | No | **Yes** |
| Staleness/validity | No | No | No | No | No | **Yes** |
| Physical cost/uncertainty hooks | No | No | Partial (cost models) | Partial (auto-schedulers) | No | **Yes** |
| Fate as a decision variable | No | No | No | Partial | No | **Yes** |

Honest reading: rows 2–3 and 10 have partial precedent. The distinctive rows are 4–9: regeneration grades, reachable-domain inverses, irreversibility boundaries, recovery-as-use, failure domains, validity. This IR is not a renamed SSA: SSA derives liveness from a fixed program and has no notion of regenerability, destruction, or recovery. It is also not incompatible with MLIR; it could be hosted as dialects [I].

---

## 16. Compiler Architecture

### 16.1 Pipeline (the brief's pipeline, with corrections)

```text
source → parse → semantic analysis → information graph (L0)
       → dependency analysis
       → boundary analysis (reversibility + irreversibility: one analysis, two outputs)
       → lifetime inference
       ┌──────────────── fixpoint loop ────────────────┐
       │ fate selection ⇄ placement ⇄ routing ⇄ recovery planning │   cost model is a service to all
       └───────────────────────────────────────────────┘
       → re-costing → plan verifier (I1–I7) → execution plan → backend
```

**Corrections to the brief.**
- Reversibility and irreversibility analysis are one boundary analysis.
- "Physical cost optimization" cannot be a late stage: costs drive fate selection from the start. The final step is *re-costing* with placement and routing known.
- Fate, placement, routing and recovery are mutually dependent, so the middle is a fixpoint with convergence criteria, not a sequence.

### 16.2 Solver options [I]

| Setting | Candidate |
|---|---|
| Chains with skips | Dynamic programming (revolve-style) |
| Small/medium DAGs | MILP (Checkmate-style) |
| Reversible pebbling fragments | SAT (Meuli et al. style) |
| Dynamic/data-dependent | Online heuristics (DTR-style), bounded plan switching |

Related pebbling variants are known to be computationally hard (black pebbling and reversible pebbling are PSPACE-complete; red-blue variants are hard too [E, background; verify]). Exact solutions for general graphs are not the goal; characterizing tractable structured subclasses is [Q].

### 16.3 The verifier is the first thing to build

The solver may be heuristic. The legality checker must not be. A small trusted verifier of I1–I7 (translation-validation style) is what makes "compiler-checkable" real, and what lets experiments say a plan is *sound* independently of the planner.

---

## 17. Cost Model

### 17.1 Objective

```text
minimize   E_wallplug(Π) + Σ penalties         over fate schedules, placement, routes, recovery plans
subject to latency, storage_c(t) ≤ cap_c, bandwidth, quality (precision/SNR), reliability,
           optical loss budget, thermal, endurance, control overhead,  I1–I7
```

`destino = auto` means: solve this problem.

### 17.2 Terms

```text
E_wallplug = Σ_t [E_exec(t) + E_ctrl]                      transforms (optical or digital)
           + Σ_flow E_move                                  incl. loss → laser power
           + Σ_cross E_cross                                DAC+modulator in, detector+TIA+ADC out
           + Σ_mat [E_write + E_hold(c,Δt) + E_read]        retention (+ ECC/refresh)
           + Σ_ckpt E_ckpt + E[E_recover]                   checkpoint + expected recovery
           + E_static (thermal tuning, idle) + E_meta       fate/metadata overhead
E[E_recover] = Σ_f λ_f · T · (E_detect + E_reroute + E_replay(f))
P_laser      = P_min(bits, SNR) · 10^(L_dB/10) / η_wallplug    (P_min grows ~exponentially with bits)   [E physics, A parameters]
```

Per-fate costs:

| Fate | Dominant extra terms |
|---|---|
| retain | write + hold + read + λ_S·size·Δt |
| move | per-hop loss/energy; conversions are separate |
| checkpoint | serialization + durable write (+ endurance share) + restore·P(fault) |
| recompute | exec + re-injection + **dependency pinning** + risk |
| uncompute | exec(t⁻¹) (optical: loss doubles in dB) + pinning + residual erase + risk |
| erase | reset (+ zeroization, endurance wear: `E_w + λ_end/N_endurance`) |

### 17.3 Regime ratios

- ρ_R = E_recompute / E_retain
- ρ_U = E_uncompute / (E_erase + E_recompute-if-needed)
- Reuse distance vs hold cost
- φ = fault rate × replay cost

Uncompute is only preferred when ρ_U < 1 **and** no other constraint binds. The experiment maps where this occurs.

### 17.4 Rules for hardware claims

- **System boundary:** everything drawing from the accelerator's supply rails: lasers (at wall-plug efficiency), thermal control, modulators, DAC/ADC/TIA, control CMOS, calibration, SRAM/HBM, interface. Cooling/PUE reported separately.
- **Unit:** energy per correct task output at matched quality and throughput, not TOPS/W of a MAC array.
- Parameters carry intervals; plans are produced in expected and conservative modes.

---

## 18. Hardware Mapping

### 18.1 Division of labour

| Domain | Primarily responsible for |
|---|---|
| Photonics | Linear transforms, broadcast/multicast, WDM, high-throughput dataflow, selected movement/compute patterns |
| CMOS | Control, branching, nonlinearity, ADC/DAC, calibration, ECC, scheduling, irregular operations, digital/reversible kernels where appropriate |
| Optical network/topology | Part of the computational and reliability model, not a passive interconnect |

The mapping states what each side *can* do. *Whether* a transform should run optically is decided by the cost model (F1), not assumed.

### 18.2 Fate-availability matrix (physical, per component) [A: to be validated by specialists]

| Component | retain | move | checkpoint | recompute | uncompute | erase |
|---|---|---|---|---|---|---|
| Optical fabric (SiN) | ns–µs only | **Yes** (routing) | No (must convert) | Yes (re-run transform) | Yes in principle, if coherent, SOFT, within loss budget | Absorb (free but destroys SNR) |
| Modulator (LN) | No | Pass-through | No | Re-inject | n/a | n/a |
| HZO bank | **Yes** (persistent; write-limited) | Rewrite only | Possible (low priority) | n/a | Costly (rewrite) | Overwrite (endurance cost) |
| Detector (Ge) + ADC | No | n/a | n/a | n/a | **No** (HARD) | n/a |
| SRAM | Yes (volatile, capacity-bound) | Yes | Not durable | Yes | Digital reversible kernels only | Cheap reset |
| HBM | Yes (bulk) | Yes (bandwidth cost) | **Yes** (natural tier) | Yes | Digital reversible kernels only | Cheap reset |
| CMOS control | Registers | n/a | n/a | n/a | n/a | n/a |

Conversions (E/O: DAC + modulator; O/E: detector + TIA + ADC) are `trasforma`s hosted by components, carrying their boundary grade.

---

## 19. Novelty / Prior-Art Boundary

*Scope note: this is based on targeted searches plus background knowledge, not a systematic review. Systematic review is Work Item 0 (§23). Novelty statements are conditional on it.*

### 19.1 Area-by-area

| Area | What exists | Overlap with this project | Delta |
|---|---|---|---|
| SSA | Values, def-use, derived liveness | `stato`, birth/uses | No regenerability, destruction, recovery, or location semantics |
| Dataflow programming | Graph execution, actors, streams | `flusso`, `trasforma` | No fate/lifecycle decisions |
| Linear/affine types, ownership, borrow checking | Use-once, aliasing control, deterministic drop | Lifetime discipline | Decide *when* to release, not *whether to regenerate/uncompute/checkpoint*; no cost model |
| RAII, region inference, GC | Scope/reachability-based release | `destino = erase` | Single implicit fate; no costs |
| Compiler liveness, register allocation, spilling, rematerialization | Optimal liveness, spill vs recompute | retain/move/recompute | Single memory level; deterministic ops; no physics |
| Memory planning/bufferization (XLA, MLIR) | Buffer assignment, dealloc placement | Capacity constraint | After-the-fact; no regeneration legality |
| Halide, TVM/TensorIR | Algorithm/schedule split; `compute_at`/`store_at` recompute-vs-store | **Closest on recompute vs store** | No uncompute, boundaries, recovery, validity |
| Tensor rematerialization (Checkmate, DTR, POET, Moccasin) | Optimal/online recompute (MILP, heuristics), some with paging/offload | **Closest planner**: retain/move/recompute/checkpoint under memory caps | No uncompute; no irreversibility typing; recovery separate; deterministic-op assumption |
| Checkpoint/recovery (Chandy–Lamport, Young/Daly, lineage) | Consistent snapshots, optimal intervals, lineage vs checkpoint | `recupero`, `checkpoint` | Not coupled to fate selection or boundary typing |
| Reversible computing, Bennett uncomputation, pebbling | Reversible languages, Bennett trade-offs, reversible pebble game; SAT-based clean-up strategies | uncompute, I4 | Whole-program reversibility or quantum ancilla; no per-state multi-fate choice with erase/checkpoint/recompute; no physical-grade typing |
| Quantum uncomputation languages (Silq, Unqomp, Reqomp, Qutes) | Safe/automatic uncomputation; Qutes (2026) adds lifetime-guided uncomputation | **Closest lifetime + uncompute** | Quantum, no-cloning constraints; uncomputation as correctness device on fixed dataflow; no heterogeneous classical fabric, cost-driven multi-fate choice, or recovery |
| Approximate/reliability-aware languages (EnerJ, Rely, background) | Typed approximation and reliability | Regeneration grades | Not tied to recompute/uncompute legality |
| Explicit-memory-hierarchy models (Sequoia, Legion) | Programmer/mapper control of placement | Placement | No lifecycle legality |
| Accelerator DSLs, HLS, HDLs (Spatial, Bluespec, Chisel) | Explicit memories/registers | retain/move by construction | Fates are manual, never optimized or checked |
| Photonic compilers | Industry MLIR-based stacks lowering PyTorch graphs; ONN mapping tools | Hardware target | Public material describes lowering and architecture, none I found treats lifecycle jointly (limited search) |

### 19.2 The five-way classification

1. **Already exists:** all six fates individually; recompute-vs-store as schedule (Halide/TVM); optimal rematerialization with offload (Checkmate, DTR, POET); uncomputation as language feature (quantum); reversible pebbling (Bennett, Meuli et al.); checkpoint/lineage recovery; typed approximation.
2. **What the project combines:** the six fates in one cost-driven problem on heterogeneous analog–digital hardware with recovery and irreversibility in the same model.
3. **Plausibly different [H]:** (a) regeneration grades and boundary grades *typed* so legality is checkable across analog–digital crossings; (b) recovery obligations as shadow uses, making lifetime co-determined with fate; (c) the conditional-entropy criterion as a compiler legality rule separating uncompute from erase; (d) information-equivalence classes under invertible transforms (choose which representation to retain).
4. **Merely vocabulary:** `componente` ≈ resource, `stato` ≈ value, `trasforma` ≈ op, `flusso` ≈ edge/channel, `vincolo` ≈ constraint/SLA, `durata` ≈ liveness interval, `recupero` ≈ fault-tolerance policy. `destino` is partly new: the *decision variable with six values* is the part with content.
5. **Publishable candidates:**
   - C-A: *A fate calculus for heterogeneous analog–digital dataflow with typed irreversibility and regeneration grades* (soundness vs fate-transparent semantics).
   - C-B: *Lifetime–recovery co-determination* (shadow uses; joint planning).
   - C-C: An *empirical regime map* showing where uncompute, recompute, retain, checkpoint are optimal. Either outcome is publishable: a positive map yields a planner; a negative one shows when uncompute is dominated, which is useful to the reversible-computing community.

### 19.3 Verdict and the smallest change that strengthens it

**As currently defined ("first-class information lifetime"), the contribution is insufficiently novel.** Stated at that level it restates liveness plus rematerialization.

**Smallest semantic change:** redefine `destino` from "what happens after death" to "a release-point decision whose legal values are computed by a typed legality calculus over *regeneration grade* and *irreversibility grade*, and whose lifetime effects feed back into dependencies and recovery." Concretely: make κ (regeneration grade) and `bnd` (boundary grade) part of the types of `stato` and `trasforma`, and make recovery obligations part of `U(x)`. This requires no ninth primitive and turns vocabulary into a checkable calculus.

---

## 20. Killer Experiment (KE-1)

**Question.** At matched quality, throughput, fault rate, precision, capacity and workload, does a planner with {uncompute, boundary typing, recovery coupling} beat a state-of-the-art-style rematerialization/offload planner and fixed strategies, and which of the three additions earns its keep?

### 20.1 Core comparison (from the brief)

```text
Conventional:  compute → retain/store temporary → use → erase/release
This model:    compute → use → {uncompute | recompute | erase | move | checkpoint} per compiler decision
```

### 20.2 Workloads

| ID | Workload | Why |
|---|---|---|
| W-S | **Synthetic chain-with-reuse graphs**: n = 16–256 stages; each stage invertible-linear (NONE/SOFT) or HARD; reuse distance d; state sizes s_i | Controls the parameters that generate the fate regimes |
| W-B | **Beamformer with delayed adaptive update** (the brief's example): ADC front end → DFT (invertible) → beamform → detect (HARD) → decision → weight update reusing an earlier spectrum | Real signal-processing structure; maps to the optical cost model |
| W-R | **RevNet-style forward/backward**, digital only, real hardware | **Positive control**: reproduces the known benefit of invertible blocks vs storing activations; tests solver validity and numerical (tier N) inversion drift |

### 20.3 Arms

| Arm | Description |
|---|---|
| A0 | Conventional: retain all temporaries to last use, then release; recovery = periodic checkpoint (Young/Daly interval) |
| A1a/b/c | Fixed: retain-all / recompute-all-possible / offload-all |
| A2 | **Rematerialization/offload planner** (Checkmate-style MILP): {retain, move, recompute, checkpoint}; no uncompute, no boundary typing (all ops deterministic), recovery independent |
| A3 | Full model |
| A3−u, A3−b, A3−r | Ablations: no uncompute / no boundary typing / no recovery coupling |

### 20.4 Matched conditions

Quality contract (end-to-end error ≤ ε or SNR ≥ X dB with probability ≥ 1−δ); throughput target; identical fault process and seeds (link, node, token corruption, drift, photon loss, memory, ADC); identical bit widths; identical per-level capacity caps; identical input seeds.

### 20.5 Metrics

Wall-plug energy (modeled for optical, measured for digital); latency (mean and p99); memory traffic (bytes per level); peak temporary storage per level; recovery cost (energy + latency per injected fault); recomputation energy; uncomputation energy; quality violations; solver time and metadata overhead.

### 20.6 Controls

- **Positive control:** W-R must show the solver choosing invertible blocks (uncompute/recompute) when storage is capacity-infeasible.
- **Negative control:** a graph in which every stage is HARD must yield **zero** uncompute fates; any appearance is a soundness bug.
- **Soundness tests:** (i) the independent verifier rejects 100% of mutation-seeded illegal plans; (ii) A3 has zero contract violations under fault injection; (iii) A3−b produces violations on boundary-heavy graphs (otherwise boundary typing is unnecessary and T2 fails).

### 20.7 Calibration

Digital arm: measured via microbenchmarks (power counters). Optical arm: parametric, with every dominant parameter swept ±10× around literature ranges: laser wall-plug efficiency, path loss, ADC ENOB/FoM, DAC and modulator energy, HZO write energy and endurance, SRAM/HBM energy per bit, fault rates. Report one-at-a-time sensitivity and a regime map in (ρ_R, ρ_U, reuse distance, φ) space. **All thresholds below are [A] and must be frozen before the first run.**

### 20.8 Decision rule (pre-registered, proposed)

| Outcome | Condition |
|---|---|
| **Soundness gate (must pass first)** | Controls in 20.6 pass |
| **Thesis supported** | On ≥ 2 of 3 workloads, A3 beats A2 by ≥ 10% wall-plug energy, or ≥ 25% peak temporary storage at energy within ±3%, within the *plausible* parameter region (fixed a priori from literature), at matched quality; ablations show each of uncompute, boundary typing, recovery coupling contributes |
| **Thesis supported in reduced form** | Gains come from boundary typing and/or recovery coupling but not uncompute, so the model is five-fate and uncompute becomes optional |
| **Thesis falsified** | A3 within ±5% of A2 across the plausible region; or the best fixed strategy is within 5% of A2 (the problem is trivial here); or the benefit exists only outside the plausible region; or solver/metadata overhead exceeds the gain |

**Stage order.** Stage 0, digital-only with measured energy (W-R + W-S): if the calculus cannot beat A2 here, stop and reframe before modeling photonics. Stage 1: add the optical cost model and W-B. No parser, chip design, or photonic hardware is required: just the graph IR, the verifier, a cost-model simulator, an off-the-shelf MILP solver, and a fault injector.

---

## 21. Falsification Criteria

| Claim | **Fails if** | Metric | Consequence |
|---|---|---|---|
| **F1 Photonics** | Laser (wall-plug) + loss + thermal tuning + modulators + DAC/ADC/TIA + memory movement + control energy ≥ best-available electronic baseline at matched quality and throughput | Energy per correct task output, whole system | Hardware premise fails; the compiler idea is then retested on other heterogeneous machines, but not silently |
| **F2 Reversible computing** | `E_uncompute + ΔL·P_idle > E_retain(write+hold+read) + E_erase` over the same interval, for all states, across the plausible region | Per-state break-even ratio ρ_U | Remove uncompute from the fate set |
| **F3 Topology/recovery** | `E_redundancy + E_reroute + E_ckpt + E_restore` > expected loss avoided (`λ·E_rework` or availability penalty); or no gain over Young/Daly periodic checkpointing | Expected recovery cost; availability | Recovery coupling (T3) fails; keep topology recovery, drop joint planning |
| **F4 Persistent optical state (HZO)** | Endurance < writes needed over lifetime; retention < required hold time at operating temperature; level count/stability < required bits; write energy/time over budget; thermal crosstalk beyond calibratable; added loss. *Sources found show ~10⁴ s persistence only and ~40 pJ switching in one device, so these are live risks* | Endurance, retention, bits, write energy, drift | HZO relegated to quasi-static configuration, or replaced; do not alter stack without evidence |
| **F5 Compiler model** | Metadata + solver + analysis complexity exceeds benefit: solver time explodes; plan explanations fail; Level-1 programs capture < 80% of Level-3 gain (T5) | Solver time vs graph size; annotations per app; gain ratio | Narrow to a verified checker plus library planner |
| **F6 Co-design** | No measurable gain on ≥ 2 real (non-synthetic) workloads | KE-1 outcomes | Thesis reduces to a synthetic curiosity |
| **F7 Main thesis** | (a) KE-1 "falsified" row; (b) fate-frontier collapse: a fixed fate is within 5% of auto everywhere; (c) gains only outside plausible region; (d) irreversibility dominance: > 90% of state bytes cross a HARD edge within 1–2 transforms, so uncompute is inapplicable | As stated | Stop or reframe at the smallest semantic model that survives |

**Hardware claims always use full wall-plug system energy, never isolated component efficiency.**

---

## 22. Open Research Problems

1. **[Q]** Complexity and tractable subclasses of the generalized fate game (chains with skips, series-parallel graphs, bounded treewidth); approximation guarantees.
2. **[Q]** A sound calculus for regeneration grades under stochastic transforms: composition of (ε, δ) contracts through chains and joins.
3. **[Q]** Bounding uncompute residual from analog noise and calibration error; tying SOFT(η) to measurable SNR.
4. **[Q]** Joint fate–recovery optimization with correlated failures and shared failure domains.
5. **[Q]** Phase ordering: convergence and decomposition guarantees for the fate/placement/routing/recovery fixpoint.
6. **[Q]** Cost-model uncertainty: robust plans and when expected vs conservative planning differs.
7. **[Q]** Static plans with contingencies vs runtime fate adaptation under data-dependent control flow.
8. **[Q]** Information-equivalence classes: which representation of an invertible pair to retain (stability, size, noise sensitivity).
9. **[Q]** Security semantics of erase (zeroization) versus optimization freedom.
10. **[Q]** Translation validation for `auto`: how small and trustworthy can the verifier be?
11. **[Q]** Whether adiabatic reversible CMOS partners change fate economics enough to make Landauer-scale accounting relevant.
12. **[Q]** Human factors: can builders understand and trust explain-plans; annotation burden at Level 2.

---

## 23. What Specialists Need to Implement

| Work item | Owner | Deliverable | Acceptance |
|---|---|---|---|
| **WI-0** Systematic prior-art review | PL researcher + architect | Annotated corpus; revised §19 | Each novelty claim confirmed or withdrawn |
| **WI-1** Core calculus | PL researcher | Typed core: states, transforms, grades, fates; legality rules; soundness vs fate-transparent semantics | Proof sketch or mechanized core; I1–I7 formalized |
| **WI-2** IR + verifier | Compiler engineer | IR (standalone or MLIR dialects [I]), L0–L4 lowering skeleton, independent plan verifier | Verifier rejects 100% of mutation-seeded illegal plans |
| **WI-3** Characterization models | Photonics engineer | Per-device tables: loss, noise, calibration drift, laser/modulator/PD/ADC energies, tier-L/N/P grades for each transform, HZO endurance/retention/write energy, all with uncertainty | Sourced or measured; intervals stated |
| **WI-4** Cost model + fate-availability matrix | Computer architect | §17 model parameterized; SRAM/HBM/interface parameters; wall-plug boundary spec | Reproduces published system-level energy breakdowns within stated error |
| **WI-5** Fault model | Reliability engineer | Fault rates, failure domains, detection latencies, recovery costs, replay-frontier semantics | Injector reproducible from seeds |
| **WI-6** Simulator + solver | Compiler engineer + architect | MILP/DP/SAT planners; A0–A3 arms | Runs W-S, W-B, W-R |
| **WI-7** KE-1 execution | Experiment lead | Frozen thresholds, regime map, ablations, report | §20.8 outcome declared |

Dependency order: WI-0 ∥ WI-1 ∥ WI-3 → WI-2, WI-4, WI-5 → WI-6 → WI-7. Gate: WI-7 Stage 0 before any optical modeling effort.

---

## 24. What Must NOT Be Changed Without Evidence

| Fixed element | Evidence required to change |
|---|---|
| Exactly eight primitives, with canonical names | A required concept proven inexpressible via property/type/annotation/contract/analysis |
| Fate-transparent semantics | A concrete case where fate must change meaning, and a contract expressing it |
| Reversible transformation ≠ uncompute ≠ erase; reversibility (property) ≠ uncomputation (fate) | None: definitional |
| Mathematical invertibility ≠ physical reversibility (L/N/P tiers) | A device model showing the tiers coincide |
| Irreversibility boundary is explicit and compiler-visible | None |
| Topology handles dataflow recovery; lifetime handles information disposal | A mechanism by which topology recovers destroyed information (none known) |
| No claim that all computation should be reversible, that reversibility saves energy, or that optics is efficient by default | KE-1 and F1 results |
| Hardware roles: HZO is persistent optical state, not RAM; SRAM transient; HBM bulk; photonics for linear/broadcast/WDM; CMOS for control/nonlinear/ADC-DAC/ECC | F1–F4 failures, specifically |
| Wall-plug system energy for hardware claims | None |
| Surface syntax is non-normative | — (free to change) |

---

## 25. One-Page Specification

**Definition.** A programming model and compiler architecture for classical photonic-CMOS dataflow computers in which information lifecycle is an optimization variable. The compiler decides, per release point of each state, among *retain, move, checkpoint, recompute, uncompute, erase* (`destino = auto`), subject to physical, reliability and resource constraints and a typed legality calculus.

**Primitives (exactly eight).** `componente` (resource) · `stato` (information with identity, type, precision, provenance grade, validity) · `trasforma` (action; carries determinism, inverse, boundary grade) · `flusso` (movement/channels) · `durata` (semantic relevance interval) · `destino` (release-point decision) · `recupero` (fault responses) · `vincolo` (predicate on plan metrics). Everything else is a property, type, annotation, contract, analysis or backend attribute.

**Semantics.** Meaning is defined without fates; a plan is correct iff outputs meet quality contracts against the fate-free semantics under the fault model.

**Lifetime.** `birth ≤ uses ≤ death`, where uses include recovery shadow uses; fates act at *release points*; fate and lifetime are co-determined (dependency pinning). Invariants I1–I7: well-formedness, coverage, recovery closure, dependency pinning, boundary respect, destruction accounting, failure-domain independence.

**Distinctions.** Reversible transformation = invertible over the reachable domain (property). Uncompute = executing the inverse to remove state (action; legal only if the victim is a reversible function of surviving state, H(X|survivors)=0). Erase = destroying information. Recompute = forward regeneration. Mathematical invertibility ≠ numerical ≠ physical reversibility.

**Irreversibility boundary.** Transforms are NONE/SOFT(η)/HARD. No uncompute across HARD. Recompute across HARD downgrades regeneration grade (EXACT › TOLERANT(ε) › DISTRIBUTIONAL › SOURCE_BOUND).

**Recovery.** Topology recovers computation/dataflow; lifetime machinery disposes of information. Topology cannot recover information physically destroyed. Recovery obligations extend lifetimes.

**Compiler.** Information graph → boundary analysis → lifetime inference → fixpoint of {fate, placement, routing, recovery} under a shared cost model → re-costing → independent verifier → plan. Objective: minimize wall-plug energy under latency, storage, bandwidth, precision, reliability, loss, thermal and endurance constraints.

**Hardware.** Si (integration/CMOS), SiN (low-loss guides), LN (E/O modulation), HZO (persistent configuration, not RAM), Ge (detection: HARD boundary), SRAM (transient), HBM (bulk, checkpoint tier). Photonics: linear/broadcast/WDM. CMOS: control/nonlinear/ADC-DAC/ECC/irregular.

**Claims [H].** Fate non-dominance; boundary typing necessary; recovery coupling pays; uncompute non-empty; Level-1 captures ≥ 80% of Level-3 gain.

**Falsifiers.** Photonics loses on whole-system wall-plug energy; uncompute dominated everywhere; recovery overhead exceeds benefit; HZO fails endurance/retention/precision/write budget; metadata exceeds benefit; no gain on real workloads; KE-1 shows A3 within ±5% of the rematerialization planner (A2).

**Next.** WI-0 (prior-art review), WI-1 (calculus), WI-2 (verifier first), WI-3–5 (models), WI-6–7 (simulator, KE-1, Stage 0 digital first).

---

## Sources consulted

Retrieved during this work (October 2026):
- Silq: Bichsel et al., PLDI 2020, https://pldi20.sigplan.org/details/pldi-2020-papers/47/Silq-A-High-Level-Quantum-Language-with-Safe-Uncomputation-and-Intuitive-Semantics
- Unqomp (Paradis et al., PLDI 2021), https://www.research-collection.ethz.ch/handle/20.500.11850/493352
- Qutes, "Reversible Lifetime Semantics for Quantum Programs", arXiv:2603.14538
- Meuli et al., "Reversible Pebbling Game for Quantum Memory Management", DATE 2019, arXiv:1904.02121
- Checkmate (Jain et al., MLSys 2020), arXiv:1910.02653; Dynamic Tensor Rematerialization, arXiv:2006.09616; Moccasin, arXiv:2304.14463 (related-work survey incl. POET)
- Photonic compiler efforts: Q.ANT MLIR-based stack (talk/job postings); Neurophos compiler postings
- Taki et al., "Non-volatile optical phase shift in ferroelectric hafnium zirconium oxide", arXiv:2309.01967; "Silicon Microring Resonator Integrated HZO Ferrophotonic Non-Volatile Memory", ACS Photonics 2025 (https://par.nsf.gov/biblio/10630473)
- Photonic-electronic integrated circuits survey, arXiv:2403.14806; "A Case Study on the Performance Metrics of Integrated Photonic Computing", arXiv:2511.00186; Lightening-Transformer, arXiv:2305.19533
- Vaire Computing Ice River coverage (TechRadar, ScienceNews; company-reported)
- Erasure work with side information: del Rio et al., arXiv:1009.1630; review arXiv:1505.07835

From background knowledge (citations to be verified in WI-0): Landauer 1961; Bennett 1973, 1989; Hong–Kung 1981; Gilbert–Lengauer–Tarjan 1980; Chan 2013; Halide (Ragan-Kelley et al. 2013); TVM; MLIR (Lattner et al.); Legion; Sequoia; Spark RDD lineage; Chandy–Lamport 1985; Young/Daly checkpoint intervals; Griewank–Walther revolve; RevNets (Gomez et al. 2017); Janus (Yokoyama–Glück); EnerJ; Rely; region inference (Tofte–Talpin).
