# Source-Grounded Shop Stock (Storeline) — Slice 7

> **Status:** DESIGN (2026-06-26). The first **source-grounded** connective slice — replaces the owner's hand-authored
> `sells` *shorthand* with the wiki's authoritative per-shop stock from `Bucket:Storeline`. Branch: continues on
> `feat/connective-varrock` (accumulating the connective vertical; slice 6 is its predecessor, not yet merged). Builds
> on the containment spine (place/npc/shop, slice 6) + the item resolver (slice 1) + the evaluator (quest/diary atoms).

## 0. Why this slice

Slice 6 shipped the containment spine but resolved only **23 of the owner's 50 authored `sells`**; the other **27 are
category/aggregate shorthand** the owner wrote editorially ("Bows", "Runes (most types)", "Daggers (bronze through
adamant)", "Staves") — not item names. `verify_map` reports them as a residual. Category-page expansion is the wrong
tool (a shop stocks a *subset* of a category, so it over-includes). The wiki's **`Bucket:Storeline`** is the
authoritative per-shop stock table — exact items, with prices/stock/currency — and it covers regular gp shops, not just
minigame-reward shops. This slice makes Storeline the **stock spine**: the owner's flat shorthand is superseded by the
exact wiki stock, while the owner's editorial **prose gates** (the Zaff diary/quest offers) survive as an overlay.

## 1. Decisions (settled in brainstorming, 2026-06-26)

| # | Decision | Choice |
|---|---|---|
| 1 | Source | **`Bucket:Storeline`** (per-shop stock), via the wiki **Bucket API**. NOT Category-page expansion. |
| 2 | Stock model | **Storeline = the stock spine.** It supersedes ALL of the owner's flat `sells` (including the 23 that resolved in slice 6). The owner's authored data retains only structure (slice 6) + the **prose gates** as an overlay. |
| 3 | Gate sourcing | **Structured gates from Storeline** (currency; **members recorded as edge DATA, not a cond_group** — Varrock is F2P-dominant + no members atom exists yet; the account gate is deferred). **Prose gates stay owner-authored** (the Zaff diary-discount + What-Lies-Below offers) — the wiki has these only as prose/bespoke tables; editorial authoring is the correct source. The owner's overlapping authored offers are **canonicalized/collapsed** into a clean gate set (§3), subject to **owner editorial review**. Skillcape/wield-level gates → deferred (item requirement, not shop data). |
| 4 | Scope | **Full bucket snapshot committed** (the ~6,237-row reproducible raw snapshot); **sells edges generated only for the 15 Varrock shops** already in the graph. Future towns need no re-ingest. |
| 5 | Pricing | **Deferred.** The snapshot retains `store_buy_price`/`store_sell_price`/`store_stock` for the future cost layer; the `sells` edges carry `currency` + `members` only. No price tokens enter the graph (`validate_cost` stays clean — the slice-6 deferral). |

## 2. The data source — `Bucket:Storeline`

**Schema (verified live, 2026-06-26):** `sold_by`, `sold_item`, `sold_item_image`, `store_buy_price`,
`store_sell_price`, `store_currency`, `store_delta`, `store_stock`, `store_buy_multiplier`, `store_sell_multiplier`,
`restock_time`, `store_notes` (consistently empty), `sold_item_json` (carries a `"Members":"Yes|No"` property).
**No structured requirements/condition field exists** — confirming gate prose lives elsewhere (decision 3).

**Query (Bucket API):**
```
https://oldschool.runescape.wiki/api.php?action=bucket&format=json&query=
  bucket('storeline')
    .select('sold_by','sold_item','store_currency','store_buy_price','store_sell_price','store_stock',
            'store_delta','restock_time','sold_item_json')
    .limit(10000).run()
```
`.limit()` must exceed the row count (≈6,237) — the default cap silently truncates (the slice-CA `.limit(5000)`
lesson). Filtering by shop is done client-side (`where('sold_by', …)` works but the build filters the full snapshot).

**Verified samples (the join + resolution work by exact name):**
- `sold_by="Varrock General Store"` → 13 items (Pot, Jug, Shears, Bucket, Tinderbox, Chisel, Hammer, Newcomer map,
  Security book, …), all `Coins`. (Resolves the owner's 3 category strings.)
- `sold_by="Blue Moon Inn"` → `sold_item="Beer"`, `Coins`. (`Beer` → the slice-6 page-name heuristic → `item:1917`.)
- Lowe's Archery Emporium → the 6 bows + 5 arrow tiers + bronze bolts + crossbow (exact, replacing "Bows"/"Crossbows"/
  "Ammunition").

## 3. The model — supersede flat sells, keep gates as overlay

**`build_map` (existing, slice 6):** keeps emitting place/npc/shop nodes + `located_in`/`operates`/`same_entity`.
**Stops emitting flat `sells` edges.** It still reads the owner's authored gate offers from `varrock.json` and passes
them (resolved to `(shop_id, item_id, cond_group)`) to `build_storeline` as the **gate overlay** (or exposes them for
`build_storeline` to consume). No node/edge regressions to containment.

**`build_storeline` (new):** the sole source of `sells` edges.
- Input: the Storeline records, the set of in-graph Varrock shop names, an `item_resolver`, and the owner gate overlay.
- For each Storeline row whose `sold_by` matches an in-graph shop:
  - resolve `sold_item` → `item_id` (`make_item_resolver`; skip + report on no/ambiguous match — never fabricate).
  - emit `sells`: `shop:<slug> → item:<id>`, `data = {currency: <store_currency>, members: <bool>, source_token}`.
    (`source_token` = the dataset provenance; bulk Bucket data is grounded by the snapshot + verifier, not per-row
    quotes — the `items_equipment`/`drop_rates` precedent.)
- **Gate overlay — canonicalize first, then apply (two cases):**
  - **Canonicalization (owner-reviewed):** the owner's authored gate offers are overlapping (Zaff has **6** battlestaff
    offers: quest `in_progress` *and* `completed`, all four diary tiers, noted vs unnoted). A one-time canonicalizing
    edit collapses each item's offers into a clean set — typically **base-unlock** (battlestaff gated by What Lies
    Below) + **one perk** (the diary daily noted allotment, gated by the minimum tier `diary:varrock:easy`; per-tier
    *quantity* is deferred with pricing/stock). This edit lands in `varrock.json` and is an **owner editorial-review
    checkpoint** (a validator cannot judge the collapse — the human gate). The builder then consumes the canonical gates.
  - **Case 1 — condition on a stocked item:** a canonical gate whose `(shop, item)` matches a Storeline-derived edge →
    attach its `cond_group` to that edge (the What-Lies-Below gate on Zaff's `Battlestaff`).
  - **Case 2 — a conditional offer with no Storeline row:** a canonical gate that is a distinct perk (the diary noted
    allotment, which Storeline does not itemize) → emit it as an **authored gated `sells` edge** (`data` marks it
    owner-editorial), reusing the slice-6 `cond_group` construction.
- **Ownership rule:** if the owner authored any gate for an `(shop, item)`, the overlay owns that item's edges; Storeline
  does NOT add a duplicate unconditional edge for it. Storeline supplies every item the owner did not gate. The verifier
  checks no Storeline edge duplicates a gated item.
- The owner's category-shorthand `sells` entries are **dropped** (superseded by Storeline); their loss is intentional,
  not a residual.

**Edges are shop-`src`** (like slice-6 sells) → they re-key in their **own** `rekey` call, NOT the item-`src` shared
rekey. Builder-local edge band disjoint from slice 6's `0xE0` (e.g. `0xF0`; the `_MASK` 28-bit guard holds). The global
edge-id-uniqueness assert is the backstop.

## 4. Item & shop resolution (reuse + extend the slice-6 lesson)

- **Item:** the existing `make_item_resolver(item_dictionary)` (canonical match + page-name disambiguation +
  noted-strip). Storeline `sold_item` values are real item names, so they resolve cleanly; true ambiguity → `None` →
  skipped + reported.
- **Shop:** `sold_by` (the wiki shop display name) → the graph shop node by **exact name match** (then a slug fallback).
  A graph shop with no matching `sold_by` rows, or a `sold_by` that matches no graph shop, is a **reported residual**
  (not a failure). The build skips unmatched shops; the verifier lists them.

## 5. Reproducibility + verifier

- **`data/fetch_storeline.py`** — runs the Bucket API query, writes the raw snapshot `data/raw/storeline_bucket.json`
  (the full bucket). Mirrors `data/fetch_items_equipment.py`. Dataset `_provenance` (source_url, accessed, license
  CC BY-NC-SA, query) recorded.
- **Deterministic parse** — the builder (or a `parse_storeline` helper) reads the committed raw snapshot; the committed
  graph is re-derivable from it offline. A `--refresh` mode re-queries live and diffs (the `audit_quest_requirements.py`
  reproduce-offline / freshness-online pattern).
- **`data/verify_storeline.py`** — source-grounding gate, **report-not-fail** on resolution/coverage residuals
  (the editorial-data lesson):
  - **Hard-fail (exit 1) — structural only:** a matched shop's `sells` dst is not a real item node; an owner gate that
    resolves to neither overlay case (case 1 nor 2); a `cond_group` ref that doesn't resolve to a real quest/diary node;
    a malformed currency; a Storeline edge that **duplicates an owner-gated item** (violates the §3 ownership rule).
  - **Report (exit 0) — residuals:** shops with no Storeline match; `sold_item` names that don't resolve. Printed with
    counts (the to-do for a future ambiguity/alias pass).

## 6. Assemble wiring

`build_storeline` runs **before the reference collection** (its resolved `sold_item` dsts feed `referenced_item_ids`
so `build_items` auto-imports the stocked items, like slice 6). `build_map` is called first (it produces the shops +
the gate overlay); `build_storeline` consumes the overlay. The storeline `sells` edges + their gate `cond_group`s
re-key in their **own** `rekey` call (shop-`src`); their groups merge into `groups`; `map_nodes` dedup unchanged. The
global edge-id assert covers them.

## 7. Validation & success criteria

- `assemble` **byte-stable** (re-run → identical bytes); global edge-id assert passes.
- `validate_kg` **exit 0** (`sells` VIOLATION-clean: `shop → item`, dsts resolve; cond_groups well-formed).
- `validate_cost` **exit 0** (NO price/currency *cost tokens*; `currency` is a descriptive string, not a cost).
- `verify_storeline.py` **exit 0** with a clean resolution + shop-match report; **the 27 categories are gone** — Varrock
  shops now carry their exact Storeline stock (Lowe's → bows+arrows+crossbow; Aubury → the exact runes; General Store →
  the 13 items).
- **Zaff's `Battlestaff` keeps its What-Lies-Below `cond_group`**; the Varrock-diary extra-stock offer survives as the
  authored gated edge.
- `verify_map.py` still exit 0 (it no longer reports the sells residual, since `build_map` no longer emits sells; or it
  is updated to drop the sells-resolution section, which moved to `verify_storeline`).
- Golden + slice-1..6 tests green. New **TDD** tests: `build_storeline` (a shop's Storeline rows → exact sells edges;
  the gate overlay attaches a cond to a stocked item AND emits a standalone diary offer; an unresolved `sold_item` is
  skipped+flagged, not fabricated; an unmatched shop is flagged); shop-name match; all-edge-ids-unique with the new
  shop-`src` family present.
- **+1 competency question:** *"What does Lowe's Archery Emporium stock?"* → `shop:lowes-archery-emporium` has `sells`
  out-edges to the expected bow/arrow item nodes (`method: "shop_stock"`, expect ≥ the known row count).
- Graph: the 15 shops gain their full Storeline stock + auto-imported items (the 27 categories → dozens of concrete
  item edges). Node/edge deltas recorded at build time.

## 8. Out of scope — named follow-ups

1. **Prose-gate parsing** — the bespoke per-shop diary-discount subsections + quest footnotes (decision 3); only if a
   structured source ever appears, or as a separate fragile-by-nature slice.
2. **All-shops scale-up** — generate `sells` for every `sold_by` in the bucket (thousands of shops); the volume step.
3. **Shop pricing / currency cost-model** — `store_buy_price`/`store_sell_price` → the cost layer; the currency model
   (coins vs reward points), iron realization, GE-vs-shop (decision 5).
4. **Skillcape / wield-level gates** — derived from the item's own equip requirement (the deferred wield-requirements
   slice), not shop data.
5. **Item aliases** — a name→id alias table for `sold_item` values the canonical resolver still misses (the residual
   the verifier reports).

## 9. Open micro-items (settle in implementation)

- **Shop-name match edge cases** — confirm all 15 `sold_by` values against the graph shop names; a mismatch (e.g.
  Aubury's exact wiki shop name) is a reported residual, not a build break. Verify which Varrock pubs have Storeline
  rows (Blue Moon Inn does; confirm the others).
- **`build_map` ↔ `build_storeline` overlay handoff** — whether the gate overlay is passed as a return value from
  `build_map` or read independently by `build_storeline` from `varrock.json`. Prefer an explicit handoff (one reader of
  the owner file).
- **Edge band** — `build_storeline` shop-`src` band disjoint from slice-6 map `0xE0` / group `0xD0`; pick `0xF0` edges,
  a free group band; confirm against `_MASK`.
- **`verify_map` sells section** — move the sells-resolution report out of `verify_map` into `verify_storeline` (sells
  no longer originate in `build_map`).
- **`members` — RESOLVED: data-only** this slice (recorded on the sells edge `data`); the account-property `cond_group`
  is deferred (no members atom yet; Varrock is F2P-dominant).
- **Gate canonicalization is an owner-review checkpoint** — the collapsed gate set (the `varrock.json` edit, §3) must be
  presented to the owner for editorial sign-off before merge; a validator cannot judge the collapse. The plan includes
  this checkpoint as a discrete task.
