# Node Import — Slice 1: item nodes from the Wiki Bucket (bounded proof)

> **Status:** DESIGN (2026-06-25). The first vertical slice of **build step 2** (cache/node-import) of the
> Entity-Graph Ontology v2 (`2026-06-25-entity-graph-ontology-v2.md`). Branch: `feat/entity-graph-ontology`.
> Builds against the LOCKED schema (`kg/schema.json`) and the schema-driven `validate_kg` invariant (step 1).

## 0. Why this slice

Step 2 bulk-imports the v2 **node layer** (items/npcs/scenery/places, cache-id keyed). The cache-source
research (`research/osrs-cache-data-sources.md`) recommended a cache/RuneLite pipeline, but the repo already
bulk-imports **items** from the **OSRS Wiki Bucket API** (`infobox_item`) into `data/item_dictionary.json` —
cache-id-keyed, variant-aware, **CC BY-NC-SA** (no Jagex-IP / GPL entanglement). Spec §9 maps most node types to
`infobox_*` buckets anyway. So this build proceeds **Wiki-Bucket-first**; the cache is an optional later backstop.

This slice is a **bounded proof**: stand up the v2 item node model (decision 5: page-identity + variant children
+ `same_entity`) on a verifiable subset, with **zero new fetch** (reuses committed `item_dictionary.json`). The
model is **two-level** — auto-derived **intra-page** variants (glory's charges) + a **curated, editorial cross-page
family** layer (all scythes of vitur, all salve amulets). It proves the variant model both levels, the first new v2
edge (`same_entity`), the schema-invariant flip, byte-stability, and the first competency questions — before scaling
to the full roster.

## 1. Decisions (settled in brainstorming, 2026-06-25)

| # | Decision | Choice |
|---|---|---|
| 1 | Source | **Wiki-Bucket first** (reuse `item_dictionary.json`; cache deferred as optional backstop) |
| 2 | First slice | **Items, bounded proof** |
| 3 | Coverage | **Referenced items ∪ variant exemplars** (no golden-test regression + exercises the variant model) |
| 4 | Variant model | **Explicit page node** + variant children + `same_entity` bridge |
| 5 | Stats | On the **variant** node; the **page node is identity-only** |
| 6 | Competency-questions gate | **Seed minimally** now (2 questions — one per level — + runner test) — decision 9 "from day one" |
| 7 | Exemplar list | **Committed data files** — `data/item_node_exemplars.json` (intra-page) + `data/item_node_families.json` (cross-page, editorial) |
| 8 | `tradeable` | Modeled as `data.tradeable` on the variant; **populated in the intrinsic-attrs follow-up** (not this slice) |
| 9 | Cross-page families | **Two-level identity** — auto intra-page (L1) + **curated** cross-page family bridges (L2), source-grounded + owner-editorial-reviewed |

## 2. The variant model (decision 5) — TWO LEVELS

Item identity is two-tiered, because OSRS variant families split across wiki pages. `slugify` is the existing
`kg_ingest.ids.slugify`.

### Level 1 — intra-page variants (AUTO, from `item_dictionary.json` `page_name` grouping)

Three node/edge shapes:

**Page node** (only for a multi-variant page) — pure identity, **no stats**:
- `id = item:<slugify(page_name)>` (non-numeric tail → never collides with a numeric variant id)
- `kind = item`, `name = page_name`, `slug = slugify(page_name)`, `data = {"is_page": true}`

**Variant node** (one per cache `item_id`) — carries this variant's identity/stats:
- `id = item:<item_id>` (numeric cache id), `kind = item`, `name = item_name` (variant display name), `slug = slugify(item_name)`
- `data = {"members": <bool>, "is_canonical": <bool>, "version_anchor"?: <str>}`
- (intrinsic attrs `value`/`alch`/`weight`/**`tradeable`**/`buy_limit`/equip slot land here in the **intrinsic-attrs
  follow-up**; the combat-bonus block lives on a separate `equipment_bonuses` facet via `has_bonuses` — a later slice)

**`same_entity` edge** (one per variant, including the canonical one) — the identity bridge:
- `type = same_entity`, `src = item:<item_id>` (variant), `dst = item:<page-slug>` (page), `cond_group = None`
- `data = {"basis": "shares wiki page '<page_name>'"}`

**Single-variant item** (`is_variant == false`): just the variant node `item:<item_id>` with
`data = {"members", "is_canonical": true}`. **No page node, no `same_entity`** (the item is its own identity).

```
Amulet of glory (7-variant page)             Dragon scimitar (single-variant)
  item:amulet-of-glory  {is_page:true}        item:4587  {members:true, is_canonical:true}
    ▲        ▲        ▲        ▲               (no page node, no bridge)
    │ same_entity (variant → page)
  item:1704  item:1710  item:1712   item:11978
  glory      glory(3)   glory(4)*   glory(6)   ← own stats (later); is_canonical/version_anchor now
  (* is_canonical = the wiki default_version; reified edges (later slices) target the VARIANT id)
```

Resolution: ambiguous "amulet of glory" → the **page node**; "glory(6)" → `item:11978`. "Do I own a glory?" →
`same_entity`-closure of the page. Prevents over-merge (per-variant stats kept) and over-split (page = "all glory").
**Why the page node, not the canonical variant:** `is_canonical` follows the wiki `default_version`, which is *not*
necessarily the intuitive default — Amulet of glory's canonical is `glory(4)` (`item:1712`), so anchoring ambiguous
resolution on the canonical variant would surprise; the stat-free page node is the correct anchor.

### Level 2 — cross-page families (CURATED, editorial)

Many families span **multiple wiki pages** — ornament kits (`Holy`/`Sanguine`/`Corrupted Scythe of vitur`), imbues
(`Salve amulet(i)`/`(ei)`, `Ring of suffering (i)`), recharge/cosmetic variants (`Bow of faerdhinen (c)`, `Infernal
axe (or)`). `item_dictionary`'s `page_name` grouping **cannot** unify these; the bridges are **curated and
source-grounded** (the spec's `same_entity` / link-don't-merge / "Jaguar Problem" layer, decision 6's
search-resolution). This is the *editorial* half — owner review is a hard gate.

- **Family node** `item:<family-slug>` (curated slug, suffixed `-family` to never collide with a base page),
  `data = {"is_family": true}`, `name = "<family display>"` — the cross-page concept ("all scythes of vitur").
- **`same_entity` (member → family)**: each member's **page node** (multi-variant member) or **variant node**
  (single-variant member) → the family node, `data = {"basis": "<relationship>"}`, basis ∈
  `{base | ornament_kit | imbue | enchant | recharge_state | source_duplicate | cosmetic_recolor | broken}`.
- So `same_entity` is a **2-level hierarchy**: variant → page (L1), and page|single-variant → family (L2).

```
item:scythe-of-vitur-family  {is_family:true}     ← "all scythes of vitur"
   ▲ same_entity (member → family, basis)
   ├── item:scythe-of-vitur          (page, basis: base)        ─▶ Charged/Uncharged variants
   ├── item:holy-scythe-of-vitur     (page, basis: ornament_kit)─▶ Charged/Uncharged variants
   ├── item:sanguine-scythe-of-vitur (page, basis: ornament_kit)
   ├── item:corrupted-scythe-of-vitur(page, basis: ornament_kit)
   └── item:22664                    (single variant, basis: broken)   [Scythe of vitur (rotten)]
```

**Anomalies handled explicitly (real `item_dictionary` data):**
- **Multi-canonical page** — `Ring of suffering (i)` has 6 variants with **3** `is_canonical` rows (wiki
  `default_version` fires per imbue-source). `is_canonical` is per-variant metadata; the **page node** is the anchor
  regardless, so multi-canonical needs **no special logic** — the builder must just *not assume singular*. Disclosed
  in provenance.
- **Source-duplicate ids** — `Salve amulet(i)` = ids 12017/25250/26763 (NMZ / Soul Wars / Emir's Arena) are the
  *same item, different obtain-source*; L1 keeps them as three variants distinguished by `version_anchor` — the
  purest `same_entity` case.

Resolution: "all scythes of vitur" → family node → its `same_entity` in-edges (member pages) → each page's variant
in-edges. "Do I own any salve amulet?" → family `same_entity`-closure (two hops).

## 3. Components & data flow

```
data/item_dictionary.json (committed, wiki-Bucket-sourced) ──┐
data/item_node_exemplars.json (NEW: intra-page page_names) ──┤
data/item_node_families.json  (NEW: cross-page families,EDIT)─┤
referenced item ids (from committed edges/atoms) ────────────┘
   └─► kg_ingest/builders/items.py (NEW):
         build_items(dict_records, exemplar_page_names, family_records, referenced_item_ids) → (nodes, edges, groups=∅)
   └─► kg_ingest/assemble.py: rekey + dedup (same pipeline as build_diaries)
```

**`build_items` selection rule:**
- **Exemplar pages** (page_name ∈ exemplars) → import the **full intra-page family** (L1): page node + every variant
  node + a `same_entity` per variant.
- **Family member pages** (from `item_node_families.json`) → import each member page's **L1** (page+variants, or a
  single variant node if the member page has one id) **plus** the **L2** family node + a `same_entity` (member →
  family) per member.
- **Referenced item ids** not covered above → import the **single variant node** from the dict (richer than today's
  bare supporting node: gains name/members), **no page node, no bridge** (not claiming page completeness). Promotable
  later (link-don't-merge).
- Dedup by id across all sources (an id reached via both an exemplar and a referenced ref is imported once).
- Nothing else is imported (un-referenced, non-exemplar items stay out until a later scale-up).

## 4. Handoff with `build_supporting` (link-don't-merge, no dedup conflict)

`build_items` becomes the **owner** of every item id it emits. In `assemble.py`, those ids are added to `owned_ids`
**before** `build_supporting`, so the existing `referenced - owned_ids` subtraction stops `build_supporting` from
re-minting them (exactly how diaries are already excluded). `build_supporting` still mints any *other* referenced
leaf id, so the graph stays referentially whole and **byte-stable**. Ordering: existing builders → collect
references → `build_items(referenced_item_ids ∪ exemplar_families)` → add to `owned_ids` → `build_supporting`.

## 5. Additive engine/schema changes (spec permits "new edge", additively)

- **`model.py`**: add `EdgeType.SAME_ENTITY = "same_entity"`. (The schema already declares `same_entity`; the
  tested invariant `model-enum ⊆ schema` stays green.)
- **`kg/schema.json`**: flip `same_entity` status `reserved` → `live`; add `"is_page"` to the `item` kind's declared
  `data_keys`; note in the `item` kind that page-identity nodes are slug-keyed (`item:<page-slug>`), variants are
  cache-id-keyed.
- No new node kind (page + variant are both `kind = item`).

## 6. Bounded subset — two committed files

### 6a. `data/item_node_exemplars.json` — intra-page (L1 only, auto)

A list of page_names whose full intra-page family is imported. Each verified genuinely multi-variant in
`item_dictionary.json`. Shape:
```json
{ "_provenance": {"note": "intra-page multi-variant exemplars (L1)", "accessed": "..."},
  "records": ["Amulet of glory", "Ring of dueling", "Ring of wealth", "Slayer ring", "Dragon dagger"] }
```
Verified counts (records/canonical): Amulet of glory 7/1, Ring of dueling 8/1, Ring of wealth 6/1, Slayer ring 8/1,
**Dragon dagger 4/1** — **33 variants + 5 pages + 33 `same_entity`**. Four are charge-family jewellery; **Dragon
dagger** broadens to a **weapon** with a **poison** axis and **textual** anchors (`Unpoisoned`/`Poison`/`+`/`++`).

### 6b. `data/item_node_families.json` — cross-page (L1 + L2, EDITORIAL)

Curated, **source-grounded** family map (decision 9 / owner editorial gate). Each record carries `source_url` +
verbatim `source_token`. Shape:
```json
{ "_provenance": {"note": "curated cross-page families (L2); editorial — owner-reviewed", "license": "CC BY-NC-SA 3.0"},
  "records": [
    { "family_name": "Scythe of vitur (all variants)", "slug": "scythe-of-vitur-family",
      "members": [ {"page": "Scythe of vitur", "basis": "base"},
                   {"page": "Holy scythe of vitur", "basis": "ornament_kit"},
                   {"page": "Sanguine scythe of vitur", "basis": "ornament_kit"},
                   {"page": "Corrupted scythe of vitur", "basis": "ornament_kit"},
                   {"page": "Scythe of vitur (rotten)", "basis": "broken"} ],
      "source_url": "https://oldschool.runescape.wiki/w/Scythe_of_vitur", "source_token": "<verbatim phrase>" } ] }
```
The 6 seed families (verified pages / ids in `item_dictionary.json`):

| Family | Member pages | ids | L1 nodes |
|---|---|---|---|
| Salve amulet | `Salve amulet`, `(e)`, `(i)` (3), `(ei)` (3) | 8 | 2 pages + 8 variants |
| Scythe of vitur | base, Holy, Sanguine, Corrupted, `(rotten)` | 9 | 4 pages + 9 variants |
| Ring of suffering | base, `(i)` (6; **3 canonical**) | 8 | 2 pages + 8 variants |
| Bow of faerdhinen | base, `(c)` (**core only**; 9 per-Elf-house/league cosmetics deferred — see §10) | 3 | 1 page + 3 variants |
| Crystal pickaxe | `Crystal pickaxe`, `(The Gauntlet)` | 3 | 1 page + 3 variants |
| Infernal axe | base, `(or)`, `(or) (Trailblazer Reloaded)` | 6 | 3 pages + 6 variants |

Families total: **37 variants + 13 pages + 6 family nodes**, ~32 L1 + ~18 L2 `same_entity` edges. Combined with 6a
and the referenced-item half (computed at assemble time), the slice adds ≈ **90 item-related nodes** — bounded and
fully verifiable, exercising intra-page, ornament-kit, imbue, source-duplicate, multi-canonical, single-variant, and
cross-page identity in one proof.

## 7. Competency-questions gate (decision 9, seeded minimally)

- **`kg/competency_questions.json`** (NEW): questions the graph must answer. Seed with two — one per level:
```json
{ "records": [
  { "id": "cq-item-variants-amulet-of-glory", "question": "What are all variants of the Amulet of glory?",
    "method": "same_entity_members", "target": "item:amulet-of-glory", "expect_min": 5 },
  { "id": "cq-item-family-scythe-of-vitur", "question": "What are all Scythes of vitur (every kit)?",
    "method": "same_entity_family", "target": "item:scythe-of-vitur-family", "expect_min": 5 } ] }
```
- **`tests/kg_ingest/test_competency_questions.py`** (NEW): loads the committed KG, runs each question's `method`
  (`same_entity_members` = `same_entity` in-edges of `target`; `same_entity_family` = two-hop family→pages→variants),
  asserts `expect_min`/membership. Establishes the gate; grows question-by-question as later slices add structure.

## 8. Validation & success criteria (all must hold)

- `validate_kg` **exit 0** — item nodes + new `same_entity` edges VIOLATION-clean (schema `same_entity` domain/range
  `*` already permits the bridge; page nodes are `kind=item`).
- `assemble` **byte-stable** (re-run → identical bytes).
- **Golden tests stay green** (referenced item ids resolve unchanged; nodes only gain `data`).
- New **TDD** tests: L1 page+variant+`same_entity` structure; single-variant case (no page/bridge); `is_canonical`
  carried; **multi-canonical** page tolerated (Ring of suffering (i)); **L2** family node + member→family bridges
  (page-member and single-variant-member); the `build_supporting` handoff (no conflicting item definitions); schema
  invariant accepts `same_entity` (L1 and L2).
- Both seeded **competency questions** pass.
- **Editorial source-grounding gate** for the curated L2 file — `data/verify_item_families.py` (NEW, follows the
  `verify_diary_rewards.py` pattern): every `item_node_families.json` member `page` resolves in `item_dictionary.json`,
  every record carries `source_url` + a verbatim `source_token`, family slugs are unique and don't collide with a
  base page slug. **Owner editorial review of the family map is a hard human gate before merge.**
- Full `pytest` green (the 4 pre-existing `drop_rates` collection errors excepted).

## 9. Out of scope — named follow-ups (not this slice)

**Node-layer (step 2) follow-ups:**
1. **Intrinsic attrs** on variants: `value`/high-`alch`/`weight`/**`tradeable`**/`buy_limit`/equip slot — extend the
   `infobox_item` Bucket query (`build_item_dictionary.py`) to persist them, then carry onto variant `data`.
2. **`equipment_bonuses` facet + `has_bonuses`** — the combat-bonus block (BIS substrate), from the `infobox_bonuses`
   Bucket.
3. **Full item roster** scale-up (drop the bounded subset; import every `item_dictionary` record).
4. **`npc` / `scenery` / `place`** node imports — each a new `infobox_*` Bucket builder (the repeatable pattern).
5. **Aliases** (wiki redirects, bulk) + the search-resolution layer.

**Edge-layer (step 3) follow-ups — attach to the nodes this slice creates:**
6. **Charge / recharge recipe edges** — the *first edge-layer slice*, and the natural next step after this one.
   A `recipe` reified relation per charged item: `consumes`(charge materials + the uncharged variant) →
   `produces`(the charged variant), with optional `requires_facility`/location. E.g. Scythe of vitur = blood runes +
   vials of blood; Ring of suffering = rings of recoil; Trident = chaos/death/fire runes + coins; Glory = the
   Fountain of Heroes. Per-item materials/qty/facility are **source-grounded** from the wiki (`Bucket:Recipe`) and
   editorially reviewed. Charge **state** is already on the variant node (`version_anchor`); this adds the **process**.
   Needs the material item nodes (blood rune, vial of blood, ring of recoil…) to exist — which is exactly why nodes
   come first.

**Optional later:**
7. **Cache / RuneLite** path — completeness backstop for entities the wiki lacks.

## 10. Open micro-items (non-blocking, settle in implementation)

- **Bow of faerdhinen** per-Elf-house/league cosmetics (9 pages: Amlodd/Cadarn/Crwys/Iorwerth/Ithell/Meilyr/
  Trahaearn/LMS/deadman) are **deferred** — pure cosmetic recolors, low planner value. Family seeds with the **core**
  (base + `(c)`); the cosmetics are **disclosed** (in `_provenance`), never silently dropped. Promotable later.
- **Multi-canonical pages** (Ring of suffering (i): 3 `is_canonical`) — disclosed in the builder's provenance; the
  page node anchors regardless. Builder must not assume a single canonical.
- Two distinct pages slugifying to the same slug → `dedup_nodes` raises (surfaced, not silent); handle if hit.
- Family slug collision with a base page slug avoided by the `-family` suffix; verifier enforces uniqueness.
- Whether the page/family node carries `members` (currently identity-only; revisit if a query needs it).
- `same_entity` direction is member → anchor (variant→page, page→family), matching spec §3 `any → existing node`.
