# Shop Layer — All-Shops Scale-Up — Design

> **Status:** DESIGN (finalized 2026-06-28). Branch: `feat/shop-layer` (off `main`, world skeleton +
> re-homing merged, PRs #19/#20). This is the **first bottom-up layer** attaching to the world skeleton
> (`docs/superpowers/specs/2026-06-27-world-skeleton-design.md` §7). It scales the slice-7 Varrock-only shop
> work (`build_map` nodes + `build_storeline` sells) to **every shop the wiki documents**, source-grounded,
> parented into the skeleton — with NPC operators AND currency-as-entity both explicitly deferred to their own
> follow-up slices.

---

## 1. Goal

Turn the ~12 hand-authored Varrock shops into the **complete shop layer of Gielinor**: every shop in
`Bucket:Storeline` (581 distinct sellers) becomes a `shop:` node, parented `located_in` a skeleton place via a
new shop-infobox brick, with item-only `sells` edges (currency deferred — §7) — built deterministically,
byte-stable, and gated by a coverage verifier that proves the roster is honest from both directions.

## 2. Architecture (fits the existing pipeline)

Approach **A** — Storeline roster spine + shop-infobox brick + shop-type-category, mirroring the world
skeleton's backbone + category-snapshot + infobox triad. Three sources, one new builder:

```
data/raw/storeline_bucket.json        (have)  roster + stock            →┐
data/raw/wiki_shop_infoboxes.json     (NEW)   location + members + owner →┤ build_shops →  shop nodes
data/raw/wiki_shop_categories.json    (NEW)   shop_type + coverage union →┘  (kg_ingest/builders/shops.py)  + located_in
                                                                                                            + sells (item-only)
```

`build_shops` runs **after** `build_storeline` in `assemble.py`; its edges are shop-`src` and are re-keyed in
their **own** seeded `rekey` call (seeded from the prior shop-`src` per-owner counts of `build_map` +
`build_storeline`, so ids stay disjoint — the established per-`src`-class pattern). The build stays
**byte-stable** (re-run = identical bytes). **Zero schema changes** (§6).

## 3. Locked decisions (brainstorm outcomes)

- **D1 — Shops before NPCs.** In the reciprocal `operates`/`operator` pair, build the layer whose *core* is
  self-sufficient first. A shop's core (node + `located_in place` + `sells item`) closes over places + items,
  both of which exist; the NPC layer's `operates` edges need shops as targets. Readiness, not hierarchy depth,
  sets the order. Storeline is a ready bounded source; the NPC roster is unscoped (its own future brainstorm).
- **D2 — Currency deferred to its own follow-up slice.** Investigation showed currency is a first-class
  *entity* (the schema's `currency:` node + a `currency_ref` edge key), not a tag: a loose `"currency"` token in
  `kg/*.json` trips `validate_cost` Invariant 6 by design (a raw-text guard keeping per-account cost out of the
  graph). Doing it right needs promoting the `currency:` kind, extending owner-curated `currencies.json`, AND
  refining Inv 6 — a cross-cutting mini-project. So `sells` edges stay **item-only** this slice; currency lands
  next as a focused slice (§7). price/stock/restock remain in the snapshot regardless.
- **D3 — Operators deferred to the NPC layer.** Derived shops carry **no** operator and **no** `operates`
  edge. The infobox `owner` field is captured **in the brick** (verbatim) for the NPC layer to consume, but
  is not emitted into the graph here. Varrock's hand-authored shops keep their existing operators.
- **D4 — Multi-location rule (§5).** A shop resolving to exactly one place → `located_in` it (the ~95%); to
  **more than one** distinct place → **defer** (tag `multi_location`, emit no location edge, disclose as a
  categorized residual); to **zero** → `FLAG`. No arbitrary "primary" location is ever asserted. The
  slayer-master *role consolidation* (a `slayer-master` role node whose instances carry the locations) is the
  **documented NPC-slice plan**, not built here.
- **D5 — Storeline is the roster spine.** Every distinct `sold_by` becomes a node; the shop-type-category
  union is the **second yardstick** the coverage verifier measures against, not the roster source.
- **D6 — No schema changes.** `shop.shop_type` already exists in `kg/schema.json`; `multi_location` is the one
  additive `shop` data key (§6). With currency deferred, no `currency`/`currency_ref` token enters `kg/*.json`,
  so `validate_cost` Inv 6 stays satisfied untouched.

## 4. Sources & the new bricks

### 4a. `Bucket:Storeline` (have it)
581 distinct `sold_by` sellers, 6,236 rows, currency-agnostic (Coins + ~36 token/point currencies; 45 shops
are non-coin). Fields: `sold_by`, `sold_item`, `store_currency`, prices, stock, restock. This is the roster
+ stock + currency truth. Fetched by `data/fetch_storeline.py` (committed snapshot).

### 4b. NEW shop-infobox brick — `data/fetch_shop_infoboxes.py` → `data/raw/wiki_shop_infoboxes.json`
Mirrors `data/fetch_world_infoboxes.py`. Steps:
1. Enumerate shop **pages** as the union of members of `Category:Shops`' type-subcategories (`Archery shops`,
   `Axe shops`, `Clothes shops`, …). This list yields both the page set to fetch **and** `shop_type` (4c).
2. For each page, isolate the `{{Infobox Shop}}` block and extract **verbatim**: `location` (a `[[wikilink]]`),
   the versioned `location1..locationN` variants, `members` (Yes/No), and `owner`/`owner1..N` (the seller NPC,
   captured for the NPC layer — never emitted here).
3. Record sorted, with `_provenance` (source_url, license CC BY-NC-SA, extraction method, row count).

`location` values are parsed with the world skeleton's `parse_infobox_links` (ordered, de-duped wikilink
targets). Scope extraction to the `{{Infobox Shop}}` block to avoid `{{Relativelocation}}`-style traps.

### 4c. `shop_type` — from the infobox `icon`
**Implementation finding (2026-06-28):** the fine "X shops" taxonomy does **not** exist as wiki categories
(only coarse/junk subcats — `Members' shops`, `Merchants`, `Lliann's Wares`, `Shop images`). The structured
type signal is the `{{Infobox Shop}}` **`icon`** field — the in-game map-icon legend — e.g.
`[[File:Archery shop icon.png]]` → `Archery shop`. `build_shops` parses the verbatim icon (captured in the
infobox brick) into `shop.data.shop_type` (advisory — the `content_kind` "over-tag" lesson; `None` if absent).
The `Category:Shops` subcategory snapshot (`wiki_shop_categories.json`) is still fetched, but serves only as the
**coverage yardstick** for `verify_shop_coverage`, not as the `shop_type` source.

### 4d. Matching Storeline ↔ infobox
A Storeline `sold_by` is joined to its infobox record by normalize-but-town-aware matching (**reuse
`storeline.match_shop`**). Unmatched sellers (no shop page / NPC-direct sellers) → no location → `FLAG`; the
node + its `sells` still emit. This is reported, never fabricated.

## 5. Data model (what lands in the graph)

- **Shop node** `shop:<slug>` (slug from `sold_by`, deterministic, trailing-period/parenthetical-safe, with a
  collision guard). `data`: `shop_type` (advisory), `members` (from the infobox Yes/No, omitted if unknown),
  and `multi_location: true` for deferred multi-site shops. **No `operator`** on derived shops.
- **`located_in`** edge: shop → place. Emitted only when the shop resolves to **exactly one** distinct place
  (the multi-location rule, D4). At most one `located_in` per shop in this slice — the place skeleton stays a
  clean single-parent tree.
- **`sells`** edge: shop → item. `data`: `members` (from the item record, as today), `source_token`. Optional
  gate `cond_group` only for the Varrock owner-overlay (unchanged from slice 7). **No** currency (deferred,
  §7), **no** price/stock/restock (those remain in the snapshot). Byte-identical edge shape to today's
  `build_storeline` sells — the scale-up is "same join, every shop."

### Multi-location handling (D4, detail)
Resolve every `location`/`location1..N` to a place id via the same name-index used for parenting. Then:
| distinct resolved places | action |
|---|---|
| exactly 1 | emit `located_in` → that place |
| more than 1 | emit **no** location; set `multi_location: true`; `verify_shop_coverage` lists it as a categorized residual (`deferred-multi-location`) |
| zero | `FLAG` (unparented), reported |

Rationale: a multi-site shop (Slayer Rewards = 9 slayer-master spots) has no honest single home; its location
is properly a property of its **operators**, which is NPC-layer work. We assert nothing arbitrary now and let
the NPC slice resolve it via the role/instances.

## 6. Schema (no changes)

Confirmed against `kg/schema.json`:
- `node_kinds.shop.data_keys` already includes **`shop_type`** (and `operator`, `aliases`).
- `edge_kinds.sells` is reified (notes name `currency`/`price`/`stock`/`restock`), but this slice leaves all of
  them **unpopulated** — exactly as slice 7 did. So no `currency` token enters `kg/*.json` and `validate_cost`
  Invariant 6 stays satisfied untouched (currency is its own follow-up slice, §7).
- `edge_kinds.located_in` domain already includes `shop`, range `place`.
- The `located_in` acyclicity/tree gate in `validate_kg` is **place-only**, and this slice emits ≤1
  `located_in` per shop, so no structural rule is added or stressed.

Adding `multi_location` as a `shop` data key is the one additive touch (a boolean flag), consistent with the
"additive, never a re-ingest" discipline; confirm it is permitted by the schema's data-key policy during
implementation (add to `node_kinds.shop.data_keys` if the validator enforces a closed set).

## 7. Currency — deferred to its own follow-up slice (NOT in this slice)

The brainstorm chose "record currency, not price." Implementation investigation then found currency is **not a
tag** but a first-class entity, and modeling it touches three subsystems — so it is deferred to a dedicated
follow-up slice. This slice emits **item-only `sells`** edges (no currency key), exactly like slice 7.

Why it's a mini-project, not a line on the edge:
- **`validate_cost.py` Invariant 6** fails on the literal token `"currency"` (key *or* value) anywhere in
  `kg/*.json` except `schema.json` — a deliberate raw-text guard keeping per-account cost/price out of the
  committed graph. A `currency` string on a sells edge would break it; even a `currency:` *node* instance
  (carrying `"kind": "currency"`) trips the same blunt scan.
- The schema's blessed model is a **`currency:` node** (reserved kind) referenced by a **`currency_ref`** edge
  key (which the regex does not match). Instantiating that needs: promote the kind reserved→live; build
  `currency:` nodes from the **owner-curated** `data/currencies.json` (extend its 4 seed entries to the ~36
  currencies Storeline uses — editorial); refine Inv 6 to admit the legitimate currency *vocabulary instances*
  while still blocking per-account price/cost.

**The follow-up slice** (its own spec/plan) will: promote `currency:` to live, extend `currencies.json`
(owner-reviewed), refine `validate_cost` Inv 6, and add `currency_ref` to the **existing** sells edges
(additive, no re-ingest). It also handles the `Points` ambiguity honestly (the wiki labels ~6 distinct point
currencies all as `Points`; resolved per-shop or left coarse-and-disclosed — never fabricated). The shop layer
ships fully without it.

## 8. Verification & never-fabricate

- **NEW `data/verify_shop_coverage.py`** (the completeness gate): cross-checks the two rosters — Storeline
  `sold_by` vs the shop-type-category union — and reports `have N/total` per `shop_type`, plus counts of
  shops `parented` / `deferred-multi-location` / `FLAGged` / matched-vs-unmatched. `--refresh` checks live
  drift. **Report-not-fail** (exit 0). This is how "all shops" is *proven*, not asserted.
- **NEW `data/verify_shops.py`** (the source-grounding gate, pattern of `verify_storeline.py`): every derived
  `sells` edge traces to a Storeline row; every `located_in` traces to an infobox `location` token and resolves
  to a committed place node; `members` matches the source. **Structural** breaches (a sells edge with no backing
  row, a non-existent dst) hard-fail; **resolution** residuals (unmatched sellers, deferred multi-location,
  FLAGged no-location) are REPORTED.
- **`validate_kg`**: existing domain/range + the place-only tree gate already cover shop `located_in`/`sells`;
  the global edge-id-uniqueness assert backstops the seeded rekey.
- **Residual disclosure**: the FLAGged (no-location) and deferred-multi-location shops are a categorized,
  owner-visible residual — never silently dropped, never fabricated.

## 9. Testing & competency questions

TDD via subagent-driven-development. Slice sketch (detailed in the plan):
1. **Infobox brick + parser** — `fetch_shop_infoboxes.py`, `{{Infobox Shop}}` block isolation, `location1..N`
   handling, `parse_infobox_links` reuse; committed `wiki_shop_infoboxes.json`.
2. **Roster + node emission** — distinct `sold_by` − varrock-owned (`extra_seen`) − excluded; `shop:<slug>`
   with collision guard; `shop_type`/`members`.
3. **Parenting + multi-location rule** — `parent_for` over a place name-index built from the committed place
   graph; the 1/>1/0 split.
4. **Sells scale-up** — extend the `build_storeline` join to all shops (item-only edges; no currency).
5. **Verifiers** — `verify_shop_coverage.py` + `verify_shops.py`.
6. **Assemble wiring + byte-stable + competency** — seeded rekey after `build_storeline`; golden re-assemble;
   competency questions.

**Competency questions** (added to `kg/competency_questions.json`, reusing the existing `sold_by`/`shop_stock`/
`region_chain` method handlers): "what does shop X sell", "where can I buy item Y" (`sold_by`), a `region_chain`
over a derived shop up to `place:gielinor`.

## 10. Scope / non-goals

**IN:** all Storeline shops as `shop:` nodes · `located_in` (single-location shops) · item-only `sells` ·
`members` · `shop_type` · the two verifiers · competency questions.

**OUT (deferred, by design):**
- **Currency** — the entire `currency:` node + `currency_ref` model + `currencies.json` extension +
  `validate_cost` Inv 6 refinement (its own follow-up slice, §7).
- **Operators / NPCs** — the entire `npc` layer, `operates`/`operator` edges, the slayer-master role
  consolidation (next slice; the infobox `owner` is captured in the brick for it).
- **Multi-location resolution** — deferred to the NPC layer via operators (disclosed residual here).
- **Price / stock / restock** in the graph (stay in the snapshot; cost layer owns price).
- **Grand Exchange & banks** — facilities layer (GE confirmed to have no `{{Infobox Shop}}`).
- **`same_entity` bridging** of shops to any legacy nodes.

## 11. Open micro-items (settle in implementation)

- Exact edge band for `build_shops` (share `0xF0` seeded, or a new disjoint band) — keep builder-local bands
  disjoint per the CLAUDE.md convention.
- New module `kg_ingest/builders/shops.py` vs extending `storeline.py` (lean: new module; `build_storeline`
  stays the Varrock-overlay join, `build_shops` owns the derived roster).
- The place name-index helper: refactor `world.resolve_parents` to expose its name-index, or add a small
  `build_place_name_index(place_nodes)` that reads the committed place nodes (preferred — keeps shop parenting
  a pure function of the shipped place graph, reinforcing the bottom-up cross-check).
- Finalize the `shop_type` priority order from the actual `Category:Shops` subcategory set.
- Slug determinism for NPC-name sellers and trailing-period names; collision guard.
- Confirm `multi_location` is accepted by the schema data-key policy (add to `shop.data_keys` if needed).
