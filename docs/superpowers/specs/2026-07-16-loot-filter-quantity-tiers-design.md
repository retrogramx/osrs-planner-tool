# Loot-Filter Quantity Tiers — hand-ranked ironman base importance + ×10 stack escalation

**Status:** design approved (owner), ready for plan.
**Branch:** `feat/loot-filter-quantity-tiers` (off `main`, which carries the merged itemization emitter, PR #28).
**Supersedes:** §7.1 of `2026-07-16-loot-filter-itemization-design.md` (which proposed a *per-family, zero-authoring* base tier). We deliberately choose **per-item hand-ranked** base tiers instead — see §2.

---

## 1. Problem & goal

The itemization filter (PR #28) colors a resource *pile* with a **flat** hue and no size signal: a
drop of 5,000 coal looks identical to 1 coal. The value fallback escalates by *total GE value*, which
leaves the cheap-but-bulky iron staples an ironman actually stockpiles — pure essence, coal, feathers,
nature runes, bones — dim even in huge piles.

Storn's Iron Filter solves this with **quantity tiering**: each resource has a hand-assigned *base
tier* (its intrinsic importance to an iron), and pile **count** bumps the displayed tier up (`×10`
steps). So 40 ranarrs read as a big deal (40 prayer/super-restore doses) while 40 guams do not — even
though both are "40 herbs" and neither is worth much by GE.

**Goal:** reproduce that engine as a *generated* module. Every resource item gets a hand-ranked base
tier (mine to author, owner to review); pile count escalates the display tier; the item keeps its
identity hue. Fold it into the generic filter and the tailored Tiger0295 build.

## 2. The core decision: per-item hand-ranked base tiers (not per-family, not value-derived)

The itemization spec's §7.1 proposed a per-family base tier (one number per family, zero per-item
authoring). **We reject that** because it throws away exactly the ironman nuance that motivates the
feature: within `herb`, ranarr ≫ guam; within `rune`, nature/law/blood ≫ air/mind; within `ore`,
runite ≫ copper. A per-family tier cannot express that.

We also reject **value-derived** base tiers: within a family, unit value is a decent proxy
(ranarr 5,214 gp > guam 210 gp), but it fails hard for the zero-value staples that matter most to an
iron (pure essence 2 gp, coal 151 gp, feather/nature-rune/bones 0 gp). Those are precisely the items
the feature exists to surface.

**Decision (owner-approved): I hand-rank the base tier of every resource-family item.** This is
*editorial filter-side data*, the same class as the family hues and potion-liquid colors already in
the filter — a curated judgment, not a wiki fact, so it needs no `source_token`, but it **does** get
the owner-review gate (`feedback_verbatim_editorial_verification`). Every ranking carries a one-line
rationale so the owner reviews *reasoning*, not opinion-as-magic-number.

## 3. The model

**display tier = base tier promoted one grade per ×10 in pile count, capped at SS.**

Grade order (highest→lowest), reusing the existing `palette.VALUE_GRADES` emphasis ladder:

```
SS  S  A  B  C  D  E          # index 0..6; lower index = louder
```

For a pile of `count` items with base grade at index `bi`:

```
display_index = max(0, bi - floor(log10(count)))          # count >= 1
```

Worked (the ranarr/guam case the design turns on):

```
Grimy ranarr   base A (idx 2)  →  1: A   ·  10: S   ·  100: SS
Grimy guam     base E (idx 6)  →  1: E   ·  10: D   ·  100: C  ·  1k: B  ·  10k: A  ·  100k: S
Pure essence   base B (idx 3)  →  1: B   ·  10: A   ·  100: S  ·  1k: SS
Coal           base B (idx 3)  →  1: B   ·  10: A   ·  100: S  ·  1k: SS
```

A **single** ranarr already reads important (base A solid panel); 40 jump to S. No per-item threshold
tables — the per-item nuance lives entirely in the authored base tier, and escalation is one uniform
`×10` rule. Emphasis (font weight / border / beam / sound) escalates through the existing
`palette.style_for` grade ladder; the **hue stays the item's identity color** (coal dark, nature
green, ranarr herb-green). Base tiers D/E render as `style_for`'s plain faded text (no panel), so a
single trivial item stays quiet and only a real pile lights up.

This matches Storn's `×10` schedule exactly; the only difference is that our base tiers live in one
reviewable file instead of scattered across ~40 hand-typed modules.

## 4. Data — `data/loot_importance.json`

One committed, human-readable file. **Every** item in the ranked resource families gets an explicit
base tier (owner chose "rank everything, no value fallback" — nothing is silently value-derived).

```json
{
  "_provenance": {
    "domain": "loot_importance",
    "kind": "editorial",
    "note": "Hand-ranked ironman base importance per resource item. Judgment, not a wiki fact; owner-reviewed. base_tier in {SS,S,A,B,C,D,E}. Quantity escalation (×10/grade) is applied at emit time, NOT stored here."
  },
  "records": [
    { "item_id": 207, "name": "Grimy ranarr weed", "family": "herb", "base_tier": "A", "rationale": "prayer/super-restore backbone" },
    { "item_id": 199, "name": "Grimy guam leaf",   "family": "herb", "base_tier": "E", "rationale": "low-level, trivial to an established iron" }
  ]
}
```

**Families ranked.** From `loot_families.json` (the authority on membership, id-lists ready):
`herb`, `rune`, `ore`, `bar`, `log`, `seed`, `bones`, `ammo`, `food`. Plus three families whose
membership lives in `categories.py`, not `loot_families.json` — **essence** (`ESSENCE_NAMES`), **gem**
(`CUT_GEMS` + their uncut forms), **planks** (`PLANK_NAMES`) — listed in the importance file by
`item_id` (names resolved via `item_dictionary.json`) with `family` set to `"essence"` / `"gem"` /
`"plank"`. **Herblore secondaries are deferred** (§10): we have no membership set for them, so ranking
them would mean authoring a new item list — out of v1 scope.

**Authoring guidance (mine to apply, owner to review):**
- **herb** — ranarr/snapdragon/torstol/toadflax A–B (potion backbones); avantoe/kwuarm/cadantine/
  lantadyme/dwarf weed C; irit/harralander D; guam/marrentill/tarromin E.
- **rune** — nature/law/death/blood/soul/wrath A (alching, high spells, RC targets); chaos/cosmic/
  astral B; body/mind/combos C–D; air/water/earth/fire E (elemental, cheap in bulk but staples → C
  floor, owner's call).
- **ore/bar** — runite A, adamantite B, mithril/coal/gold C, iron/silver D, copper/tin E; bars one
  tier below their ore (already smelted, less of a grind gate).
- **log** — magic/redwood A, yew B, maple/mahogany/teak C, willow D, oak/logs E.
- **seed** — ranarr/snapdragon/torstol/tree/fruit-tree/special (celastrus, redwood, spirit, crystal
  excluded — those are `utility`, not a bulk resource) A–B; herb seeds C; allotment/hops E.
- **bones** — superior dragon/dagannoth/ourg A, dragon/wyvern/lava B, big bones C, bones D; ashes
  (infernal/malicious A–B, others C–D); ensouled heads by the standard demand tier.
- **ammo** — dragon A, rune/amethyst B, adamant C, mithril D, iron/bronze E; tips one tier below
  finished ammo; cannonballs B (iron staple).
- **essence** — pure/daeyalt A (RC fuel, hoarded by the thousand), guardian B, rune essence C.
- **gem** — dragonstone/onyx/zenyte A, diamond B, ruby C, emerald/sapphire D, semi-precious
  (opal/jade/red topaz) E; uncut one tier above cut (the grind gate is cutting).
- **planks** — mahogany A, teak B, oak C, plain plank E.
- **food/supplies** — shark/karambwan/anglerfish/manta/dark crab and brews/super-restores/prayer pots
  ranked as **supplies** (high base B–A: "don't lose these"), everything else E. Food rarely drops in
  bulk stacks, so it barely escalates — that is fine; the base tier alone gives it presence.

The exact per-item tiers are the deliverable of the authoring task and land in the file; the owner
reviews the rationales before merge.

## 5. Emitter — `emit_quantities()`

New function in `src/osrs_planner/lootfilter/emit.py`.

**Inputs:** the importance records (`{item_id, name, family, base_tier}`) and a `hue_for(name,
family)` callable.

**Hue:** `hue_for` returns the **per-name** category hue when `categorize(name)` yields one (coal
dark, per-element rune, per-tree log, ore/bar per-name, gem), else `FAMILY_HUES[family]`. This
preserves the identity palette the current filter already shows; without it, quantity tiering would
flatten every rune to one indigo and every ore to one earth, a visible regression.

**Grouping:** group ranked items by `(hue, base_tier)`. Each group shares one id-list and one
escalation schedule, so id-lists stay short (often 1 item, since per-name hues are distinct) while the
rule count stays bounded.

**Rule emission per group** (terminal `rule`, highest count threshold FIRST so first-match-wins picks
the loudest reachable tier):

```
for display_index in 0 .. base_index:                 # SS .. base
    threshold = 10 ** (base_index - display_index)    # SS first (largest threshold)
    grade     = GRADE_ORDER[display_index]
    cond      = IRONMAN && id:[group ids] && quantity:>=threshold   # drop the quantity clause when threshold == 1
    emit editable style-input(cond, style_for(hue, grade))
```

The `threshold == 1` rule is the base floor (always matches a dropped item, count ≥ 1). Each tier is an
editable FilterScape `type: style` input (colour picker), grouped under a per-family label
(`Quantities — Herbs`, etc.), consistent with every other module.

**`GRADE_ORDER`** = `["SS","S","A","B","C","D","E"]`, added to `palette.py` (single source; `emit`
imports it). `style_for` already accepts a grade string and renders the emphasis — no new styling
code.

**Hide-below-count floor:** one global `#define QUANTITY_FLOOR 0` number input; a single leading
`apply (IRONMAN && id:[all ranked ids] && quantity:<QUANTITY_FLOOR) { hidden = true; }`. Default 0
hides nothing (mirrors `HIDE_FLOOR`). Non-terminal `apply` so it only sets `hidden`, letting a raised
floor hide trivial piles without swallowing the styling rules below.

## 6. Placement & the `categories` trim

**Module order (generate.py `parts`):**

```
settings → custom → [tailoring if account_state] → notable → trophies → gear
        → quantities → categories → families → untradeables → coins → fallback → meta
```

`quantities` sits directly **above** `categories`. Because rules are terminal/first-match-wins and
`quantities` now owns every ranked resource item (base rule matches at count ≥ 1), the corresponding
per-name rules in `categories` become **unreachable dead rules**. To keep the filter clean:

- **Trim `categories.py`** to only the non-quantity remainder: **gear-metal cosmetics, teleports,
  charged jewellery, potions.** Remove the resource rows now owned by `quantities`: ores, bars, runes,
  gems, essence, planks, ammo, logs, herbs, seeds, bones/prayer-supplies, food.
  - `categorize()` (used by `hue_for` and by tests) **keeps** its full resource logic — `quantities`
    depends on it for per-name hues. Only `category_rules()` (the emit list) is trimmed. Split the two
    responsibilities cleanly if they are currently entangled.
- **`emit_families`:** skip the quantity-tiered families (they are fully handled by `quantities`), so
  no dead flat family panels are emitted either. It keeps emitting only `utility` and any family not
  in the importance file.

Net: every resource item is styled exactly once, by `quantities` (identity hue + base tier +
escalation). Non-resource items are unaffected.

## 7. UI configurability

- Every quantity tier is an editable `type: style` picker (via the existing `emit_style_input`),
  grouped per family. Users retune colours/beams live in FilterScape, same as all other modules.
- One `QUANTITY_FLOOR` number input (default 0) to hide sub-N piles.
- **Base tiers are not UI-editable** (they are a bucketing, not a style); they retune by editing
  `data/loot_importance.json` and regenerating. This matches how family membership and category
  patterns already work.

## 8. Grounding, validation, testing

**Never-fabricate boundary:** base tiers are declared editorial (`kind: editorial`), so the
"grounding" obligation is the **owner-review gate**, not a `source_token`. The *membership* is
grounded — every ranked id must be a real item in the family it claims.

- **`data/validate_loot_importance.py`** (structural, hard-fail): every `item_id` exists in
  `item_dictionary.json`; every `base_tier` ∈ `{SS,S,A,B,C,D,E}`; every `family` is one of the ranked
  families; no duplicate `item_id`; each record's `family` agrees with `loot_families.json` where that
  item is present (essence/gem/plank excepted — their membership is `categories`-sourced, not in
  `loot_families.json`). Wire into
  `data/validate_loot_filter.py`'s module-order subsequence check (add `quantities` between `gear`
  and `categories`).
- **`data/verify_loot_importance.py`** (coverage, report-not-fail, exit 0): per family, `have N /
  family-total M`; lists any family member absent from the importance file (the "still to rank"
  residual) and any `categorize()` resource name with no importance record. Follows the
  `verify_*_coverage` pattern.
- **Unit tests** (`tests/lootfilter/`): the model (`display_index` math — base A count 40 → S; base E
  count 40 → D; count 1 → base; count 10^k caps at SS); `hue_for` per-name vs family fallback;
  grouping; rule emission order (SS threshold first); the `categories` trim (a trimmed resource name
  still `categorize()`s but is absent from `category_rules()`); `emit_families` skips ranked families.
- **Byte-stable assemble/regen:** `generate_filter()` (generic, `account_state=None`) stays
  byte-identical on re-run; a golden test asserts `open(outputs/gilded-tome-iron.rs2f).read() ==
  generate_filter()`. The KG is untouched (`kg/*.json` unchanged; this is filter-side only).
- **Full suite green** (`pytest -q --continue-on-collection-errors`; the 4 pre-existing
  `tests/drop_rates/` collection errors are unrelated). Load `data/*.py` via
  `importlib.util.spec_from_file_location`, never `from data.X import` (the `tests/data/__init__.py`
  package-shadow trap — `reference_tests_data_package_shadow`).

## 9. Deliverables

1. `data/loot_importance.json` — hand-ranked base tiers + rationales, every ranked resource item.
2. `palette.GRADE_ORDER`; `emit.emit_quantities()`; `hue_for` helper; `categorize`/`category_rules`
   split + resource trim; `emit_families` family-skip; `generate.py` wiring (load importance, place
   `quantities`).
3. `data/validate_loot_importance.py` + `validate_loot_filter.py` order update;
   `data/verify_loot_importance.py`.
4. Regenerated **`outputs/gilded-tome-iron.rs2f`** (generic, byte-stable) and
   **`outputs/gilded-tome-tiger0295.rs2f`** (tailored — the quantities module is account-independent,
   so it slots into `generate_filter`'s `parts` for both builds; the tailored build just adds the
   existing clog-tailoring module on top). Then a commit-SHA raw URL for the owner to re-import into
   filterscape.xyz.
5. Memory + `CLAUDE.md` note; PR.

## 10. Non-goals / deferred

- **Bank-aware tiering.** FilterScape `quantity:` is the dropped ground-pile size, not your bank
  total. Escalating by what you already hold would need the account overlay and is out of scope.
- **Per-name hue at the quantity layer beyond `categorize()`'s current coverage.** We reuse the
  existing per-name palette; no new hue authoring.
- **Area/boss-gated rules** (Storn's crown jewel). They need chunk geometry — the deferred KG layer —
  and become derivable then (boss → area → drop table). Explicitly out of scope here.
- **Per-family or per-tier hide floors** (Storn has per-tier `MIN_QUANT`). One global `QUANTITY_FLOOR`
  is enough for v1; per-family floors can follow if wanted.
- **Herblore secondaries.** No membership set exists in our data (unlike essence/gem/plank, which have
  `categories.py` sets). Ranking them means authoring a new item list; deferred to a follow-up.
