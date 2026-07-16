# Loot-Filter Itemization (v3) — deep ironman families + derived notability + manual override

**Status:** Design (brainstormed). Supersedes the itemization posture of
`docs/superpowers/specs/2026-06-20-loot-filter-design.md` §6/§9/§13 (which deferred
"granular per-content curation" and "rarity sub-ranking"). The two-axis visual language,
the `IRONMAN accountType:1` gate, the FilterScape-compat constraints, and the emitter
grammar are all inherited unchanged.

**Owner ask (verbatim intent):** "itemize every item we can to give unique colors and beams
to drops"; "important ironman resource drops and gear upgrades to matter"; "ironman specific
for now, not account specific"; "be able to search for an item in FilterScape and change the
color or loot beam myself manually"; "I don't want to manually add items that matter" —
derive them (from families, GE value, rarity, a structured iron list); "take inspiration from
Storn's Iron Filter."

---

## 1. Problem & goal

The committed filter gives **~23.5% of items** a bespoke treatment; **76.5% fall through to a
7-band value ramp**, and 67.9% of the item dictionary renders as undifferentiated gray text
(measured against `data/item_dictionary.json`). The itemization is stuck at 23.5% not by bug
but by construction: `categories.py` is 116 hand-enumerated `fnmatch` patterns over item
*names*, covering ~13% of items, with no taxonomy to generalize from.

**Goal:** a **shareable, ironman-oriented** filter (still `accountType:1`-gated, inert on mains)
that (a) colors far more items by a *correct family identity*, (b) makes genuine **gear upgrades**
and **important iron resources/uniques** stand out, and (c) lets the user **recolor/re-beam any
specific item by hand in the FilterScape UI** without editing filter text. NOT account-tailored
to live levels/bank — that is a separate, later concern.

**Non-goals (this slice):**
- Account-specific tailoring to tiger0295's live hiscores/bank (the `tailor.py` path stays but is
  out of scope here).
- "Can I wear this *now*" — blocked on wield-requirement data (no wiki Bucket source; deferred).
- "Is this better than what I'm wearing" — worn-gear data does not exist and has no source.
- Literal unique-color-per-item (rejected — destroys the hue-as-family language; see §3).
- Byproduct/currency modeling; custom `.wav` audio.

---

## 2. Two hard constraints that shape everything (both source-verified)

1. **FilterScape has NO native per-item override.** Three independent source inspections of
   `riktenx/loot-filters` (the plugin) + `Kaqemeex/loot-filters-ui` (filterscape.xyz) confirm:
   the input-type enum is a closed 6-type set (`boolean|number|stringlist|enumlist|style|text`);
   the UI search box only searches author-declared labels, never the bundled item DB. There is no
   "type an item name → get a color picker for it" path. The **only** no-text-editing way for a
   user to recolor a specific item is the reference-filter pattern: the filter ships generic
   **custom highlight groups** (paired `stringlist` + `type: style` inputs) the user fills in. This
   is §6.
2. **Rules scale with COLORS, not ITEMS.** A single `rule (id:[…N ids…])` colors N items in one
   rule (the trophy layer already ships 1,701 ids on one ~12 KB line). So deep itemization grows
   the file in *bytes* (~150–250 KB expected, vs 137 KB today), NOT in *rules*. The naive
   per-item-rule explosion (~15k rules / ~5.9 MB / a 15k-entry GUI) is explicitly avoided: we emit
   **per-family** style inputs, never per-item inputs.

---

## 3. Visual language (three axes)

Inherits the committed two-axis language and adds a third signal discovered during design.

- **HUE = identity ("what is it").** Every family gets one correct, learn-once color, each an
  editable `type: style` input. Herbs green, ores their own ladder (Coal dark, Gold gold), runes
  per-element (already done), etc. This is where the width comes from.
- **EMPHASIS = attention ("how much do I care").** Within a hue, brightness/panel/border escalate.
  Driven by `max(value_tier, notability_tier)` — a cheap-but-notable item is lifted by notability,
  a pricey item by value; the louder wins.
- **BEAM = scarcity ("stop what you're doing").** The loudest, rarest signal. **Beam color = the
  item's family hue**, so a beam carries two bits: *that* it beams ("stop") and *what color*
  ("…it's a herb / a unique"). Beam fires ONLY on the notable/value line in §5.

**Why not literal unique-color-per-item:** the file already has 129 colors, 99 used exactly once;
pushing to 15,496 forces sub-perceptible deltas at drop-glance speed — the color stops carrying
information the item *name* doesn't carry better, and the hue-as-family language (learn 8 metal
colors once, not 192 gear colors) is destroyed. The owner's own prior work (38 hand-tuned potion
families; ores refusing the gear palette) is *item-accurate families*, not item-unique. This design
scales that.

---

## 4. The derived taxonomy brick (`loot_families`)

Follows the house pattern: **derive what's structurally derivable, hand-author the residue through
an overrides file, gate everything with a source-grounding verifier** (same shape as
`facility_overrides.json` + `world_parenting.json`).

**Naming note (avoid a collision):** the repo ALREADY has `data/item_node_families.json` (+
`data/verify_item_families.py`) — that's the KG's item-*variant* grouping (6 records: "all Salve
amulet variants"), a `same_entity` facet, **unrelated** to this resource taxonomy and ingested via
`assemble.py`. So the new brick uses the `loot_` prefix and is **filter-side** (read directly by
`generate.py`, NOT through `assemble.py` — confirmed: the lootfilter package `json.load`s
`data/*.json` directly and never imports `kg_ingest`).

**New files:**
- `data/loot_families.json` — committed: `item_id → {family, source_signal, source_token, source_url}`.
  Every row carries *why* it got that family so the verifier can re-prove it. Envelope =
  `{"_provenance": {...}, "records": [...]}` (mirror `data/parse_drop_rates.py`'s `write_dataset`).
- `data/build_loot_families.py` — deterministic builder (lives in `data/`, filter-side — NOT
  `kg_ingest/builders/`).
- `data/loot_family_overrides.json` — owner escape hatch for signal misses/misclassifications.
- `data/verify_loot_families.py` — re-derives from source; **structural drift hard-fails (exit 1)**
  (clone `data/verify_item_families.py`'s `errors`-list shape), resolution/coverage residuals
  **reported (exit 0)** (clone `data/verify_recipe_coverage.py`) per the report-not-fail rule.

**Family set** (each family uses its *highest-precision* signal — noisy signals are rejected in
favor of name-suffix or routed through overrides; nothing gets a family it can't defend):

| Family | Signal | Coverage | Precision |
|---|---|---|---|
| `gear` (→ stat-tiered, §7) | `items_equipment.json` `slot`+`stats` | 4,298 / 12 slots | exact |
| `utility` (equippable, no combat score) | `items_equipment.json` combat_score ≤ 0 | 1,649 | exact split |
| `herb` | grimy→clean Herblore recipe (KG) | 46 | 100% |
| `potion` | Herblore-produced + dose filter | ~269 | high |
| `food` / `raw_fish` | Cooking-produced / `Raw ` prefix ∩ Cooking-consumed | 356 / 96 | high |
| `seed` `ore` `bar` `log` `rune` `ammo` `gem` `bones` | name-suffix (proven high-precision) | ~700 | high |
| `secondary` | Herblore-consumed non-herb | ~227 | noisy → overrides-assisted |
| hand-authored keeps | `charged_jewellery` `teleport` `essence` `planks` + 40 potion-liquid sub-hues | ~340 | editorial |

`~59%` of distinct item names become structurally classifiable (equipment ∪ recipe ∪ suffix),
versus 13% today. The KG is **not** touched — families feed the loot filter, not the ontology
(a family is a filter concern, not an ontology claim); keeps this additive and off the
entity-graph critical path.

**The `utility` split (the "Pharaoh's sceptre" fix):** 1,649 of 4,298 equippables have a combat
score ≤ 0. Stat-tiering (§7) would bury every one — games necklace, explorer's ring, teleport
jewellery, skilling tools. These route to `utility` (identity color, **no** stat rank) and are
never ranked against real armour. (Pharaoh's sceptre itself is already a clog slot, so it also
gets a notable lift via §5 signal 1.)

**Family precedence (resolves overlap):** families are assigned most-specific-first. The
hand-authored sub-families `charged_jewellery` (glory/games-necklace/etc.) and `teleport` (tabs/
scrolls) take precedence over the broad `utility` catch-all — an item matching a specific sub-family
keeps its established hue; `utility` only claims equippable, zero-combat items that no more specific
family matched. The builder records which rung assigned the family (like the world layer's
`parent_for` rungs), so precedence is auditable.

**Hues stay hand-authored** — no data source carries "herbs are green." The family→hue map lives
in `palette.py` (extended). This is the irreducible editorial core, behind the owner-review gate.

---

## 5. Derived notability (four grounded signals, zero hand-curation)

"Importance" is a third signal, not derivable from value or stats alone (a Pharaoh's sceptre is
cheap, statless, untradeable, yet matters). A `notable` item is **lifted in EMPHASIS above its
family's default** (a brighter panel + border) — this is NOT the same as a beam (see the beam
subset below). Sourced from a union of grounded signals — no hand-typed "items that matter" list:

| # | Signal | Source | Kind | Emphasis | Beam? |
|---|---|---|---|---|---|
| 1 | Collection-log slot | `data/collection_log.json` (1,701 ids) | committed id-list | lift | only if RARE/ULTRA tier |
| 2 | **Recommended-for-activity** | **new `recommended_equipment` brick (960 items)** | committed id-list | lift (border) | no (unless also 3/4) |
| 3 | Worth ≥ 500k | plugin-native `value:>=500000` | runtime rule | lift | **yes** |
| 4 | Rare drop | `data/drop_rates.json` (rarer than ~1/512) | committed id-list | lift | **yes** |

**Beam is the scarcity SUBSET, not all of notability** (the owner's beam line): a beam fires only for
**value ≥ 500k (signal 3) OR rare drop (signal 4) OR a clog RARE/ULTRA slot (signal 1's top tiers;
COMMON clog stays panel-only, per the existing `tailor.py:52-54` anti-spam rule)**. Recommended-only
items (signal 2) get the emphasis/border lift so they read as "a known target," but do **not** beam
unless they also clear 3 or 4 — otherwise 960 items would beam and the signal would drown. Beam color
= the item's family hue (§3).

**Two kinds of notable live in different places** (this is why it's cheap):
- **Runtime-derived (ship no data):** "worth ≥ 500k" is the plugin's native `value:>=500000`
  (`value` = `max(GE, high-alch)` × stack, computed live in-game — never a stale snapshot). This
  is the **value safety-net**: anything valuable beams even if we never classified it. Owner-set
  threshold = **500k**.
- **Build-time id-lists (ship grounded data):** the plugin can't know "in the clog?" / "recommended?"
  / "1/5000 drop?" — those aren't properties it has. Each is one committed, source-cited `id:[…]`
  list (cheap: N items, one rule).

**The `recommended_equipment` brick (new) — the derived iron-relevant list:**
- Source: `Module:Recommended equipment` writes a `recommended_equipment` **Bucket**, queryable via
  the same `action=bucket` API the repo already uses for `Bucket:recipe`. 454 rows / 146 pages →
  **960 distinct items**; each grounds cleanly (`page_name` = verbatim `source_token`, + `style` +
  `slot`, `source_url` = that page). CC BY-NC-SA, identical to existing bricks.
- **Complementarity (the payoff):** only 291 of the 960 are clog slots — **555 are NOT in the clog**,
  exactly the "common-but-important non-drop" gap the clog structurally can't hold (Barrows gloves,
  Fire cape, Infernal cape, Avernic defender, Void, Ava's, agility cape, glory, god blessings, the
  adamant/rune/dragon tool+armour ladders).
- **Parser gotcha (load-bearing):** the Bucket `json` stores *rendered HTML cells*, not clean names
  (multiple items per cell, `<br>`/`/` joins, `<small>` notes, `UNIQ--ref` placeholders). Clean
  names extract deterministically from `\[\[File:[^\]]*?\|link=([^\]|]+)\]\]` (the `link=` target =
  canonical item page) → 960 names. A few non-item tokens (generic `Arrows`, section-links) leak →
  skip against `item_dictionary.json` and disclose (report-not-fail). Note the **5-per-slot render
  cap** (a 6th+ option isn't stored — a disclosed completeness residual).
- **Files:** `data/fetch_recommended_equipment.py` (clone of `data/fetch_recipes.py`) +
  parser + `data/recommended_equipment.json` (+ `data/raw/` snapshot) + `data/verify_recommended_equipment.py`.
- **Third-party sources considered & rejected as a *source*:** the owner-suggested
  `exchange-insights.gg` bank-templates and any `osrsbestinslot.com`/Fandom lists are all-rights-reserved
  and/or unstructured; the wiki Bucket dominates on structured-ness × groundability × licensing.
  They may inform hand-authored *overrides* at most.

---

## 6. Manual override layer — custom highlight groups (§ the "recolor it myself" ask)

The only no-text-editing per-item recolor mechanism FilterScape supports (§2, constraint 1).

- Emit **N paired inputs** at the TOP of the filter (right under settings, so first-match-wins makes
  them win over everything): a `stringlist` ("Custom highlight 1") + a `type: style` picker for it.
- Empty by default. In the FilterScape UI: expand a group → type `Ranarr weed` into its chip box
  (free text) → set its `textColor`/`backgroundColor`/`borderColor` + `showLootbeam` +
  `lootbeamColor`. No filter-text editing; edits persist across re-imports (IndexedDB input-config
  overlay — verify it reapplies after a base re-pull).
- **Count = N distinct manual colors/beams.** Prior art: the riktenx reference filter ships 6;
  Storn's Iron Filter ships **3** true free-color groups (`Extra Food 1/2/3`) **plus 5**
  "inject a typed name into a preset tier's color" slots (`Custom Uniques SS/S/A/B/C`). **Chosen:
  6 free-color custom highlight groups** (each `stringlist` + full `style` incl. beam) as the
  primary "recolor any item yourself" mechanism, **plus** the Storn-style **5-slot tier-injection**
  (`Custom notable SS…C` — type a name, it drops into that emphasis tier's existing color) as a
  lower-effort convenience. All empty by default. Tunable.
- **User hide-bank (Storn-inspired, ~4 slots):** a small set of `stringlist`/toggle catch-alls at the
  top — Hide-listed-items, Hide-if-unnoted, Hide-if-quantity-under-N — the ironman "stop showing me
  this" escape hatch. Empty/off by default (respects the owner's "nothing hidden" `HIDE_FLOOR` stance).
- **Backup override paths (documented, not primary):** in-game click-to-highlight/hide (one click,
  one global color — filter-agnostic, plugin feature); `prefixRs2f` raw buffer (power-user, is text
  editing).

---

## 7. Gear tiering by slot (§ "gear upgrades to matter")

Fully grounded in `items_equipment.json` (4,298 items, 12 slots, exact stats) — arithmetic on
published bonuses, no fabrication. **Editorial** (a validator can't check "is this the right
weight") → owner-reviewed.

- **Score (per slot family):** armour slots = Σ(5 defence bonuses) + prayer + relevant offence;
  weapon/2h = `max(attack bonuses) + strength_bonus` (ranged/magic analogues). Score buckets into
  ~4 tiers per slot.
- **Slot-relative, not global:** a body's defsum is comparable only to other bodies (body ranges
  0→620; top = Justiciar/Crystal/Bandos, bottom = 0-stat cosmetics). Cross-slot comparison is
  meaningless, so never done.
- **Zero-combat-score items excluded** → `utility` family (§4), never stat-ranked.
- **Recommended/clog lift complements stat-score:** stat-score gives the quality ladder; the §5
  notable signals give "known target." So a statless-but-recommended Fire cape or games necklace
  still pops, instead of relying on stats alone.
- **Disclosed limitation:** without wield-requirement data, a maxed Torva and a rune platebody both
  read "high-tier body" — a *quality* signal, not *can-I-use-it-yet*. Fine for a shareable filter;
  the ceiling until wield-reqs are sourced.

### 7.1 Quantity-aware promotion (borrowed from Storn; derivable; phase-2-optional)

A pure, per-family rule (zero per-item authoring): a base tier plus stack thresholds
(`×10/×100/×1000`) so a growing on-ground stack escalates its emphasis — a stack of 1,000 nature
runes or 100 dragon bones reads louder than one. Emitted as extra `id/name … && quantity:>=N`
rules layered above the base-tier rule. Iron-appropriate (volume of a cheap essential matters).
Flagged **optional / phase-2** to keep the first implementation focused; the base itemization
(§4–§8) ships first.

---

## 8. Assembly & filter layout

**Module order, top→bottom (first-match-wins = the priority mechanism):**

| # | Layer | Emits | Beams? |
|---|---|---|---|
| 1 | Settings | `IRONMAN accountType:1` gate + global toggles | — |
| 2 | **Custom highlight groups** (§6) | N × (stringlist + style), empty | user's choice |
| 3 | **Notable** (§5) | trophies(clog) + recommended + rare `id:[…]`; `value:>=500000` | scarcity subset only (§5) |
| 4 | **Families** (§4, §7) | one editable `style` per family; gear stat-tiered by slot | only if also notable |
| 5 | Coins | existing gold-darkening ladder | — |
| 6 | **Value ramp** (safety-net) | the fallback ladder (shallower now) | ≥500k only |
| 7 | `meta{}` | at END (parser regex-scans it; content before first module discards the filter) | — |

**Prerequisite fix (folded in — the "dead palette table" bug):** `palette.py`'s `VALUE_GRADES`
carries `beam`/`sound`/`border`/`bg_alpha` fields that `style_for` **never reads** (it re-hardcodes
those as grade-membership literals at `palette.py:49-52`); `TROPHY_GRADES`' `beam`/`sound` are
likewise dead (`emit.py`). Two sources of truth agreeing by coincidence. Make the emitter actually
read the tables before stacking itemization on top, so styling stays single-source.

**Code touch-points** (with the exact reuse anchors from exploration):
- `palette.py` — add family hue maps (herb/seed/secondary/utility/etc.); make grade emphasis
  table-driven (kill the dead `beam`/`sound`/`border`/`bg_alpha` fields `style_for` never reads).
- `categories.py` — evolve from "name-pattern → family" to **consume `loot_families.json`** for
  membership (id-lists), keeping the hand-authored family→hue map + the potion/jewellery name-globs
  that must stay open. Its `category_rules()` is the seam `emit_categories()` already iterates.
- `emit.py` — add `emit_custom_highlights()` (layer 2), `emit_notable()`/`emit_recommended()`
  (layer 3), `emit_gear()` (layer 4, stat-tiered). **Model the id-list modules on `emit_trophies()`
  (`emit.py:91`)** — it already builds `_id_list(...)` + `IRONMAN &&` + per-grade `emit_style_input`
  pickers over a big id-list. Reuse `emit_style_input()` (`:31`), `emit_module()` (`:43`),
  `_id_list()` (`:83`), `_macro_name()` (`:117`) verbatim.
- `generate.py` — new module order (§8) in the `parts` list (`generate.py:65-70`); add `load_*`
  functions for `recommended_equipment.json` + `loot_families.json` mirroring `load_clog_ids()`
  (`:12`, plain `json.load(...)["records"]`). Generic path (`account_state=None`) stays the committed
  byte-stable artifact.
- `data/validate_loot_filter.py` — extend the hard-coded module-order assertion
  (currently `settings < trophies < categories < fallback`, `:36-38`) to the new order; id-resolution
  check (`:39-43`) already covers new `id:[…]` lists.

**Settings defaults (Storn-informed):** the whole design is **usefulness-first, value-as-fallback**
(Storn's thesis: *"tiers based on usefulness or rarity, rather than GE value"*). Layers 3–4 (notable,
families) dominate; the value ramp (layer 6) only catches what nothing else classified. A global
`SHOW_VALUE` toggle defaults **off** (calmer HUD; the value ramp still works, it's the *on-item value
text* that's hidden). `HIDE_FLOOR` stays default-off (the owner's "nothing hidden" preference).

**Iron gate & shareability:** unchanged. `generate_filter(account_state=None)` → committed
`outputs/gilded-tome-iron.rs2f` (byte-stable). The account-tailored `tailor.py` path is untouched
and out of scope.

---

## 9. Grounding, validation, testing (the discipline)

- **Never fabricate:** every `loot_families.json` and `recommended_equipment.json` row cites
  `source_url` + verbatim `source_token`. Hues + gear-score weights are editorial → owner-review gate.
- **Verifiers:** `verify_loot_families.py` + `verify_recommended_equipment.py` re-derive from the
  wiki snapshot; **structural violations hard-fail**, resolution/coverage residuals **report (exit 0)**.
  `validate_loot_filter.py` extended (color format, id resolution, new module order, no-orphan-before-module).
- **Byte-stable regen (not `assemble`):** the filter is filter-side, so "byte-stable" means
  `open("outputs/gilded-tome-iron.rs2f").read() == generate_filter()` — the existing gate
  `tests/lootfilter/test_byte_stable.py`. Regenerate the committed artifact with `write_filter(path,
  account_state=None)` (`generate.py:73`; there is no `--update-golden` CLI). `data/raw/` snapshots
  make both new bricks reproducible (the foundation-audit pattern).
- **Tests:** unit per module + verifier; golden byte-stable filter regen; FilterScape-parse
  compatibility (module-first, meta-last, no forbidden `IRON` macro). Competency questions: "Fire cape
  reads notable?", "bronze platebody reads low-tier body?", "ranarr beams only above its notability
  line?", "a games necklace is `utility`, not buried gear?".
- **Test-collection gotcha:** load `data/*.py` via `importlib.util.spec_from_file_location`, not
  `from data.X import …` (the `tests/data/__init__.py` package-shadow bug); run the FULL suite before
  claiming green.

---

## 10. Build sequence (for the plan)

1. Fix the dead-palette-table bug (prerequisite; keeps styling single-source).
2. `recommended_equipment` brick: fetch → parse (the `link=` regex) → commit raw + json → verify.
3. `item_families` brick: builder (equipment slot + recipe grammar + name-suffix + overrides) →
   commit → verify. Owner review of the family→hue map + gear-score weights.
4. Emitter/generator: family id-lists, gear stat-tiers, notable layer (recommended + rare + value
   net), custom highlight groups (count from §6), new module order.
5. Regenerate committed `outputs/gilded-tome-iron.rs2f`; validators + golden + full suite green;
   FilterScape import smoke-test.
6. Live in-game iteration with the owner (the PR #12 pattern — screenshot-by-screenshot hue
   correction; sprite-sampling is a first pass, the human-in-the-loop wiki check gets colors right).

---

## Appendix — prior art (Storn's Iron Filter)

Design *inspiration only* — `github.com/Storn42/Iron-Filter` is all-rights-reserved; we borrow
STRUCTURE, never its code/colors/item-lists (structural metadata only was inspected).

**What it is:** *"A True Ironman Filter for FilterScape."* 26,342 lines / ~890 KB / **2,364 terminal
`rule`s, 61 `apply`s, 2,361 `#define`s, 2,330 UI inputs across 43 modules** — and a **60-second+
import time**. That size is the whole point of *our* contrast: Storn spells out every family × 7
tiers × {names, style, quantity thresholds, unnoted flags} **by hand**; we **derive** the families
from the KG and generate the same shape at a fraction of the size and zero hand-enumeration.

**Its thesis (why it validates this design):** *"All tiers are based on an item's usefulness or
rarity, rather than GE value… turn off item value and enjoy."* Exactly the owner's ask.

**Module layering (a priority cascade, terminal `rule` = first-match-wins):**
`settings → user-hide → survival supplies (food/pots) → uniques (collection-log) → PvM/raid/clue/
minigame → the ironman economy (currency, alchs, keys, teleports, seeds, herbs, secondaries, cooking,
runes, ores/bars, logs, planks, crafting, prayer, fletching) → gear by metal tier (dragon→…→bronze)
→ misc → value FALLBACK (the ONLY GE-value tiering, last)`. Our §8 layout mirrors this shape.

**User-override patterns:** 3 free-color groups (`Extra Food 1/2/3`: `stringlist` + own `style`) +
5 tier-injection slots (`Custom Uniques SS…C`) + 6 hide catch-alls (`Hide if quant <N`). Basis for §6.

**Beam/sound budget:** beam only at value S/SS + all 5 unique tiers (`showLootbeam=true` 89×, never
`false`); sound at value A+ (uniques get their own 5 sounds). Confirms §3/§5's scarcity line.

**Colors:** ~206 distinct ARGB — a two-axis **family × tier** system (~40 hand `_STYLE` blocks),
close in spirit to our HUE(identity) × EMPHASIS(value) but hand-authored, not derived.

**Ideas borrowed into this design:** (1) value-as-fallback / usefulness-first (§8 settings);
(2) per-family emphasis ladder, not one global value scale (§3–§4); (3) quantity-aware promotion
(§7.1); (4) principled beam/sound budget (§3); (5) empty-by-default user override groups (§6).
**Not borrowed (out of scope / over-scope here):** the "Blank companion filter", per-boss custom
lists, UIM death-pile mode, account-tailored supply seeding (belongs to the deferred `tailor.py`
path).
