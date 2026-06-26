# Degradation Edges (`degrades_to`) — Slice 3

> **Status:** DESIGN (2026-06-25). The reverse-direction edge-layer slice of the Entity-Graph Ontology v2 build
> (`2026-06-25-entity-graph-ontology-v2.md`). Branch: `feat/entity-graph-ontology`. Builds on the item nodes (slice 1,
> `2026-06-25-node-import-items-slice1-design.md`) and the charge recipes (slice 2,
> `2026-06-25-charge-recipe-edges-design.md`).

## 0. Why this slice

Slice 2 added the **create/refill** direction (`recipe`/`consumes`/`produces`). This adds the **deplete** direction:
`degrades_to`, the downgrade ladder an item walks as it loses charges/durability through use. It's the inverse of
`supersedes` (the *upgrade* ladder) and completes the charge lifecycle's structure. The charge-count variant nodes
already exist (slice 1), so this is mostly edges + a small auto-import.

**Charge lifecycle — the three composable directions over the same variant nodes:**
- **create/refill** = `recipe`/`produces` — slice 2 (done).
- **deplete** = `degrades_to` — **THIS slice**.
- **restore** (the inverse of each terminal) = recharge (`recipe`, done) for `reverts_to`; **repair** (`service` edge) for
  `broken` — **deferred** (§8).

## 1. Decisions (settled in brainstorming, 2026-06-25)

| # | Decision | Choice |
|---|---|---|
| 1 | Data source | **Curated `data/degrade_paths.json`** (editorial, source-grounded, verifier-gated) |
| 2 | Destroyed terminal | a `degrades_to` edge with **`dst=None`** + `data.terminal="destroyed"` (uniform with the node-dst terminals) |
| 3 | Terminal scope | **all three** — `destroyed` (Ring of dueling), `reverts_to` (Amulet of glory, Scythe), `broken` (Dharok's helm) |
| 4 | Ladder | **per-step `degrades_to` edges** through a curated ordered sequence (queryable per intermediate state) |
| 5 | Lifecycle link | **implicit** — `reverts_to` points to the uncharged node, which slice 2's recipe already produces from (shared-node loop) |
| 6 | Edge rekey | `degrades_to` is item-`src` → **folded into a shared rekey with `build_items`' `same_entity` edges** (see §5) |
| 7 | Deferred | repair (`service` edge), degrade-rate/cost-per-use, expeditious bracelet (`per_xp`), other items |

## 2. Model additions (additive ontology extension)

- **`model.py`**: add `EdgeType.DEGRADES_TO = "degrades_to"`.
- **`kg/schema.json`**: add a **new** `edge_kinds.degrades_to` entry (status `live`) — `degrades_to` is **not** in the
  original v2 §3 table (that is `supersedes`, the upgrade inverse), so this is the first *additive* extension to the
  locked ontology (the lock permits "new kind/edge/atom"). Declaration:
  `{domain: ["item"], range: ["item"], dst: "optional", cond_group: "forbidden", reified: true, status: "live",
  notes: "downgrade ladder through use (inverse of supersedes' upgrade). dst=None = destroyed terminal."}`. Add a
  `vocab.degrade_terminal = ["destroyed", "reverts_to", "broken"]` and `vocab.degrade_trigger = ["per_use", "per_hit"]`.
- The `model-enum ⊆ schema` invariant stays green (the new value is declared in both).

## 3. The `degrades_to` model

`slugify` is `kg_ingest.ids.slugify`. Each `degrades_to` edge: `type=degrades_to`, `src=item:<id>`, `cond_group=None`,
`data = {"trigger": <per_use|per_hit>, "terminal"?: <destroyed|reverts_to|broken>}` (`terminal` only on the last edge).

A family's chain = consecutive `degrades_to` edges through the ordered `sequence`, then a **terminal** edge from the
last sequence item:
- **destroyed** → `dst=None`, `data.terminal="destroyed"`.
- **reverts_to** → `dst=item:<uncharged>`, `data.terminal="reverts_to"`.
- **broken** → `dst=item:<broken>`, `data.terminal="broken"`.

```
destroyed   Ring of dueling: 2552(8)→2554(7)→…→2566(1) --{terminal:destroyed}--> ∅ (dst=None)
reverts_to  Amulet of glory: 11978(6)→…→1706(1) --{terminal:reverts_to}--> 1704 (uncharged)
            Scythe of vitur: 22325(charged) --{terminal:reverts_to}--> 22486 (uncharged)
broken      Dharok's helm:  <100>→<75>→<50>→<25> --{terminal:broken}--> <0/broken>
```

Resolution: "is a Ring of dueling destroyed when used up?" → its `(1)` node has an outgoing `degrades_to` with
`dst=None`. "What does glory(5) become?" → glory(4). "How is a depleted scythe restored?" → its `reverts_to` dst is
the uncharged node, which `recipe:charge-scythe-of-vitur` (slice 2) produces from — the loop is implicit (decision 5).

## 4. Data + verifier (editorial)

### 4a. `data/degrade_paths.json` — curated, source-grounded
Per family: an ordered `sequence` of item ids (degrade order), a `terminal`, a `terminal_item` for reverts/broken,
a `trigger`, `source_url` + a verbatim `source_token`. Shape:
```json
{ "_provenance": {"note": "curated item degradation paths; editorial — owner-reviewed", "license": "CC BY-NC-SA 3.0",
                  "accessed": "..."},
  "records": [
    { "slug": "ring-of-dueling-degrade", "page": "Ring of dueling", "trigger": "per_use",
      "sequence": [2552, 2554, 2556, 2558, 2560, 2562, 2564, 2566],
      "terminal": "destroyed",
      "source_url": "https://oldschool.runescape.wiki/w/Ring_of_dueling", "source_token": "<verbatim>" },
    { "slug": "amulet-of-glory-degrade", "page": "Amulet of glory", "trigger": "per_use",
      "sequence": [11978, 11976, 1712, 1710, 1708, 1706],
      "terminal": "reverts_to", "terminal_item": 1704,
      "source_url": "https://oldschool.runescape.wiki/w/Amulet_of_glory", "source_token": "<verbatim>" },
    { "slug": "scythe-of-vitur-degrade", "page": "Scythe of vitur", "trigger": "per_hit",
      "sequence": [22325],
      "terminal": "reverts_to", "terminal_item": 22486,
      "source_url": "https://oldschool.runescape.wiki/w/Scythe_of_vitur", "source_token": "<verbatim>" },
    { "slug": "dharoks-helm-degrade", "page": "Dharok's helm", "trigger": "per_hit",
      "sequence": [<owner-verified ordered ids 100..25>],
      "terminal": "broken", "terminal_item": <owner-verified broken id>,
      "source_url": "https://oldschool.runescape.wiki/w/Dharok's_helm", "source_token": "<verbatim>" } ] }
```
The exact orderings + Dharok's ids are wiki-sourced + pass the **owner editorial gate** before merge (never invented).
Known-correct ids today: Ring of dueling 2552..2566, Glory 11978/11976/1712/1710/1708/1706→1704, Scythe 22325→22486.

### 4b. `data/verify_degrade_paths.py` — source-grounding gate
Follows the `verify_charge_recipes.py` pattern (committed, exits non-zero on violation): every `sequence[]` + every
`terminal_item` id resolves in `item_dictionary.json`; `sequence` is non-empty and all its ids share a `page_name`
(== `page`); `terminal ∈ {destroyed, reverts_to, broken}`; `reverts_to`/`broken` carry a `terminal_item` that shares
the family's `page_name`, `destroyed` carries **no** `terminal_item`; `trigger ∈ {per_use, per_hit}`; slug unique;
`source_url` + non-empty `source_token`. **Owner editorial review of the orderings/terminals is a hard human gate.**

## 5. Builder + the shared item-`src` rekey (the integration crux)

`kg_ingest/builders/degrade_paths.py` — `build_degrade_paths(records) -> (nodes=[], edges, groups={})`: per record,
emit a `degrades_to` edge between each consecutive `sequence` pair (`data={"trigger"}`), then the terminal edge from
the last sequence id (`dst=None` for destroyed, else `dst=item:<terminal_item>`, `data={"trigger","terminal"}`).
Builder-local edge ids in a fresh band (`0xA0000000`, verified free). Emits **no nodes** — every referenced item id
is a node already (slice 1) or auto-imported (below).

**`assemble.py` wiring (two coupled concerns):**
1. **Auto-import** Dharok's variants: run `build_degrade_paths(...)` and append its edges to `edges` **before**
   `referenced_all = _collect_referenced_ids(...)`, so the sequence/terminal item ids land in `referenced_item_ids`
   and `build_items` imports the not-yet-present nodes (Dharok's `100/75/50/25/0`). Ring of dueling / Glory / Scythe
   ids already exist.
2. **Shared rekey** (decision 6): `degrades_to` edges are **item-`src`**, exactly like `build_items`' `same_entity`
   edges. `assemble.rekey` derives an edge's global id from `(src, per-owner index)` and is called **per builder**; if
   `degrades_to` were rekeyed in its own call, an item that is the `src` of BOTH a `same_entity` edge and a
   `degrades_to` edge (e.g. Ring of dueling (8) = `item:2552`, bridged to its page AND degrading to (7)) would mint
   `stable_edge_id(item:2552, 0)` in both calls → a duplicate global edge id. **Fix:** rekey the `degrades_to` edges
   **together with** `build_items`' `same_entity` edges in a single `rekey(i_nodes, i_edges + dg_edges, {})` call, so
   the per-owner index assigns `same_entity`→0, `degrades_to`→1 for a shared owner. This is precisely the "fold item
   edges into a shared rekey" the slice-2 final review recommended. The **global edge-id-uniqueness assert** added in
   slice 2 is the committed backstop that fails the build if this regresses.

Ordering in `assemble.assemble()`: existing builders → `build_degrade_paths` → append `dg_edges` (builder-local) to a
list used only for reference collection → collect references (incl. Dharok's) → `build_items` → **shared rekey** of
`i_edges + dg_edges` → combined into `edges` → global edge-id assert → `build_supporting` → `dedup_nodes`.

## 6. Validation & success criteria (all must hold)

- `validate_kg` **exit 0** — `degrades_to` edges VIOLATION-clean (item→item, `dst` optional incl. `None`; the schema
  invariant permits `dst=None` since `dst:"optional"`). Recipe + same_entity + degrades_to all coexist cleanly.
- `validate_cost` **exit 0** (degrade data carries no cost tokens; `degrade_paths.json` is not a cost file).
- `assemble` **byte-stable** (the shared rekey is deterministic — sorted builder outputs); the global edge-id assert passes.
- **Golden + slice-1/2 tests stay green** (degrades_to is additive; existing item/recipe behavior unchanged).
- New **TDD** tests: `build_degrade_paths` for all 3 terminals (destroyed dst=None, reverts_to/broken dst=node, the
  per-step chain, `trigger`/`terminal` data); the Dharok's auto-import (its variants become nodes); the **shared-rekey
  no-collision** case (an item that is both a `same_entity` src and a `degrades_to` src gets two distinct edge ids);
  `verify_degrade_paths.py`.
- **+1 competency question:** *"Is a Ring of dueling destroyed when depleted?"* → its last variant has an outgoing
  `degrades_to` with `dst=None` (`method: "is_destroyed"`, expect true).
- Full `pytest` green (the 4 pre-existing `tests/drop_rates/` collection errors excepted).

## 7. The degradation taxonomy (for reference)

| Terminal | Depletion ends at | Restore (inverse) | This slice |
|---|---|---|---|
| `destroyed` | nothing (`dst=None`) | none — make/buy fresh | ✅ models |
| `reverts_to` | the uncharged variant node | **recharge** = slice 2's `recipe` | ✅ models (loop implicit via shared node) |
| `broken` | a broken state node | **repair** = `service` edge | ✅ models the degrade side; repair deferred |

## 8. Out of scope — named follow-ups (not this slice)

1. **Repair** (the `broken` inverse): `EdgeType` for `service` (or a repair `recipe`) — `broken → repaired` at an
   NPC/anvil for a fee (Barrows armour, barrelchest anchor). v2 §3 reserves the `service` edge for this. Its own slice.
2. **Degrade-rate / cost-per-use** (charges/durability per hit/use → gp/hour): the cost layer, derived from the trigger
   + slice 2's `charge_yield`.
3. **Expeditious bracelet** + other `per_xp` auto-degraders (degrade on XP gain, not use) — `trigger: per_xp`; variants
   not yet imported.
4. **Other degrading items** (Trident, blowpipe, crystal gear, Barrows weapons, etc.) — add as their families land.

## 9. Open micro-items (non-blocking, settle in implementation)

- Exact Dharok's degrade ordering + ids (`Undamaged` vs `100` head, the `0`/broken terminal id) — wiki-sourced +
  owner-reviewed.
- The `degrade_paths` builder edge band `0xA0000000` must stay disjoint (bands in use: quests 0x10/0x20, goals
  0x30/0x40, quest_rewards 0x50/0x60, items 0x50-edge, completion_goals 0x70/0x78, recipes 0x80, diaries 0x90/0x98,
  diary_goals 0xB0/0xB8 — `0xA0` is free).
- Whether to record the `degrade_terminal`/`degrade_trigger` vocab as schema `vocab` (yes) vs enforce it (no — edge
  `data` is not schema-enforced this build; the verifier enforces it on the data).
