# Equipment Bonuses (`equipment_bonuses` node + `has_bonuses` edge) — Slice 5

> **Status:** DESIGN (2026-06-25). The BIS/loadout substrate. Branch: `feat/entity-graph-ontology`. Builds on item
> nodes/variants (slice 1) and the shared item-`src` rekey (slices 1/3/4).

## 0. Why this slice

Adds the **combat-stat facet** to equippable items: a reified `equipment_bonuses` node per equippable item-variant +
a `has_bonuses` edge (`item → equipment_bonuses`). This is the substrate for BIS/loadout reasoning ("what's the best
weapon in this slot"). Both kinds are **already reserved** in the v2 schema (`has_bonuses: item → equipment_bonuses`),
so this slice **flips them live** (the slice-1/2 pattern), not an additive-new edge.

## 1. Decisions (settled in brainstorming, 2026-06-25)

| # | Decision | Choice |
|---|---|---|
| 1 | Model | Flip `NodeKind.EQUIPMENT_BONUSES` + `EdgeType.HAS_BONUSES` **reserved → live** |
| 2 | Node identity | One `equipment_bonuses:<item_id>` per equippable item-variant (1:1, no dedup) |
| 3 | Node contents | **Combat profile**: 14-field `stats` block + `slot` + `weapon` sub-block (speed/range/combat_style, weapons only) |
| 4 | Scope | **Bound to the ~86 equippable item-variant nodes already in the graph** (no auto-import; full roster deferred) |
| 5 | Data source | The existing committed `data/items_equipment.json` (no new ingest) + a **selection rule** (§4) |
| 6 | Edge rekey | `has_bonuses` is item-`src` → the **4th edge** to join the shared rekey (§6) |
| 7 | Deferred | full roster · wield requirements · non-combat intrinsics · set bonuses · special effects · DPS/EHP |

## 2. Model additions (flip reserved → live)

- **`model.py`**: add `NodeKind.EQUIPMENT_BONUSES = "equipment_bonuses"` + `EdgeType.HAS_BONUSES = "has_bonuses"`.
- **`kg/schema.json`**: flip `node_kinds.equipment_bonuses` and `edge_kinds.has_bonuses` from `status: "reserved"` to
  `"live"` (domain/range already declared: `has_bonuses` = `item → equipment_bonuses`). No new schema entry; just the
  status flip (+ confirm `has_bonuses` dst `required`, `reified: false`).
- The `model-enum ⊆ schema` invariant stays green.

## 3. The facet node + edge

**Node** — one per equippable item-variant: `id = "equipment_bonuses:<item_id>"`, `kind = equipment_bonuses`,
`name = "<item name> (equipment bonuses)"`, `data` = the combat profile:
```json
{ "item_id": 22325, "slot": "2h",
  "stats": { "stab_attack_bonus": 70, "slash_attack_bonus": 125, "crush_attack_bonus": 30,
             "magic_attack_bonus": -6, "range_attack_bonus": 0,
             "stab_defence_bonus": -2, "slash_defence_bonus": 8, "crush_defence_bonus": 10,
             "magic_defence_bonus": 0, "range_defence_bonus": 0,
             "strength_bonus": 75, "ranged_strength_bonus": 0, "prayer_bonus": 0, "magic_damage_bonus": 0 },
  "weapon": { "weapon_attack_speed": 5, "weapon_attack_range": "1", "combat_style": "Slash" } }
```
`weapon` is present only when the source record has a weapon block (weapon/2h slots); absent otherwise.

**Edge** — `has_bonuses`: `item:<item_id> → equipment_bonuses:<item_id>`, `cond_group = None`, `data = {}` (the
bonuses live on the node). Item-`src`.

Bonuses attach to **variant** nodes (`item:22325`), never **page** nodes (`item:scythe-of-vitur`) — `items_equipment`
is keyed by numeric `item_id`, so page (slug-id) nodes simply don't match. Charged vs uncharged are distinct variant
ids with distinct records, so they're distinguished for free (charged Scythe → slash 125; uncharged Scythe → no record
→ no bonuses node).

## 4. Data source + the selection rule (the crux)

**Source:** the existing committed `data/items_equipment.json` — 4,298 records from the `infobox_bonuses` +
`infobox_item` Buckets (dataset-level `_provenance`; no new ingest). **No per-record `source_token`** — bulk Bucket
data is grounded by the dataset provenance + the verifier (§5), not per-row quotes.

**The selection rule (why it exists — a 2026-06-25 data audit):** the dataset carries **multiple records per
`item_id`** — one per stat-variant (`stat_variant_index`) plus **beta-page duplicates** (`page_name` like
`"Scythe of vitur (beta)"`). A naive one-record-per-id pick lands on stale/empty records: 8 items were spot-checked
against the live wiki and **all 8 recover to correct values once the right record is selected** (e.g. Scythe slash =
**125** on the canonical page / `variant_idx 0`, not 110 on the beta page; Dharok's helm def = **45** on `variant_idx
0`, not the all-zero `variant_idx 1`). So the data is **sound**; only selection was wrong.

**Rule** — for each in-scope `item_id`, pick exactly one record:
1. Prefer the record whose `page_name` **equals the item's `item_dictionary` page** (this drops `(beta)` and other
   non-canonical pages). Fallback: any non-`(beta)` page.
2. Among those, prefer `stat_variant_index == 0`, then `None`, then the lowest index.

Applied to the 86 in-scope items this yields **0 beta leaks and 0 all-zero combat-gear blocks** (only 7 of 86 needed
selection; the other 79 are single-record and verified clean).

## 5. Verifier — `data/verify_equipment_bonuses.py` (with teeth)

Re-runs the selection for the in-scope items and asserts (exits non-zero on any violation):
- **Selection integrity:** exactly one record selected per in-scope `item_id`; the selected `page_name` is
  **non-`(beta)`** and **equals the item's `item_dictionary` page** (the canonical-page gate).
- **Coverage gate:** no selected record on a **combat slot** (`weapon/2h/body/head/legs/shield/hands/feet/cape`) has an
  **all-zero** stat block (catches the empty-variant failure mode). (Pure-utility slots — ring/neck/ammo — may be
  all-zero legitimately.)
- **Structural:** every `item_id` resolves in `item_dictionary`; all 14 `stats` fields present + numeric; `slot` is a
  known equipment slot; a `weapon` block is present iff `slot ∈ {weapon, 2h}`.

This gates the exact corruption classes the audit found (beta dupes, empty stat-variants) — a stronger bar than
structural-only. **Owner editorial review** remains the gate for any judgment a check can't make.

## 6. Builder + the shared item-`src` rekey

`kg_ingest/builders/equipment_bonuses.py` — `build_equipment_bonuses(eq_records, owned_item_ids, canonical_pages) ->
(nodes, edges, groups={})`: groups records by `item_id`; for each `item_id` whose `item:<id>` is in `owned_item_ids`,
applies the selection rule, emits the `equipment_bonuses:<id>` node + the `has_bonuses` edge. Builder-local edge ids in
a fresh band (`0xD0000000`, verified free).

**`assemble.py` wiring:** `build_equipment_bonuses` runs **after `build_items`** (it needs the owned item-variant ids;
it does **not** auto-import — bounded to existing nodes). The `equipment_bonuses` nodes are added to the node set (like
recipe nodes); the `has_bonuses` edges (`hb_edges`) are item-`src`, so they **join the shared rekey** —
`rekey(i_nodes, i_edges + dg_edges + rp_edges + hb_edges, {})` (the 4th item-`src` edge family). The slice-2 global
edge-id-uniqueness assert is the backstop.

Sequence: existing builders → `build_degrade_paths` + `build_repairs` (builder-local) → reference collection →
`build_items` → **`build_equipment_bonuses(owned)`** → shared rekey (`i + dg + rp + hb`) → edge-id assert →
`build_supporting` → `dedup_nodes`.

## 7. Validation & success criteria

- `validate_kg` **exit 0** — `has_bonuses` VIOLATION-clean (`item → equipment_bonuses`, dst required, both resolve).
- `validate_cost` **exit 0** (no cost tokens; the bonus block carries no price/value — intrinsics deferred).
- `assemble` **byte-stable**; the global edge-id assert passes (the shared rekey covers all four item-`src` edge types).
- **Golden + slice-1..4 tests stay green**; `verify_equipment_bonuses.py` exit 0.
- New **TDD** tests: the selection rule (canonical-page over beta; `variant_idx 0` over empty); `build_equipment_bonuses`
  (one node + one `has_bonuses` edge per in-scope equippable item; node carries the stat block; item-`src`);
  Scythe `slash_attack_bonus == 125` and Dharok's helm `stab_defence_bonus == 45` in the committed graph (the audit
  regression guards); the all-ids-unique check with four item-`src` edge types present.
- **+1 competency question:** *"What is the Scythe of vitur's slash attack bonus?"* → `item:22325` has a `has_bonuses`
  edge to a node whose `stats.slash_attack_bonus == 125` (`method: "equipment_bonus"`).
- Graph grows ~**572 → 658 nodes** / ~**867 → 953 edges** (≈86 equippable in-scope items).
- Full `pytest` green (the 4 pre-existing `tests/drop_rates/` collection errors excepted).

## 8. Out of scope — named follow-ups (not this slice)

1. **Full 4,298-item roster scale-up** — the same builder, unbounded (auto-import the roster). A volume step.
2. **Wield requirements** — "can I equip this?" (`requires` cond_group from the record's `requirements`): its own slice.
3. **Non-combat intrinsics** — value / high-alch / weight / tradeable / buy_limit on the item node: the intrinsic-attrs
   slice (the same `items_equipment.json` record carries these).
4. **Set bonuses** (Dharok's/void/etc.) and **special effects** (Salve's +16.67% vs undead — confirmed *not* in the
   stat block; effect-items look weak by stats alone): a separate "effects" concern.
5. **DPS / EHP calculators** — derived compute over the bonus blocks; downstream, not graph.

## 9. Open micro-items (non-blocking, settle in implementation)

- The selected-record `weapon_attack_range` is a string in the source (`"1"`, `"10"`) — keep as-is (verbatim) or coerce
  to int; keep verbatim for byte-fidelity unless the planner needs numeric.
- `equipment_bonuses` builder edge band `0xD0000000` must stay disjoint (in use: …0xA0 degrade, 0xB0/0xB8 diary_goals,
  0xC0 repair — `0xD0` is free).
- `owned_item_ids` passed to the builder = all numeric `item:<id>` variant nodes present after `build_items`.
- A few in-scope items legitimately carry all-zero combat blocks pre-selection but resolve to real stats post-selection;
  the verifier runs its coverage gate on the **selected** record only.
