# Loot Filter v4 — Storn-Structured, Data-Driven Design

**Goal:** Regenerate the Gilded Tome ironman loot filter in the structure of Storn's Iron
Filter — ~35 domain modules (Seeds, Herbs, Ores & Bars, gear-by-metal, bosses, clues, …), each
a cleanly editable section in the FilterScape UI, with editable tier-membership dropdowns and
per-tier colour pickers — driven entirely by our own data (`loot_families` + `loot_importance` +
the KG), never a copy of Storn's file.

**Owner asks (verbatim):** "I want to be able to edit any item in the game as well as see them as
part of a category/family like seeds" → "basically building upon Storn's filter" → full filter,
import time no object.

**Status:** design approved 2026-07-17. Builds on the now-importable quantity-tiers work
(`feat/loot-filter-quantity-tiers`, PR #29, which carries the FilterScape YAML-quote import fix).

---

## 1. Background & the two asks

The itemization (PR #28) + quantity-tiers (PR #29) work produced a filter that is *data-correct*
but presents families as a single flat 479-input `quantities` module with tier-encoded labels
("Quantities — Seeds / Seeds A (base A, >=1)"). The owner imported it and it "isn't what I
envisioned." The vision is **Storn's Iron Filter** (`github.com/Storn42/Iron-Filter`), whose UX
solves both asks natively within FilterScape's constraints:

- **"See items as part of a category/family like seeds"** → Storn ships **one module per
  family/domain**. "Seeds" is its own editable section.
- **"Edit any item in the game"** → FilterScape has **no item browser** (verified: its input-type
  enum is a closed 6-set — boolean, number, stringlist, enumlist, style, text — and its search box
  searches author labels only, never the item DB). Storn's two native mechanisms are:
  1. an **`enumlist`** per tier inside each family module — a dropdown of the whole family's items;
     move any item between tier dropdowns to re-tier it;
  2. a global **Hidden Items** module of **`stringlist`** inputs — type any item's name to hide it.

## 2. Non-goals & hard constraints

- **No global item browser / per-item colour picker.** FilterScape cannot render one. Per-item
  control is exactly the two mechanisms above (enumlist re-tiering + typed name-lists). This is a
  tool limit, not a scope cut.
- **Licensing.** Storn's `Iron-Filter.rs2f` is all-rights-reserved (no LICENSE file). We reuse only
  its **structure and UX pattern** as design reference — the `.rs2f` grammar and the enumlist/style
  input pattern are the plugin's, not Storn's IP. **Every item-list, default tier assignment,
  colour, beam, and hide-list is ours, derived from our KG / `loot_importance`.** No verbatim copy
  of his enum lists, styles, or hide-lists.
- **Area rules are IN (owner directive, 2026-07-17).** FilterScape fully supports
  `area:[x1,y1,z1,x2,y2,z2]` coordinate boxes — Storn uses them in 305 rules — and this needs **no
  KG chunk-geometry layer**: we source each box's coordinates from the wiki per boss/area (exactly as
  Storn hardcodes them) and disclose any we can't ground. Used to gate a boss's drop styling to that
  boss's arena (§6a).
- **No true "perfect kill" / on-task game-state condition exists.** The plugin has no such lever;
  Storn's `PERFECT_KILL_LISTS` is purely a big OR of arena `area:` boxes. We deliver the same *effect*
  the owner wants — a boss's drops styled only at that boss — via area boxes, honestly labelled as
  area-gating (not kill-quality detection). Per-boss "enable perfect-kill area" is a toggle like Storn's.
- **KG untouched.** This is filter-side only, like PR #28/#29. Data derivations live in `data/`.
- **Plain labels — no AI-sounding copy (owner directive, 2026-07-17).** Every module name,
  subtitle, group name, and input label the owner sees in FilterScape must be **simple, plain
  English**. **No em-dashes (`—`), no colons in labels, no clever/convoluted phrasing, no jargon.**
  Use short words a player reads at a glance: "Seeds", "Minimum quantity", "Colour", "Hide these",
  "SS tier". This retires the current em-dash/colon labels ("Quantities — Ammo", "Custom highlight
  1 — items", "Resource piles: base importance escalated by stack size"). Keep subtitles a plain
  short phrase ("Farming seeds", not "Resource piles: importance escalated by stack size").

## 3. Module taxonomy (~35 modules)

Ordered for first-match-wins (see §7). Each row is one FilterScape module.

| Wave | Module(s) | Data source | Notes |
|---|---|---|---|
| Frame | `settings` | existing | IRONMAN gate + global toggles (§8) |
| Frame | `custom` | new | user override highlights — WIN over all styling |
| Frame | `hidden` | new + junk-derive | user hide-lists; excludes clog/uniques |
| Content | `uniques` | `collection_log` + tailoring | missing-clog purple beams; never hidden |
| Content | **one module per boss + per raid** (e.g. `zulrah`, `vorkath`, `cox`, `tob`, `toa`, …) | `bosses_pvm` + `drop_rates` + wiki | **specific themed colours per boss** (§6b); arena `area:` box; unique tiers by rarity + hide commons + highlight supplies (heaviest wave) |
| Content | `slayer_monsters` | `bosses_pvm` (non-boss) | generic slayer/monster drops bundled (one module) |
| Content | `clues`, `clue_uniques` | existing `emit_untradeables` | per-tier seal colours (already built) |
| Families | `seeds`, `herbs`, `herblore_secondaries`, `runes`, `ores`, `bars`, `logs`, `planks`, `gems`, `ammo`, `food_pots`, `prayer` (bones/ashes), `essence` | `loot_families` + `loot_importance` | one family = one module (ores & bars split); tier-bucket pattern (§4) + ×10 escalation (§5) |
| Gear | metal: `bronze_gear` … `dragon_gear` (9) · non-metal: `ranged_armour`, `magic_robes`, `jewellery`, `other_gear` | gear name-lists + `emit_gear` + sprite sampling | metal = smithed sets; non-metal by type; `jewellery` coloured by **sprite** (§6c); `other_gear` = stat-tiered catch-all; boss/raid gear lives in its boss module |
| Utility | `currency`, `alchs`, `teleports`, `keys` | coins + HA realization + categories | `alchs` = High-Alch-realization items (§6d); `keys` = name-derived, disclose gaps (§6e). No per-charge module — charged jewellery is handled by `jewellery` sprite colour (§6c) |
| Frame | `fallback` | existing | cheap-loot text tier + HIDE_FLOOR cut |

Confidence: **high** for frame/families/gear/clues/currency (strong data, mostly existing code
reshaped); **medium** for per-boss modules (data exists in `bosses_pvm`+`drop_rates`, but one-per-boss
+ themed colours + arena boxes is the heaviest, owner-collaborated wave); **low/thin** for keys
(name-derived, disclose residual).

## 4. The per-family module pattern (Storn shape)

For family `F` (e.g. Seeds), for each base tier `T` in {SS, S, A, B, C, D, E} that has members:

```
/*@ define:input:seeds
label: "Items"
type: enumlist
enum: ["Ranarr seed", "Snapdragon seed", ... every seed name ...]
group: "SS tier"
*/
#define SEEDS_SS_NAMES ["<items we assign to SS by loot_importance>"]

/*@ define:input:seeds
label: "Minimum quantity"
type: number
group: "SS tier"
*/
#define SEEDS_SS_MIN 1

/*@ define:input:seeds
label: "Colour"
type: style
group: "SS tier"
*/
#define SEEDS_SS_STYLE textColor = "<identity hue @ SS emphasis>"; showLootbeam = true; ...

... rules referencing SEEDS_SS_NAMES (§5) ...
```

Labels stay plain (§2): the **group** is the tier ("SS tier", "A tier", …); inside it the inputs
are just "Items", "Minimum quantity", "Colour". No em-dashes, no colons, no jargon.

- **`enum`** = the full family roster (all seed names). Fixed option set the dropdown offers.
- **`#define …_NAMES [default]`** = which items start in tier `T`, **pre-filled from
  `loot_importance`** (Storn ships these empty; we ship sensible defaults). The user moves items
  between tier dropdowns to re-tier — this is "edit any item" within a family.
- **`…_STYLE`** = the tier's editable colour/beam (our identity hue + tier emphasis). Editing it
  reflows every item in the tier, including quantity-promoted ones (§5).
- **`…_MIN`** = hide below this stack count (Storn's per-tier min-quantity).

Item **names** (not ids) fill `enum`/`…_NAMES` and drive `name:` matching (readable + editable;
matches noted+unnoted; the usual variant caveat). We hold both name and id in `loot_importance`.

## 5. Quantity escalation, integrated with editable tiers

Preserve the ×10 model ("40 ranarr seeds is HUGE"): a stacked pile renders the **next tier up's
style**, capped SS. The escalation rules key off the editable `…_NAMES` macro, so re-tiering and
recolouring both flow through. For a base-A seed group (promote one grade per ×10 in count):

```
rule (IRONMAN && name:SEEDS_A_NAMES && quantity:>=100) { SEEDS_SS_STYLE }   # A + 2 decades
rule (IRONMAN && name:SEEDS_A_NAMES && quantity:>=10)  { SEEDS_S_STYLE }    # A + 1 decade
rule (IRONMAN && name:SEEDS_A_NAMES && quantity:<SEEDS_A_MIN) { hidden = true; }
rule (IRONMAN && name:SEEDS_A_NAMES) { SEEDS_A_STYLE }                       # base
```

Grade math is single-sourced from the existing `palette.quantity_display_grade` /
`GRADE_ORDER` / `_decades` (PR #29). SS-threshold-first preserves first-match-wins. This is the
current `emit_quantities` engine, refactored to (a) per-family modules, (b) editable enumlist
membership, (c) named per-tier style macros the ladder references.

## 6. Module-specific behaviour

**Colour sourcing (owner directive, 2026-07-17):** colours are **not arbitrary hues**. Resource
families keep their wiki-informed identity hues (coal dark, nature-rune green, etc.). Boss/raid
modules take colours **from the content's own visual identity** (the boss's/raid's wiki art + theme).
Jewellery is coloured by its **item sprite** (§6c). The tier→colour mapping and per-boss palettes are
**editorial, owner-collaborated** — same human-in-the-loop process that got the PR #12 potion liquids
right (sprite/wiki sourced, then corrected against the wiki with the owner).

### 6a. Boss/raid arena area-gating
Each boss/raid module gates its drop styling to that boss's arena with an `area:[x1,y1,z1,x2,y2,z2]`
box (the plugin supports this natively; §2). Coordinates are **sourced from the wiki per boss**
(owner can help) and disclosed where we can't ground them. A per-boss "Only in this boss's area"
boolean toggles it (Storn's "perfect kill" pattern, honestly named). This is what makes a boss's
uniques light up *at that boss* and not confuse the same item dropped elsewhere.

### 6b. Boss/raid themed colours (one module per boss)
One module **per boss and per raid** (`bosses_pvm` cardinality), not bundled. Each module: the boss's
**uniques** tiered by drop **rarity** (`drop_rates`, ULTRA/RARE/COMMON) into editable tier buckets
with **the boss's specific themed colours**; **commons** hidden below a value/importance cut;
**supplies** highlighted. Generic (non-boss) slayer monsters bundle into one `slayer_monsters` module.

### 6c. Jewellery by sprite colour
No per-charge jewellery tiers (owner directive — don't split "Ring of duteling(8)" vs "(7)"). Instead
the `jewellery` module colours each ring/amulet/necklace by the **dominant colour sampled from its
in-game sprite** (reuse the PR #12 technique: RuneLite item-icon cache → Pillow dominant-colour), so a
games necklace, ring of wealth, amulet of glory each read in their own colour. Charge count is ignored.

### 6d. Alchs — what counts
An **alch** is an item whose best ironman realization is **High Alchemy** (per `income/realize.py`:
coins + max(raw HA, craft-chain) — i.e. gear/junk you turn into gold with a nature rune, not a
keep-item and not clog). The `alchs` module highlights alchable drops **tiered by their HA value**, so
you can see at a glance what's worth alching versus dropping. This is our iron-valuation edge; Storn's
"Alchs / Turn Everything to Gold" module, backed by real numbers.

### 6e. Keys — thin data, explained
"Thin" means there is **no authoritative structured key list** in our data (unlike families, which come
from `loot_families`). Keys (Brimstone key, Larran's key, dungeon/chest/tooth/bones keys, boss keys)
are **derived by name-matching** (`* key` + a curated known-key set) and **the residual is disclosed**,
never fabricated. If a key doesn't resolve to a real item id, it's left out and reported, not invented.

### 6f. The "edit any item" catch-all (`hidden` + `custom`)
**`custom`** (near the top → wins): paired `stringlist` (type item names) + `style` inputs, N free
slots + per-tier inject slots. Empty/inert by default. Type "Ranarr seed" → your colour/beam,
overriding its family style. This is our existing `emit_custom_highlights`, kept and promoted.

**`hidden`**: `stringlist` inputs mirroring Storn — "Hide these", "Hide if under 10 / 100 / 1000",
plus a "Hide fake items" boolean. The default hide-list is **seeded from our own low-importance junk**
(bottom-tier, low-HA, non-clog, non-recommended items), never Storn's list. **Guard: the hide rules
must not fire on collection-log or recommended items** (an `apply`/exclusion so a hidden family never
buries a clog slot).

## 7. Ordering (first-match-wins) & module order

Terminal `rule` is first-match-wins; `apply` is non-terminal (global modifiers). Order:

1. `settings` — non-terminal global gates/toggles (IRONMAN, world-spawn/ownership, value/despawn).
2. `custom` — user highlights win over everything downstream.
3. `hidden` — user hides win over default styling; excluded from clog/recommended.
4. `uniques` — clog beams; never hidden.
5. content (`bosses` … `clue_uniques`).
6. families (`seeds` … `essence`).
7. gear — metal (`bronze_gear` … `dragon_gear`), then `ranged_armour`, `magic_robes`, `jewellery`,
   `other_gear` (stat-tiered catch-all, last so themed gear wins).
8. utility (`currency`, `alchs`, `teleports`, `keys`).
9. `fallback`.

`meta{}` stays **last** (regex-scanned from anywhere; filter must START with a module — the
`settings` module carries the `IRONMAN` macro). `validate_loot_filter.py` grows to assert this
order and every module's presence.

## 8. Settings & frame

`settings` module: `#define IRONMAN accountType:1` (first, so the filter starts with a module) +
global toggles (Hide-below-value floor default 0, Show world spawns, Show unowned, Show despawn,
Show value). Area-gating IS available (§6a) and used per-boss; there is no on-task game-state
condition, so we don't fake one (§2) — the boss "area" toggle is the honest substitute.

## 9. What we add over Storn

- **KG-derived membership** — Storn hand-maintains his lists; ours come from `loot_families` (item→
  family) + `loot_importance` (item→base tier), regenerable and broader.
- **Iron High-Alch valuation** — `income/realize.py` value signal feeds the `alchs` module and the
  junk-hide seed.
- **Missing-clog purple beams** — the tailored build layers the owner's live TempleOSRS clog state
  (obtained dim, missing → purple beam) on top of the generic structure.
- **True drop-rarity tiers** — `drop_rates.json` (1/N) tiers boss/raid uniques (ULTRA/RARE/COMMON),
  not GE value.
- **Sprite-sampled jewellery colours** — rings/amulets/necklaces coloured from their own item art
  (§6c), not hand-typed like Storn's lists.

## 10. Emitter / generator architecture

`src/osrs_planner/lootfilter/`:

- `emit.py` — new helpers: `emit_enumlist_input(module, label, group, enum, macro, default)`;
  `emit_family_module(family, importance_rows)` (tier buckets + escalation); `emit_gear_module`;
  `emit_boss_module(boss, uniques, area_box)` (rarity tiers + arena `area:` box + themed colours);
  `emit_jewellery_module` (sprite colours); `emit_hidden_module`; keep `emit_style_input`,
  `emit_custom_highlights`, `emit_module`, `_yaml_scalar` (and extend quoting to `enum` option
  strings). Retire the flat `emit_quantities`/`emit_families`/`emit_categories` blob.
- `generate.py` — emit the modules in §7 order; new loaders for gear metals + non-metal gear
  (ranged/magic/other), per-boss content groups + arena boxes, HA-alch bands, jewellery sprite colours.
- `palette.py` — tier→style (reuse `quantity_display_grade`, `FAMILY_HUES`, `gear_score`); per-boss
  themed palettes (owner-collaborated, §6b).
- `data/` derivations — reuse `build_loot_families.py`, `build_loot_importance.py`; add
  `build_gear_metals.py` (metal→pieces), `build_content_groups.py` (per-boss uniques/commons/supplies
  from `bosses_pvm` + `drop_rates`), `build_boss_areas.py` (arena boxes, wiki-sourced + disclosed),
  `build_alch_bands.py`, `build_junk_hidelist.py`, `build_jewellery_colours.py` (sprite dominant-colour
  via the RuneLite icon cache + Pillow, the PR #12 technique), `build_keys.py` (name-derived + curated).
- Each new derivation gets a committed `verify_*.py` coverage report (report-not-fail), per repo
  discipline.

## 11. Validation & verification (gates)

- **Byte-stable** generic `outputs/gilded-tome-iron.rs2f` on re-run.
- **`validate_loot_filter.py`** extended: module presence + §7 order; every `enumlist` has a
  non-empty `enum`; every `…_NAMES` default ⊆ its `enum`; every enum/name-list entry resolves to a
  real item; colours 9-hex ARGB; every `area:[…]` box is 6 ints; IRONMAN-gating; macro-defined-
  before-use; the existing YAML-scalar quote guard.
- **FilterScape real-parser harness** (from the import-bug fix): run both filters through
  `Kaqemeex/loot-filters-ui`'s `parse()` locally and assert PARSE OK with the expected module/input
  counts. **Required pre-merge gate** — the only check that catches YAML/parse breakage. Script it
  under `scripts/` and document it (Node-side, not in the Python suite).
- **Coverage verifiers:** every `loot_families` item lands in exactly one default tier of its
  family module; every clog / boss-unique is reachable; report residuals (exit 0).
- Full Python suite green; the KG assemble/validate untouched and still byte-stable.

## 12. Build sequencing (subagent-driven, waves)

Large — comparable to itemization's 14 tasks. Waves, each independently importable + verified:

1. **Family framework + Seeds** (the owner's named case): the `emit_enumlist_input` /
   `emit_family_module` helpers, tier buckets, escalation, validator + parser-harness gates. Proves
   the pattern end-to-end on one module.
2. **Remaining resource families** (herbs, runes, ores, bars, logs, planks, gems, ammo, food/pots,
   prayer, essence, herblore secondaries — one module each).
3. **Gear** — metal modules (bronze→dragon), then non-metal (`ranged_armour`, `magic_robes`,
   `other_gear` stat-tiered catch-all), then `jewellery` (sprite-sampled colours, §6c).
4. **Content** — clues (reshape existing) → `uniques`/clog → **one module per boss + per raid**
   (rarity tiers + arena `area:` box + themed colours, §6a/§6b) → `slayer_monsters` bundle. Heaviest,
   owner-collaborated (boss colours + arena coords); sub-split by boss.
5. **Utility** (currency, alchs, teleports, keys).
6. **Frame** — settings globals + `hidden` + `custom` promotion + fallback; final ordering pass +
   whole-branch review + tailored Tiger0295 regen.

Each wave: per-task implementer + task review + a whole-branch review before merge (the recurring
lesson — cross-module first-match-wins ordering bugs are invisible in single-task diffs).

## 13. Open questions / editorial gates

- **Colours are owner-collaborated editorial** (§6b): tier→colour mapping, per-boss themed palettes,
  and jewellery sprite colours drawn from the wiki + content identity, corrected with the owner (the
  PR #12 potion-liquid process). Same review class as `loot_importance` base tiers (review pending,
  incl. the "Steel cannonball"→E nit). **Owner offered to help pick boss/raid colours.**
- **Boss/raid grouping = decided: one module per boss + per raid** (§6b), specific colours; generic
  slayer monsters bundle into `slayer_monsters`. Cardinality from `bosses_pvm` (~74 bosses → many
  modules; owner accepts the size).
- **Arena `area:` coordinates** are wiki-sourced per boss (owner can help); unresolved boxes are
  disclosed and that boss simply isn't area-gated, never faked.
- **Keys** data is thin — name-derived + curated, residual disclosed, nothing fabricated (§6e). **No
  per-charge jewellery** — jewellery is sprite-coloured instead (§6c).
- **Filter size** — expected to exceed Storn's ~889KB with long import times; owner accepted this
  explicitly.
```
