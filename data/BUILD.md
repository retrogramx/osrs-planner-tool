# Data foundation — how it's built & reproduced

Each `data/<domain>.json` is a frozen-envelope dataset (`{_provenance, records, _excluded}`)
built from OSRS Wiki / RuneLite sources. This file maps every dataset to the script that
produces it and its reproducibility status.

## Pipeline shape

```
fetch raw  ──►  build/parse  ──►  account-gate  ──►  validate
(data/raw/*)    (script→JSON)     (gate fields)      (validate_iron_gate.py)
```

- **Raw inputs** live under `data/raw/` and are **gitignored** (large, re-fetchable from each
  dataset's `_provenance.source_urls`). The **`.py` extraction scripts** under `data/raw/` **are
  tracked** (a `.gitignore` exception) so every dataset's build is reproducible.
- **Licenses:** OSRS Wiki content = CC BY-NC-SA 3.0; banked-experience / RuneLite `ItemID` = BSD-2
  (attributed in `banked_xp_dataset.json._provenance`).

## Account-type gate (the project's correctness moat)

Five money/economy domains carry the canonical gate fields
`{audience, pricing_basis, realization_channel, requires_ge}`:
`money_making`, `bosses_pvm`, `ironman_money_making`, `account_cost_split`, `skills_training`.

**`data/validate_iron_gate.py` enforces the invariants** (run it in CI / pre-commit):
1. No GE buy-process-sell / flipping method (`requires_ge`) is ever iron-eligible.
2. No equippable tradeable unique (rings/whips/fangs/claws) is ever counted as iron income.
3. The four gate fields are present on every record across the five domains.

```
python3 data/validate_iron_gate.py
```

## Per-dataset builders

| Dataset | Builder(s) | Reproducible? |
|---|---|---|
| `money_making.json` | `data/build_money_making.py` | ✅ core gate fully reproducible¹ |
| `bosses_pvm.json` | `data/parse_bosses_pvm.py` → `data/_polish_bosses_pvm.py` | ✅ fully |
| `items_equipment.json` | `data/fetch_items_equipment.py` → `data/parse_items_equipment.py` → `data/add_item_id_to_items_equipment.py` → `data/reresolve_item_id_against_dictionary.py` | ✅ |
| `item_dictionary.json` | `data/build_item_dictionary.py` | ✅ |
| `banked_xp_dataset.json` | `data/reresolve_banked_xp_via_itemid.py` (+ `reresolve_banked_xp_against_dictionary.py`) | ✅ |
| `combat_achievements.json` | `data/parse_combat_achievements.py` | ✅ |
| `clue_scrolls.json` | `data/parse_clue_scrolls.py` | ✅ |
| `account_cost_split.json` | `data/build_account_cost_split.py` | ⚠️ `realization_channel` added by a gate step not preserved² |
| `skills_training.json` | `data/raw/parse_html.py` + `data/raw/account_cost_split/apply_p1_gate.py` (gate) | ✅ (gate script tracked) |
| `quests.json` | `data/raw/parse_quests.py` / `parse_questreq.py` | ✅ |
| `minigames.json` | `data/raw/parse_minigames.py` | ✅ |
| `collection_log.json` | `data/raw/parse_collection_log.py` | ✅ |
| `achievement_diaries.json` | `data/raw/parse_diaries_authoritative.py` → `data/raw/assemble_diaries_envelope.py` | ✅ |
| `optimal_quest_order.json` | `data/raw/extract_oqg.py` | ✅ |
| `unlocks_transport.json` | `data/raw/parse_unlocks_transport.py` | ✅ |
| `ge_prices.json` | `prices.runescape.wiki` `/latest` + `/mapping` (raw: `data/raw/ge_latest.json`) | ✅ |
| `ironman_money_making.json` | **agent extraction** (no script; semi-structured wiki page) | ⚠️ agent-built |

¹ `money_making.json`'s core account-gate (`audience/pricing_basis/realization_channel/requires_ge/iron_eligible`)
is fully reproducible from `build_money_making.py`. The `iron_realizable_value` estimate is **carried forward**
from PR #3's original recompute (script not preserved; values known imperfect) — a correct, reproducible
iron-income recompute is a tracked follow-up. See `money_making.json._provenance.notes`.

² `account_cost_split.json`'s `realization_channel` was applied by a one-off gate step that was not preserved;
the field is correct in the committed data but not yet re-derivable from `build_account_cost_split.py` alone.
Tracked as a reproducibility follow-up.

## Cost-layer data (`src/osrs_planner/cost/`)

The cost overlay reads hand-curated channel datasets — `currencies.json`,
`shop_prices.json`, `recipes.json`, `gather.json`, `spawns.json` — plus the
GE snapshot (`ge_prices.json`) and `item_dictionary.json`. The item→channels
index is built **in-memory at load** (no committed derived artifact), so there
is no index freshness-guard; the validator below is the sole gate.

**`data/validate_cost.py` enforces the cost-layer invariants** (design §8.1; run
it in CI / pre-commit):
1. Every channel record `item_id` resolves in `item_dictionary.json`.
2. Every `currency` ref resolves in `currencies.json`.
3. `craft`/`gather` `inputs` item_ids resolve in `item_dictionary.json`.
4. Gate coherence: no `ge` channel is iron-eligible (`requires_ge=True` AND
   `account_allow == {"main"}`).
5. The KG stays cost-free: no `price`/`cost`/`currency` token in `kg/*.json`.
6. Shop `currency` values join to `currencies.json`.

```
python3 data/validate_cost.py
```

Channel-dataset coverage is the **golden-set goals + a small representative
sample** (scimitar/obby maul shops, the Guam potion craft chain, Guam-leaf
gather, Hammer spawn). **Bulk wiki sourcing** (Bucket storeline ~6.2k rows,
full production/farming/spawn tables, the full ~50 Currencies page) **is a
disclosed v1 follow-up**, stated in each dataset's `_provenance` and in the
validator's docstring.
