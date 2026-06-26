# Repair Edges (`repairs`) — Slice 4

> **Status:** DESIGN (2026-06-25). Closes the `broken` half of the durability lifecycle from the degradation slice
> (`2026-06-25-degradation-edges-design.md`). Branch: `feat/entity-graph-ontology`. Builds on item nodes (slice 1),
> charge recipes (slice 2), and degradation (slice 3).

## 0. Why this slice

Slice 3 added `degrades_to` with a **`broken`** terminal (Dharok's helm `…→ 0`). This adds the inverse: `repairs`
(`broken → repaired`). It completes a coherent **item-state-transition edge family** — `supersedes` (upgrade) /
`degrades_to` (downgrade-through-use) / `repairs` (restore-from-broken) — and closes the lifecycle:
`degrades_to`(→broken) ↔ `repairs`(broken→). The endpoints already exist (Dharok's helm) or auto-import (barrelchest).

**Deliberately deferred (iron-gate + ontology layering):** the repair **fee** is *account-aware* (scales with
Smithing-level NPC discount + a POH armour stand via Construction), so it belongs in the **cost layer**, not the
static graph. The repair **NPC/facility** ("repaired by Bob / at an armour stand") is the v2-reserved **`service`**
edge (`npc/facility → effect`), deferred until `npc`/`facility` nodes exist. This slice models only the **structural
transition**.

## 1. Decisions (settled in brainstorming, 2026-06-25)

| # | Decision | Choice |
|---|---|---|
| 1 | Edge model | **New `EdgeType.REPAIRS`** (item→item), the structural inverse of `degrades_to`'s broken terminal |
| 2 | Edge data | **Pure transition** — no `data` (the `via`/where/who/cost is wholly the deferred service + cost layers) |
| 3 | Scope | **Dharok's helm** (4884 → 4716; endpoints exist) + **Barrelchest anchor** (10888 → 10887; auto-imports) |
| 4 | Data source | **Curated `data/repair_paths.json`** (editorial, source-grounded, verifier-gated) |
| 5 | Edge rekey | `repairs` is item-`src` → **folded into the shared rekey** with `same_entity` + `degrades_to` (see §5) |
| 6 | Deferred | the repair **fee** (cost layer), the repair **NPC/facility** (`service` edge), full Dharok's/Barrows set, other repairables |

## 2. Model additions (additive ontology extension)

- **`model.py`**: add `EdgeType.REPAIRS = "repairs"`.
- **`kg/schema.json`**: add a new `edge_kinds.repairs` entry (status `live`) — not in the original v2 §3 table; the
  restore-from-broken inverse of `supersedes`. Declaration:
  `{domain: ["item"], range: ["item"], dst: "required", cond_group: "forbidden", reified: false,
  notes: "Restore-from-broken (additive extension; inverse of degrades_to's broken terminal). broken-variant -> repaired-variant. Pure structural transition; the repair fee is account-aware (cost layer) and the NPC/facility is the reserved service edge."}`.
  (`reified: false`, mirroring `supersedes` — it carries no `data`.)
- The `model-enum ⊆ schema` invariant stays green.

## 3. The `repairs` model

One `repairs` edge per repairable item: `type=repairs`, `src=item:<broken>`, `dst=item:<repaired>`,
`cond_group=None`, `data={}` (pure transition).

```
Dharok's helm:      item:4884 (Dharok's helm 0, broken) --repairs--> item:4716 (Dharok's helm, Undamaged)
Barrelchest anchor: item:10888 (Broken)                 --repairs--> item:10887 (Fixed)
```

Dharok's helm endpoints (4884, 4716) already exist (slice 3); Barrelchest's two variants (10887, 10888) **auto-import**
via the referenced mechanism (§5). Resolution: "can a broken Dharok's helm be repaired?" → `item:4884` has an outgoing
`repairs` edge → `item:4716`. "How much / where?" → the deferred cost + service layers.

## 4. Data + verifier (editorial)

### 4a. `data/repair_paths.json` — curated, source-grounded
Per item: the `broken` + `repaired` ids, `source_url` + a verbatim `source_token`. Shape:
```json
{ "_provenance": {"note": "curated item repair transitions (broken->repaired); editorial — owner-reviewed",
                  "license": "CC BY-NC-SA 3.0", "accessed": "..."},
  "records": [
    { "slug": "repair-dharoks-helm", "page": "Dharok's helm", "broken": 4884, "repaired": 4716,
      "source_url": "https://oldschool.runescape.wiki/w/Dharok's_helm", "source_token": "<verbatim>" },
    { "slug": "repair-barrelchest-anchor", "page": "Barrelchest anchor", "broken": 10888, "repaired": 10887,
      "source_url": "https://oldschool.runescape.wiki/w/Barrelchest_anchor", "source_token": "<verbatim>" } ] }
```
Verified ids (resolve in `item_dictionary.json`, share the record's `page_name`): Dharok's helm 4884/4716;
Barrelchest anchor 10888/10887. Source tokens wiki-sourced + owner-reviewed (never invented).

### 4b. `data/verify_repair_paths.py` — source-grounding gate
Follows the `verify_degrade_paths.py` pattern (committed, exits non-zero on violation): `broken` + `repaired` ids
resolve in `item_dictionary.json` and share the record's `page_name`; `broken != repaired`; slug unique; `source_url`
+ non-empty `source_token`. **Owner editorial review of the repair facts is a hard human gate.**

## 5. Builder + the shared item-`src` rekey

`kg_ingest/builders/repairs.py` — `build_repairs(records) -> (nodes=[], edges, groups={})`: per record, one
`repairs` edge `item:<broken> → item:<repaired>`, `data={}`. Emits NO nodes. Builder-local edge ids in a fresh band
(`0xC0000000`, verified free).

**`assemble.py` wiring** (a clean extension of slice 3's):
1. **Auto-import** Barrelchest variants: run `build_repairs(...)` and include its edges in the
   `_collect_referenced_ids(...)` input (alongside `dg_edges`) **before** `build_items`, so 10887/10888 land in
   `referenced_item_ids` and `build_items` imports them. Dharok's helm ids already exist.
2. **Shared rekey** (decision 5): `repairs` is item-`src`, like `same_entity` (slice 1) and `degrades_to` (slice 3).
   Fold `rp_edges` into the SAME `rekey` call: `rekey(i_nodes, i_edges + dg_edges + rp_edges, {})`. The per-owner
   index disambiguates any item that is the `src` of more than one (none in this slice, but the invariant holds for
   future overlap). The slice-2 global edge-id-uniqueness assert is the committed backstop.

Ordering in `assemble.assemble()`: existing builders → `build_degrade_paths` + `build_repairs` (builder-local) →
collect references from `edges + dg_edges + rp_edges` (incl. Barrelchest) → `build_items` → **shared rekey** of
`i_edges + dg_edges + rp_edges` → global edge-id assert → `build_supporting` → `dedup_nodes`.

## 6. Validation & success criteria (all must hold)

- `validate_kg` **exit 0** — `repairs` edges VIOLATION-clean (item→item, dst required; both endpoints resolve).
- `validate_cost` **exit 0** (the repair data carries no cost tokens; the fee is NOT in the graph).
- `assemble` **byte-stable**; the global edge-id assert passes (the shared rekey covers all three item-`src` edge types).
- **Golden + slice-1/2/3 tests stay green** (repairs is additive; existing behavior unchanged).
- New **TDD** tests: `build_repairs` (one item→item `repairs` edge per record, empty data, item-`src`); the Barrelchest
  auto-import (its 2 variants become nodes); the shared-rekey still clean (zero duplicate edge ids with all three
  item-`src` types present); `verify_repair_paths.py`.
- **+1 competency question:** *"Can a broken Dharok's helm be repaired?"* → `item:4884` has an outgoing `repairs`
  edge (`method: "is_repairable"`, expect the repaired-item set non-empty).
- Full `pytest` green (the 4 pre-existing `tests/drop_rates/` collection errors excepted).

## 7. The durability lifecycle (for reference)

| Direction | Edge | Slice |
|---|---|---|
| upgrade | `supersedes` | (pre-existing) |
| deplete-through-use | `degrades_to` (→ destroyed / reverts_to / broken) | slice 3 |
| refill (reverts_to inverse) | `recipe`/`produces` | slice 2 |
| **restore (broken inverse)** | **`repairs`** | **this slice** |

Restore inverses: `reverts_to`→recharge (`recipe`, slice 2, loop implicit via the shared uncharged node);
`broken`→**repair** (`repairs`, this slice); `destroyed`→none.

## 8. Out of scope — named follow-ups (not this slice)

1. **Repair fee** — the account-aware gp cost (Smithing-level NPC discount; POH armour stand via Construction): the
   **cost layer** (a repair-cost overlay), derived per-account.
2. **Repair NPC/facility** — "repaired at an armour stand / by Bob in Lumbridge / by a smith": the v2-reserved
   **`service`** edge (`npc/facility → effect`), once `npc`/`facility` nodes exist.
3. **Full Dharok's / Barrows set** + other repairables (other Barrows pieces, crystal gear, etc.) — add as families land.

## 9. Open micro-items (non-blocking, settle in implementation)

- Wiki source tokens for the two repair facts — sourced + owner-reviewed.
- The `repairs` builder edge band `0xC0000000` must stay disjoint (bands in use: quests 0x10/0x20, goals 0x30/0x40,
  quest_rewards 0x50/0x60, items 0x50-edge, completion_goals 0x70/0x78, recipes 0x80, diaries 0x90/0x98,
  degrade 0xA0, diary_goals 0xB0/0xB8 — `0xC0` is free).
- Whether Barrelchest's `repaired` is named "Barrelchest anchor" (Fixed, 10887) vs the broken "Barrelchest anchor"
  (Broken, 10888) — both share `page_name "Barrelchest anchor"`, so the verifier same-page check holds.
