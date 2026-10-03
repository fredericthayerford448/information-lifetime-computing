# SPEC: Implementation Specification (v0.1.0)

Derived from `docs/research-foundation-v0.1.md` (the source of truth for the conceptual model).
For each important concept this document separates:

- **Research definition**: what the foundation says (section references like `F§9`).
- **Implementation representation**: what the code does (module in `src/ilc/`).
- **Validation rule**: how it is checked (checker, verifier, interpreter, or test).

Where the foundation is silent, the smallest prototype behaviour was chosen and recorded in
`OPEN_QUESTIONS.md` (referenced as `OQ-n`). All costs are **abstract model units**, never measurements.

## 1. Scope

Stage 0, digital-only. A program is a straight-line dataflow of bit-vector transforms. There is no
photonics, no HZO model, no production backend. Time is discrete (OQ-1).

## 2. Language

```ebnf
program     = "system" IDENT "{" { item } "}" ;
item        = stato | trasforma | componente | flusso | recupero | vincolo | emit ;
stato       = "stato" IDENT ":" type [ props ] ;
trasforma   = "trasforma" IDENT "(" [ IDENT { "," IDENT } ] ")" "->" IDENT [ props ] ;
componente  = "componente" IDENT props ;                  (* role = primary|bulk|durable, capacity = bits *)
flusso      = "flusso" IDENT "->" IDENT ;
recupero    = "recupero" IDENT props ;                    (* region = [..], policy = replay|restore, commit = state *)
vincolo     = "vincolo" IDENT ("<"|"<=") NUMBER ;         (* energy storage latency recovery peak_storage *)
emit        = "emit" IDENT { "," IDENT } ;
props       = "{" { IDENT "=" value [ "," | ";" ] } "}" ;
value       = IDENT | IDENT "(" value { "," value } ")" | NUMBER | "[" value { "," value } "]" ;
type        = "bit" | "u8" | "u16" | "u32" ;
```
Comments: `//` or `#` to end of line. Declarations are order-significant for transforms only (they run in textual order).

**State properties** (`stato`): `durata = temporary | persistent | until(<state>) | steps(<n>)`;
`destino = auto | retain | move | checkpoint | recompute | uncompute | erase`;
`accept = exact | tolerant(<eps>) | distributional` (acceptance grade for regenerated values; default `exact`).
**Transform properties** (`trasforma`): `regen = exact | tolerant(<eps>) | distributional | source_bound`;
`bnd = none | soft(<eta>) | hard` (may not understate the operation's intrinsic boundary).
Undeclared outputs of a `trasforma` are declared implicitly with the operation's result type.

**Operations** (`src/ilc/ops.py`): `copy not inc xor and or add sub quantize parity`.
`quantize` and `parity` are intrinsically **HARD** boundaries; all others are `none`. All are exact (`regen=exact`).

## 3. Time model (OQ-1)

Slot 0 = inputs loaded; slot k (1..N) = transform k executes; slot N+1 = emit. Each slot has phases
`pre` (restores/regenerations), `exec`, `post` (releases, inverses). `end = N+1+horizon` (config).

## 4. Concepts

| Concept | Research definition | Implementation representation | Validation rule |
|---|---|---|---|
| **Eight primitives** | `F§7` `componente stato trasforma flusso durata destino recupero vincolo` | AST nodes `syntax.py`: `ComponenteDecl`, `StatoDecl`, `TrasformaDecl`, `FlussoDecl`, `RecuperoDecl`, `VincoloDecl`; `durata`/`destino` are state properties | Parser (`E-SYNTAX`), checker; `tests/test_parser.py` |
| **State / information object** | `F§6.1` identity, type, precision, provenance, validity | `ir.StateNode` (name, type, bits, kind input/derived, birth, uses, `accept`, `durata_*`, `declared_destino`, `is_output`). Single assignment. `valid`/staleness not implemented (OQ-12) | `E-DUP`, `E-TYPE`, `E-UNDEF`, `E-DEP` |
| **Transform** | `F§6.1` `t=(dom,cod,det,inv,bnd,...)` | `ir.TransformNode` + `ops.Op`: arity, semantics, `regen` grade, `boundary`, cost weight; `inverse` = re-execution (out-of-place) | `E-OP`, `E-ARITY`, `E-TYPE`, `E-BOUNDARY` |
| **Use** | `F§8` `U(x)` | `StateNode.uses` (slots of consuming transforms); `ir.Need` objects built by `InfoGraph.base_needs` (kinds `use`, `emit`, `durata`, `shadow`, plus planner pins `pin-uncompute`, `pin-regen`) | Verifier I2 (every read finds a resident value) |
| **Lifetime metadata** | `F§8` birth, valid, use, dependency, death | `ir.Lifetime(birth, uses, shadow, durata_end, death)`; `death = max(birth, all need slots)`; effective death in a plan also includes pins | `E-USE-AFTER-DEATH`, `E-LIFETIME`; `tests/test_ir.py` |
| **`durata`** | `F§7-8` interval of semantic relevance | `temporary` (ends at last need), `persistent` (needed through emit slot, only `retain` legal), `until(X)` (relevant until X is born), `steps(n)` (until birth+n); creates a `durata` need at its end | `E-DURATA`, `E-LIFETIME`, `E-USE-AFTER-DEATH` |
| **`destino`** | `F§9` release-point decision, `auto` = optimisation | `StateNode.declared_destino` (None = auto); a pin restricts the planner to one fate | Static pin check `E-FATE-ILLEGAL`/`E-RECOVERY-CONFLICT`; context-dependent illegality is reported by the planner as `E-PLAN` |
| **Release point** | `F§8` correction: end of need for one materialization | Fates are applied at a state's anchors: birth, each need slot, death; *idle gaps* are consecutive anchors with an interior slot | `fates.gaps_of`, `test_fates.py` |
| **Six fates** | `F§9` retain move checkpoint recompute uncompute erase | `types.Fate`; `fates.assess` (legality + reason) and `fates.build_schedule` (actions + residency windows). See `docs/fate-calculus.md` | `test_fates.py`, verifier I2-I7 |
| **Regeneration grades** | `F§6.1` EXACT > TOLERANT(eps) > DISTRIBUTIONAL > SOURCE_BOUND | `types.Grade`, `satisfies()`. Transform `regen`; inputs are source-bound; consumer `accept` | Recompute legal only if `satisfies(regen, accept)`; verifier I5; interpreter detects divergence |
| **Irreversibility** | `F§10.2-3` NONE / SOFT(eta) / HARD; no uncompute across HARD | `types.Boundary`; `ops.Op.boundary`; `bnd` may only strengthen. Uncompute needs `none`, or `soft` with `eta <= eps_clean`, and an exact producer | `assess`, verifier I5, `E-BOUNDARY` |
| **Recovery / shadow use** | `F§11` regions, frontier, commit, recovery as uses | `ir.Region(members, policy, commit, commit_slot, frontier)`; each frontier state gets a `shadow` need at the commit slot (`replay`: must be resident; `restore`: must have a durable copy, so only `checkpoint` is legal) | `E-RECOVERY*`, verifier I3, interpreter fault injection |
| **Constraint** | `F§12` predicate on plan metrics | `ir.Constraint(dim, cmp, value)` (upper bounds only); `componente ... capacity` bounds primary peak storage | Planner (leaf check), verifier `C` |
| **Machine** | `F§18` components, flows | `ir.Machine`: one component per role (primary/bulk/durable), flows by role; implicit default if none declared. `move`/`checkpoint` need the tier and `flusso` both ways | `E-COMPONENT`, `assess` |
| **IR node types / edges** | `F§15` | `StateNode`, `TransformNode`, `Region`, `Constraint`, `Component`; edges = transform inputs/outputs (dependency), region frontier (shadow), pins (planner-induced) | `docs/information-lifetime-ir.md` |
| **Cost dimensions** | `F§17` | `costs.CostVector(energy, storage, latency, recovery)`; weighted objective | `docs/cost-model.md`; planner/simulator agree (`test_simulator.py`) |
| **Planner** | `F§16-17` `destino=auto` solves an optimisation | `planner.make_plan`: exhaustive branch-and-bound (optimal under the model within budget), `greedy` (myopic), `conventional` (baseline); explanations per state/fate | `test_planner.py` (brute-force cross-check) |
| **Interpreter** | `F§6.2` fate-transparent semantics | `interpreter.run_plan`: bit-vector values, three storage tiers, inverse execution, noise for non-exact transforms, fault injection | `test_interpreter.py` |
| **Verifier** | `F§16.3` independent plan checker | `verifier.verify`: P1 completeness, I2 coverage, I3 recovery closure, I4 pinning, I5 boundary, I6 accounting/clean exit, I7 restores, C constraints. Uses only the plan and the IR | `test_verifier.py` (hand-built negative plans) |

## 5. Diagnostics

`file:line:col: error[CODE]: message`. Codes: `E-LEX E-SYNTAX E-UNDEF E-DUP E-TYPE E-OP E-ARITY E-DEP E-DURATA
E-LIFETIME E-USE-AFTER-DEATH E-FATE E-FATE-ILLEGAL E-BOUNDARY E-PROP E-COMPONENT E-RECOVERY
E-RECOVERY-CONFLICT E-CONSTRAINT E-USAGE E-PLAN`. The parser stops at the first syntax error; the checker
collects all semantic errors.

## 6. Interpreter behaviour

Executes plan actions in order on integers modulo 2^bits. Refuses to read a value that is not resident
(`use after release / lost dependency`). `UNCOMPUTE` re-executes the producer with its dependencies live and
requires the result to equal the stored value (otherwise `residual garbage`), then clears the register.
Non-exact transforms add seeded noise **per execution**, so a regenerated value really differs. Outputs are
compared with the fate-free reference semantics. `--inject-fault REGION` corrupts the region's resident
outputs at its commit slot and repairs them by the region's policy.

## 7. Verifier behaviour

Replays residency from the plan's actions and reports each check as PASS/FAIL with messages (see
`docs/falsification.md` for the negative cases). It never calls the planner's legality functions.
