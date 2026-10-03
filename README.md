# Information-Lifetime Computing: Digital Fate Calculus Prototype (v0.1.0)

A **research prototype** that makes the *fate calculus* of the project's research foundation executable. It is **not** a production compiler, and it
validates nothing about hardware.

- Research foundation: [`docs/research-foundation-v0.1.md`](docs/research-foundation-v0.1.md) (the source of truth for the conceptual model, kept unchanged)
- Implementation specification: [`SPEC.md`](SPEC.md) · Assumptions made along the way: [`OPEN_QUESTIONS.md`](OPEN_QUESTIONS.md)

## What this project is
A small language and toolchain for studying one question from the foundation:

> When should a compiler retain, move, checkpoint, recompute, uncompute, or erase information?

The prototype represents and checks the pieces the foundation identifies as the narrower contribution:

- **Fate calculus**: six fates with explicit legality conditions and reasons.
- **Typed irreversibility and regeneration**: boundary grades (`none`/`soft`/`hard`) and regeneration grades (`exact` > `tolerant` > `distributional` > `source_bound`).
- **Recovery coupling**: recovery regions create *shadow uses* that extend lifetimes.
- **Information lifetime**: birth, uses, death, effective death under dependency pinning.

## What is implemented now
Lexer/parser with located diagnostics · semantic checker (24 negative programs with expected error codes) · Information-Lifetime IR with text graph dump ·
fate-legality engine · abstract cost model with named profiles · exhaustive branch-and-bound planner (optimal *under the abstract model*), plus greedy and
conventional baselines · independent plan verifier · reference interpreter with fault injection · abstract simulator · ablation switches · CLI · 245 tests ·
6 example programs · two model-only experiment scripts.

## What is NOT implemented
- **No physical photonics**, no HZO device simulation, no fabrication model, no hardware measurements of any kind.
- **No production compiler or backend**; not a general-purpose language.
- **No validation of the thesis.** The killer experiment (foundation §20) has *not* been run; no Checkmate-style baseline; no real workloads.
- Omitted foundation concepts: sequenced fates, `valid` (staleness), information-equivalence classes, placement/routing, real failure domains (see `OPEN_QUESTIONS.md`).
- All costs are **abstract model units**. Profiles expose regimes; they are not claims about real machines.

## Quick start
```bash
git clone <this-repository> && cd information-lifetime-computing
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
ilc plan examples/reversible.lang
python -m pytest
```
Requires Python 3.9+; no runtime dependencies. `ourlang` is installed as an alias of `ilc` (the placeholder name used in the project brief).

```text
ilc check    FILE   parse and validate
ilc inspect  FILE   information graph, lifetimes, recovery regions
ilc plan     FILE   legal fates, selected plan, cost, verification
ilc simulate FILE   abstract simulator metrics
ilc run      FILE   execute the plan on the reference interpreter  [--inputs a=1,b=0] [--inject-fault REGION]
ilc profiles        list cost profiles
common options: --profile NAME  --cost-config FILE.json  --planner exhaustive|greedy|conventional  --ablate boundary-typing|recovery-coupling|uncompute
```

## Example
`examples/reversible.lang`:
```text
system Reversible {
    stato a : bit
    stato b : bit
    stato tmp : bit { durata = until(result)  destino = auto }
    trasforma xor(a, b) -> tmp
    trasforma copy(tmp) -> result
    emit result
}
```
`ilc plan examples/reversible.lang` (abridged):
```text
Program valid: Reversible (2 transforms, 4 states, 0 recovery region(s))
Information graph:
a      ──┐
         ├─ [1] xor ──> tmp
b      ──┘
tmp    ─── [2] copy ──> result  (output)
...
  tmp : bit   birth 1, effective death 2
     retain     no   dead temporary: retaining it leaks storage past its death (clean-exit rule, OQ-3) ...
     checkpoint yes  20.04  durable copy written after slot 1; no idle gap: insurance only
     recompute  no   no idle gap: needed in consecutive slots (or never again), so there is nothing to regenerate
   * uncompute  yes  17.09  tmp = xor(a, b) is deterministic and non-lossy (H(x|deps)=0); inverse = re-execution of xor ...
     erase      yes  17.75  no need after slot 2: reset after slot 2 ...
     selected: uncompute; next best: erase (17.75, +0.65)
Selected fates  (planner: exhaustive, optimal under the abstract model; 33 search nodes):
  a -> erase   b -> erase   tmp -> uncompute   result -> retain
Execution plan:
1. [slot 1 exec] xor(a, b) -> tmp
2. [slot 2 exec] copy(tmp) -> result
3. [slot 2 post] uncompute tmp: inverse(xor) with a, b live -> remove tmp
4. [slot 2 post] erase b
5. [slot 2 post] erase a
6. [slot 3 exec] emit result
Cost (abstract model units - not physical measurements):  energy=8.50 storage=13.00 latency=3.50 recovery=0.35
Verification: PASS      (verifier checks P1, I2-I7, C + reference interpreter)
```
**The choice depends on the regime, by design.** `--profile cmos-like` (cheap reset) selects `erase` for `tmp`. With `abstract-default`, reset costs 3x a unit operation, a regime
chosen to make reversible clean-up visible. That shows the planner responds to coefficients; it is not evidence about real machines.

Recovery as shadow use:
```bash
ilc run examples/recovery.lang --inject-fault guard                                  # PASS: frontier kept alive, region replayed
ilc run examples/recovery.lang --inject-fault guard --ablate recovery-coupling       # FAIL: frontier released early, replay impossible
```

## Architecture
```text
Language -> Parser -> Semantic checker -> Information-Lifetime IR -> Fate analysis -> Planner -> Abstract simulator
                                                                                          \-> Verifier / Reference interpreter
```
See [`docs/architecture.md`](docs/architecture.md) for the concept-to-code mapping, plus `docs/semantics.md`, `docs/fate-calculus.md`,
`docs/information-lifetime-ir.md`, `docs/cost-model.md`, `docs/falsification.md`.

## Research status
| Level | State |
|---|---|
| Research hypothesis | The foundation's claims T1-T5 and falsifiers F1-F7: **untested** |
| Formalization | Legality conditions and invariants I1-I7 written down in the foundation; encoded in `fates.py` / `verifier.py` |
| Implementation | Executable digital prototype; tested for internal consistency (245 tests) |
| Simulation | Abstract-unit model only; planner/simulator cross-checked; regime and ablation scripts in `experiments/` |
| Physical validation | **None** |

Novelty is **not** claimed here: the foundation itself states that the idea as first worded is insufficiently novel and that a systematic prior-art review is outstanding.

## Repository layout
`docs/` foundation and design docs · `src/ilc/` implementation · `tests/` (+ `tests/negative/`) · `examples/` · `experiments/` · `scripts/` ·
`SPEC.md`, `OPEN_QUESTIONS.md`, `IMPLEMENTATION_NOTES.md`, `CHANGELOG.md`.

## Known limitations
Straight-line programs of 1-32-bit operations; one fate per state; single durable and bulk tier; exhaustive search is exponential in the worst case (falls back to greedy past a node budget);
fault model is a single injected region fault; costs are abstract. License: MIT.
