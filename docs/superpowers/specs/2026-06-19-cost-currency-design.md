# Cost / Currency Layer — Design (v1)

**Status:** design approved 2026-06-19; spec under review → implementation plan next.
**Brick:** `feat/cost-currency`. Builds on the merged goal-engine (PR #5) + knowledge graph (PR #6).
**Companions:** `research/currency-model.md` (draft model), `research/wiki-source-catalog.md` (data sources), engine↔advisor contract (`docs/superpowers/specs/2026-06-15-engine-advisor-contract-design.md`, §5.5/§8/§10/§13).

---

## 1. Purpose & scope

The cost layer answers, for any goal item: **"what does it cost to acquire, and how does that differ by account type?"** It is the `expand_for_account` overlay the contract reserved — the engine decides *what is required* (account-type-blind); this layer decides *how you get it and what it costs* (account-type-aware).

**v1 delivers:** live-**gold** cost + account-type **channel divergence** (a main GE-buys; an ironman shops / produces / picks up), computed over real datasets. The **effort/time** dimension (earn-rates, gather-times, gp/hr, kill-rates) is a present-but-empty *skeleton* slot, filled when rate data lands.

**v1 does NOT:** rank by time/long-term value, read the player's current bank/inventory/balances, price `drop` or reward channels (incl. probabilistic rewards), fetch live prices on the request path, or normalize non-coin currencies to time. All are designed-for but deferred (§9).

### Guiding principles (locked)
- **Engine = structure, cost = overlay.** One-directional dependency; the KG stays cost-free.
- **Never auto-pick.** The output lists *all* viable routes; selection stays with the player/advisor (extends [[player-motivation-efficiency-fun]]).
- **Gold now, time later.** Every channel's gold cost is computable today; the time slot is wired but empty.
- **Absence ≠ zero.** Unknown balances stay unknown; v1 quotes full cost from scratch.
- **Data correctness via committed validator + golden set** (the iron-gate / kg-ingest discipline, [[feedback-data-validator-pattern]]).

---

## 2. Architecture

A new package `src/osrs_planner/cost/`, sibling to `engine/`. `cost` imports from `engine` (`AccountState`, `account_family`); **`engine` never imports `cost`** — same one-way boundary as the deferred advisor. All price/channel data is joined by `item_id` *outside* the knowledge graph; `kg/*.json` gains nothing.

```
src/osrs_planner/cost/
  prices.py     PriceProvider interface + SnapshotPriceProvider (reads data/ge_prices.json).
                LivePriceProvider (daily-refresh cache) is a later drop-in on the same interface.
  currency.py   Currency reference-table loader + Currency model.
  channels.py   Channel taxonomy (enum) + per-channel dataset loaders + the item->channels index.
  routing.py    price_routes(item_id, family, ...) -> list[Route]  (recursive acquisition walk).
  cards.py      CostCard + Route (pydantic output).
  overlay.py    expand_for_account(goal_id, state, price_provider) -> CostCard  (public entry).
```

- **Input:** a goal/item id + `AccountState` + a `PriceProvider` + the loaded channel datasets (+ the KG, read-only, to resolve a goal node → its item needs and to populate the strategic-timing hook).
- **Output:** a `CostCard`.
- **Why:** delivers the working slice while preserving the architecture; the `PriceProvider` interface is the single seam where snapshot → daily-refresh → live all plug in.

---

## 3. Data model

### 3.1 Currency reference table — `data/currencies.json`
A currency is a **cost denomination**, not a prerequisite (reference table, not a KG node-kind). Per-record:

| field | meaning |
|---|---|
| `id` | `currency:<slug>` (e.g. `currency:coins`, `currency:tokkul`) |
| `name` | display name |
| `category` | `physical_tradeable` \| `physical_untradeable` \| `physical_fare` \| `virtual` |
| `is_item` | banked item vs on-record-only |
| `ge_tradeable` | essentially only coins / platinum tokens |
| `observable` | `hiscores` \| `plugin` \| `plugin_or_unknown` \| `none` |
| `source_activity` | KG node id that produces it (nullable) |
| `earn_rate_per_hour` | **null in v1** (skeleton) |
| `self_earned_only` | no market → converges main-vs-iron |
| `example_sinks[]` | `{item, name, amount, note}` |

Seeded with `coins` + the non-coin currencies the sourced channels reference (e.g. `tokkul` for the obby maul). `self_earned_only` is the **convergence mechanism**: a currency with no market has no cheaper main route, so items priced in it converge structurally.

### 3.2 Channel taxonomy (all 8 defined)
`ge` · `shop` · `craft` · `gather` · `spawn` · `drop` · `quest_reward` · `activity_reward`.

### 3.3 Channel datasets (5 sourced in v1)

| Channel | Dataset | Key fields | Gold cost | Account rule |
|---|---|---|---|---|
| `ge` | `data/ge_prices.json` ✓ | (via PriceProvider) | live price | **main only** |
| `shop` | `data/shop_prices.json` *(new — Bucket `storeline` + Currencies join)* | shop, item_id, buy_price, currency, stock, sold_by | buy price (in its currency) | both |
| `craft` | `data/recipes.json` *(new — Wiki production data)* | output_item_id, skill, level, inputs[], output_qty | Σ priced inputs ÷ output_qty | both |
| `gather` | `data/gather.json` *(new — Wiki Farming/Fishing/Mining/WC/Hunter)* | resource_item_id, skill, level, inputs[] (seeds/bait/compost) | Σ priced inputs (often ~0) | both |
| `spawn` | `data/spawns.json` *(new — Wiki item-spawn locations)* | item_id, locations[], count | **0** | both |

### 3.4 Shared channel record shape
Every channel record normalizes to one shape so the walk doesn't branch per type:
```
ChannelRecord {
  item_id, channel,
  cost: { currency, amount } | computed-from-inputs,
  inputs: [ { item_id, qty } ],     # empty for buy/spawn; present for craft/gather
  account_allow: [ "main" | "ironman" | "uim" ],
  yield: 1,                         # SKELETON: distribution for probabilistic sources later
  time: null,                       # SKELETON: filled when rate data lands
  source,                           # shop/location/skill reference
  # account-gate fields (iron-gate discipline):
  audience, pricing_basis, realization_channel, requires_ge
}
```
The loader builds an **`item_id → [ChannelRecord]` index** — the per-item acquisition index the engine/data lacked. The routing walk reads only this index + the `PriceProvider`.

### 3.5 Account-allow rules (v1)
`ge` → `main` only. All other channels → both families. UIM no-bank and GIM intra-group-trade nuances are deferred (§9).

---

## 4. The routing walk (`routing.py`)

`price_routes(item_id, family, provider, index, owned=∅, _visited=∅, _depth=0) -> list[Route]`

It **walks the acquisition tree**: an item's routes may recurse into inputs that are themselves items with routes, down to leaves that have a direct price.

1. Enumerate the item's channels from the index; keep those whose `account_allow` includes `family`.
2. Price each channel's gold cost:
   - `ge`: `provider.ge_price(item_id)` (tradeable + family allows).
   - `shop`: shop `buy_price` (in its `currency`).
   - `spawn`: `0`.
   - `craft` / `gather`: `Σ price_routes(input).cheapest_gold × qty ÷ output_qty` (recurse), plus the skill/level requirement recorded (not a gold cost).
3. **Cycle / depth safety:** an item id in `_visited` is skipped for that branch; a depth cap backstops pathological recipes (mirrors the engine's acquisition-cycle guard).
4. **Unpriceable channel:** a channel with no gold figure (e.g. GE price missing, or an input that bottoms out in a deferred channel) yields `gold_status: unavailable` + a `time_status: not_estimated` marker rather than a fabricated number.
5. Return **all** priced routes (the card ranks/presents; the walk never collapses).

**Account divergence emerges, not hard-coded:** a main's allowed set includes `ge`; an ironman's excludes it, so the ironman's cheapest is drawn from shop/craft/gather/spawn. Self-earned-currency convergence falls out (no `ge` route exists for that currency).

The `owned` set (default empty in v1) is threaded but unused — when the state layer lands, an owned item/input short-circuits to cost 0.

---

## 5. Output — `CostCard` (multi-route, no auto-pick)

```
CostCard {
  item_id, name, account_family,
  routes: [ Route ],          # ALL viable routes for this family
  rankings: {
     by_gold: [route-index…], # computed in v1 (ascending gold)
     by_time: []              # SKELETON: empty until rate data
  },
  notes: [ … ],               # strategic-timing hook: downstream goals this item feeds (from the KG)
  gold_status                 # known | partial | unavailable (rolled up)
}
Route {
  channel, currency, gold_cost | null, gold_status,
  inputs: [ Route ],          # recursive sub-routes (craft/gather)
  time_status: "not_estimated",
  account_allowed, source, notes
}
```
The card **tags facts** (e.g. gold-cheapest) as information but **never names a single "best"** — selection is the player's/advisor's. For a composite goal (e.g. full Infinity = 5 pieces) the overlay resolves the goal node to its item needs, prices each, and returns a roll-up with per-item breakdown.

**Edge cases:**
- Routes with `gold_status: unavailable` (e.g. a `craft` route bottoming out in a deferred channel) are **listed but sorted last** in `by_gold` — never given a fabricated number.
- If **no** channel is allowed for the family (e.g. a tradeable item a main reaches only via GE, which an ironman cannot use and which has no shop/produce/spawn route), `routes` is empty and `gold_status: unavailable` with an explanatory note — the cost-layer analogue of the contract's *Unacquirable* / impossible-for-mode.

**Strategic-timing hook:** because the KG knows "item X is a prerequisite for quest Z (later)" and this layer knows "X is cheap/free now," `notes` carries the downstream goals an item feeds — so the advisor can later surface "grab it now, you'll need it for Z." v1 records the hook; it does not *rank* by long-term value.

---

## 6. Balances & observability

v1 computes the **full cost from scratch** — it assumes none of the item or its inputs is owned. It does **not** read bank / inventory / currency balances (the deferred per-account state layer / RuneLite bank ingest). Absence ≠ zero: an unknown balance stays unknown; we quote full cost rather than assume possession. The `owned` parameter on `price_routes` (default empty) is the wired-but-unused seam for later subtraction.

---

## 7. Price freshness

v1 ships `SnapshotPriceProvider` reading the committed `data/ge_prices.json` (deterministic, testable — like the kg-ingest golden set). The **daily-refresh seam** is designed: a `LivePriceProvider` (or a scheduled re-fetch into the cache) drops into the same `PriceProvider` interface. The refresh **job** is a follow-up, not v1. The committed snapshot **preserves `capturedAt` in the data file**, but in v1 the cost layer's API does **not yet surface staleness** to callers (the `LivePriceProvider` / refresh seam that would expose it is deferred, §9) — `capturedAt` is retained against that future, not consumed today. The price-missing half **is** implemented: `gp_status` degrades to `unavailable` when a price is missing.

---

## 8. Validation & proof

### 8.1 `data/validate_cost.py` (committed validator, iron-gate tradition)
- Every channel record's `item_id` resolves against `item_dictionary.json`.
- Every `currency` ref resolves against `currencies.json`.
- Account-gate fields consistent: **no `ge` channel is marked iron-eligible** (`requires_ge`/`audience` coherent).
- `craft`/`gather` `inputs` resolve to real items.
- **KG stays cost-free:** no price/cost/currency fields leak into `kg/*.json`.
- Shop `currency` values join to `currencies.json`.
- Byte-stable builders + a **committed == freshly-built freshness guard** (the kg-ingest lesson: a builder edit that forgets to regenerate fails the suite).

### 8.2 Golden cost-set (hand-verified, via real datasets + `SnapshotPriceProvider`)
- **Dragon scimitar** — main = `min(GE ~59k, shop 100k)` = GE; ironman = shop 100k *(flagship divergence)*.
- **Obby maul (Tzhaar-ket-om)** — main GE; ironman = Tokkul *(non-coin currency surfaces)*.
- **A potion** (simple Herblore item) — the `craft` route recurses into its inputs and picks the **cheapest route per input regardless of account type** (the cheapest-route walk takes `gather` for BOTH families when gather beats GE, which it does for the herb). The main/iron **divergence** is structural, not "main=GE inputs / iron=gather inputs": the main also has a cheaper direct buy-the-finished-item GE route (so it never needs to craft at all), while the ironman has no GE route anywhere and its entire craft recursion bottoms out GE-free (shop/gather leaves) *(recursion + herb→potion chain)*.
- **Voidwaker** — main = `min(buy assembled, assemble-from-3-components)`; ironman = assemble. In v1 the **ironman Voidwaker card is `unavailable`**: the 3 components are drop-only and `drop` is a deferred channel (§9), so the iron has no priceable route until the drop channel lands. The iron Voidwaker becomes priceable only once `drop` is sourced.
- **Full Infinity** — 5 pieces summed.
- Each test asserts the **full route set + gp-ranking** — never a single collapsed winner (enforces no-auto-pick).

---

## 9. Deferred / skeleton inventory (wired but empty)

- `time` / `yield` / `earn_rate` fields — present, null/default; fill when skill-rate baselines land ([[reference-method-rate-data-sources]], `research/skill-rate-baseline-task.md`).
- `drop` + `quest_reward` / `activity_reward` channels — defined, datasets not sourced, **including probabilistic rewards in general** (loot tables / random containers), which need the expected-value × rate model (a `yield` distribution).
- `LivePriceProvider` + daily-refresh job — seam designed; job is a follow-up.
- Reading player balances / inventory / currency — the state layer; `owned` param wired, unused.
- Non-coin currency → **time normalization** (the "75k Tokkul ≠ < 209k gp" trap) — needs earn-rates.
- Account-state cost modifiers (diary / glove shop discounts) — channel records can carry conditional prices later.
- GIM intra-group trade / UIM no-bank nuances.
- `time` / long-term **ranking dimensions** in `CostCard.rankings` — gold-only in v1.

---

## 10. Success criteria

1. `expand_for_account(goal_id, state, provider)` returns a `CostCard` listing **all** viable routes for the account family, with a gp-ranking, for the golden-set goals.
2. The flagship divergence holds on real data: scimitar main = GE, ironman = shop; obby maul ironman = Tokkul.
3. A potion's `craft` route recurses into inputs, picking the cheapest route **per input regardless of account type** (gather wins for both when it beats GE). The main/iron divergence is that the main has a cheaper direct buy-the-finished-item GE route (so it skips crafting), while the ironman has no GE route at all and its whole craft recursion is GE-free.
4. `data/validate_cost.py` exits 0; datasets are byte-stable and committed == freshly-built.
5. The KG remains cost-free; `engine` does not import `cost`.
6. The full suite stays green; the cost layer is additive.

---

## 11. Open questions / risks

- **Sourcing effort:** `shop_prices`, `recipes`, `gather`, `spawns` are four new datasets. Each is bounded (storeline ~6.2k rows; production/farming tables are structured Wiki data), but sourcing is the bulk of v1 work — the plan should sequence them so a thin vertical slice (GE + shop, scimitar divergence) lands first and the others extend it.
- **Recipe/gather coverage:** v1 need not cover every recipe — only enough to price the golden-set goals + a representative potion. Coverage breadth is a plan decision; disclose residuals.
- **Non-coin comparison:** with `earn_rate` null, the card cannot rank a non-coin route against a coin route by effort — it presents both, tags the coin one's gold, and marks the non-coin `time_status: not_estimated` (no face-amount comparison — avoids the Tokkul trap).
- **Strategic-timing hook scope:** v1 records downstream-goal references in `notes`; it does not compute long-term value. Confirm this is enough for now.
