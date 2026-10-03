# Information-Lifetime IR

Built by `semantics.check`, consumed by `fates`, `planner`, `verifier`, `interpreter`, `simulator`. Inspect with `ilc inspect FILE`.

| Node | Fields |
|---|---|
| `StateNode` | name, type, bits, index, kind (input/derived), birth slot, `uses`, `consumers`, `accept` grade, `durata_kind/arg/end`, `declared_destino`, `is_output` |
| `TransformNode` | step, `Op`, inputs, output, `regen` grade, `boundary` |
| `Region` | name, members, policy, commit, commit_slot, frontier |
| `Constraint` | dimension, comparison, bound |
| `Machine` / `Component` | role -> component (capacity), flows between roles |

Derived views (`InfoGraph`): `producer`, `deps`, `dependents`, `reverse_topo`, `base_needs(x, recovery=True)`, `lifetime(x)`.

## Edges
- **Dependency**: transform input -> output (`deps/dependents`).
- **Shadow use**: region frontier state -> region commit slot (from `Region`).
- **Pin** (planner-induced): a dependent's uncompute/recompute -> its inputs, at the slot where it runs.

## Lifetime record
`birth`, `uses`, `shadow`, `durata_end`, `death`, `interval = (birth, death)`. A plan adds effective death via pins (`Plan.needs`).

## What this IR makes explicit that a plain SSA graph does not
(Prototype-level claims only; see foundation F§15.2 for the argument.) Regeneration grade and boundary on each transform; recovery obligations as uses;
multiple materializations of one value in a plan (`Schedule.windows` over primary/bulk/durable tiers); fate as a decision variable with legality witnesses.
It is a small, purpose-built graph, not a general IR.

## Rendering
`render_graph` (ASCII blocks per transform), `render_lifetimes` (table), `render_regions`.
