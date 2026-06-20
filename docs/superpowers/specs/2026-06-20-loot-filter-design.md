# Loot-Filter Generator — Design (v1)

**Status:** design approved 2026-06-20; spec under review → implementation plan next.
**Brick:** `feat/loot-filter`. An OUTPUT product: generates a RuneLite "Loot Filters" (`riktenx/loot-filters`) filter from our committed data. Builds on the merged collection-log + drop-rate data (the drop-rates brick, PR #9); reuses item identity from `data/item_dictionary.json`.
**Companions:** the loot-filter research (findings recorded in the project memory `project_runelite_loot_filters.md`), the plugin's `filter-lang.md`, the filterscape modular system (Kaqemeex `loot-filters-ui`). Reference filters (all-rights-reserved — design reference ONLY, never copied): Storn's Iron Filter, Joe's Filter.

---

## 1. Purpose & scope

Auto-generate a **genuinely impressive, account-type-aware ironman loot filter** for the RuneLite Loot Filters plugin — turning our data into a shareable, visual artifact. The plugin renders dropped loot with colours, borders, **loot beams**, sounds, and value tiers; our generator emits a `.rs2f` filter that styles every drop with a coherent **two-axis visual language** (hue = *what it is*, emphasis = *how much you care*), the way a top hand-made iron filter looks — but generated.

**v1 delivers:** a single generated `.rs2f` file — a **generic ironman filter** (`accountType:1`-gated), self-contained and loadable/configurable in the plugin (and in filterscape). It is the same for any iron, so it's **publishable/shareable** (the "show-off" artifact).

**v1 is built tailoring-ready:** a wired-but-unused **account-state seam** (skills/bank/collection-log completion) so the v2 "tailor to YOUR account" layer (beam the log gaps you still need, hide what you've banked) is additive — no redesign.

**v1 does NOT:** tailor to a specific account (the seam is unused); do the granular per-content supply curation a hand filter tunes (per-boss hide-lists — out of scope, the user adds those or v2); rarity-sub-rank trophies; produce a main-account variant (the format supports it via `accountType`; v1 is iron-first). See §13.

**Honest framing (do not oversell):** the plugin computes item `value`/`havalue`/`gevalue` **natively**, so value-tiering is not our edge. Our edge is two things the plugin cannot know — (1) **collection-log membership** (the trophy layer; no existing filter uses it) and (2) a curated, **item-accurate visual language** (material/type colours + name-pattern categories) generated instead of hand-authored across ~22k lines.

---

## 2. Load-bearing decisions (settled in brainstorm)

1. **Generic iron filter for v1** (shareable), **+ a wired-unused account-state seam** for v2 tailoring.
2. **Two orthogonal visual axes:** **hue = identity** (material/type colour, or trophy gold/bronze) · **emphasis = value** (faded → coloured → border → beam → +sound). Modelled on Storn's actual palette/escalation.
3. **General tiering uses `value` (max of GE & HA), GE-inclusive** — a high-GE item is a good drop even for an iron (Storn's own fallback grades by `value:`). `havalue` is reserved for alch-specific calls.
4. **Collection-log = the trophy layer** (gold/bronze "unique" look + beam + sound, never hidden), the differentiator. Graded by value in v1; rarity sub-rank deferred.
5. **Resources get item-accurate colour, not "trophy"** — coloured by their real in-game material/type (mithril gear = blue, fire rune = red…), value driving emphasis within. Resource categories are **shown by default** (iron-usefulness ≠ value) with a per-category min-value toggle.
6. **Categories derived by NAME PATTERN** (OSRS names are systematic) — not from structured data (we have none) and not the granular per-content curation.
7. **Modular filterscape rs2f format** so it loads + is configurable in the plugin like any other filter. We author **our own** modules/names/colours (the format is the plugin's and free to emit; reference filters are all-rights-reserved).

---

## 3. Architecture & boundary

A new overlay `src/osrs_planner/lootfilter/` that **assembles a `.rs2f` filter** from committed config + data, then writes it. It is the most *independent* brick:

- **Reads:** `data/collection_log.json` (the trophy id-set), `data/item_dictionary.json` (name→id resolution + item enumeration), committed config (the value tiers, the category name-patterns, the material/type colour map, the settings), and OPTIONALLY `data/drop_rates.json` (rarity — deferred sub-rank). It does **NOT** depend on the engine/cost/income overlays (value is native to the plugin), and the **KG stays untouched**.
- **Emits:** a static-mostly modular rs2f. The DATA-DRIVEN part is small — the collection-log `id:[…]` list (the trophy layer). Categories + material colours + value tiers are emitted as **name-pattern / `value:` rules** the plugin matches at runtime (no per-item enumeration needed). The committed config IS the bulk of the craft (the curated colour language).

**Files (one responsibility each):**
- `src/osrs_planner/lootfilter/palette.py` — the material/type → colour map + the value-grade styles (the visual language). Pure data.
- `src/osrs_planner/lootfilter/categories.py` — name-pattern → category rules (gear-by-metal, runes, herbs…). Pure data + the matcher helper.
- `src/osrs_planner/lootfilter/emit.py` — the rs2f emitter (modules, `#define`s, `rule`/`apply`, `meta`). Takes config + clog ids (+ seam) → rs2f text.
- `src/osrs_planner/lootfilter/generate.py` — orchestrator: load clog/dictionary → emit → write the `.rs2f`. `generate_filter(account_state=None)` — `account_state` is the wired-unused seam.
- `data/validate_loot_filter.py` — committed structural validator (iron-gate tradition).
- `outputs/gilded-tome-iron.rs2f` — the committed generated artifact (byte-stable, like `drop_rates.json`).

---

## 4. The rs2f target format (filterscape modular)

A custom text DSL (verified from the plugin's `filter-lang.md` + real filters). Key surface we use:
- **Structure:** `meta { name = "…"; description = "…"; }` + `/*@ define:module:<id> … */` blocks (grouping) + `/*@ define:input:<module> … */` blocks (plugin UI toggles) + C-style `#define` macros.
- **Rules:** `rule (<conds>) { <style> }` (TERMINAL — first match wins) and `apply (<conds>) { <style> }` (NON-TERMINAL — styles then continues). Evaluated top-down per ground item.
- **Match levers:** `value` (max GE/HA), `gevalue`, `havalue`, `id:[…]`, `name:["…", "* wild *"]`, `quantity`, `stackable`/`tradeable`/`noted`, `ownership:<n>`, `area:…`, and `accountType:<n>` (reads the in-game ironman varbit).
- **Style levers:** `textColor`/`backgroundColor`/`borderColor`/`menuTextColor` (8-hex ARGB `#aarrggbb`), `showLootbeam` + `lootbeamColor`, `sound`, `icon`, `notify`, `fontType` (1–3), `textAccent`, `highlightTile`/tile stroke/fill, `menuSort`, `hidden`/`hideOverlay`, `showDespawn`. Value matching is **stack-total** (value × quantity).

---

## 5. Module structure (emit order = evaluation order)

```
meta { name = "Gilded Tome — Iron"; description = "…generated…"; }

module: settings        # global toggles + the account-state SEAM (§10)
module: trophies        # collection-log items -> gold/bronze + beam + sound, never hidden (§8)
module: categories      # name-pattern groups, item-hue coloured, value-graded within (§9)
module: fallback        # the SS->E value ladder for everything else (§7)
```

`trophies` sits **above** `categories`/`fallback` so a collection-log drop always wins its trophy style (and its `apply`-based never-hide guard runs first). `categories` sit above `fallback` so a recognised resource gets its hue before falling to the generic value ladder. (Mirrors how the reference filters order specific → general.)

---

## 6. The two-axis visual language

Every styled drop encodes two independent signals (this is what makes it read at a glance):
- **HUE = what it is.** Material/type colour for resources/gear (mithril = blue, fire rune = red, oak = tan…); **gold/bronze** for a collection-log trophy; the value-ladder's red/pink/yellow for an uncategorised high-value drop.
- **EMPHASIS = how much you care,** driven by the **value grade** (§7): `faded → coloured text → +border → +loot beam → +sound`, *rendered in the item's own hue*. So a valuable mithril item = bright blue + **blue beam** + sound; a cheap one = dim blue.

---

## 7. Value model & grade ladder

The plugin evaluates `value` at runtime; we emit the thresholds + styles. Grades (Storn's breakpoints):

| Grade | `value` ≥ | base emphasis (in the item's hue) |
|---|---|---|
| **SS** | 10,000,000 | bright + border + **beam** + **sound** + `fontType=3` |
| **S** | 1,000,000 | bright + border + **beam** + **sound** + `fontType=3` |
| **A** | 100,000 | coloured bg + **sound** + `fontType=2` |
| **B** | 10,000 | coloured bg + `textAccent` |
| **C** | 1,000 | tinted bg |
| **D** | 100 | plain coloured text |
| **E** | < 100 | **faded** + sorted last |

Escalation: **beam only at S+, sound only at A+** (no beam/sound spam). The `fallback` module applies this ladder by raw `value`; the `categories`/`trophies` modules apply the *same ladder* but tinted by the item's hue (the per-grade style is the category hue at the grade's emphasis). Thresholds + the per-grade emphasis live in `palette.py` so they're tunable in one place.

---

## 8. Collection-log trophy layer (the differentiator)

For each item id in `collection_log.json` (1,907), emit trophy rules:
- **Style:** the **gold/bronze "unique" palette** (modelled on Storn's `UNIQUE_*`) — distinct from the value ladder's red/pink — **always `showLootbeam` + a `sound`**, graded SS–C by `value`. So a trophy reads as "collection-relevant," not merely "valuable."
- **Safety-net:** a non-terminal `apply` ensures a collection-log item is **never hidden** by a later value rule (a cheap-but-collection-relevant drop — a 200gp slayer unique, an untradeable log item — still pops). Emitted as `id:[…]` lists (the one genuinely data-driven part; ids resolved via `item_dictionary.json`).
- **v1 grades trophies by value; rarity (`drop_rates.json` 1/N) sub-rank is deferred** (the per-item rarity collapse is fuzzy — see the drop-rates brick).

---

## 9. Category derivation + material/type colour map

**Categories (`categories.py`):** a committed table of **name-pattern → category** rules, reliable because OSRS names are systematic. Each category is **shown by default** (iron-usefulness) with a per-category min-value toggle (§10). Covered v1 groups: gear (by metal), runes, herbs, seeds, bones, ashes, logs, planks, ores, bars, gems, ammo, potions, food, teleports/runes-of-passage. NOT the granular per-boss supply lists (deferred).

**Material/type colour map (`palette.py`):** a committed `material/type → #aarrggbb` table, applied by name pattern so each item is its real in-game hue:
- **Metals** (the leverage — one colour covers a whole gear family): `Bronze #cd7f32 · Iron grey · Steel light-grey · Black · Mithril blue · Adamant green · Rune turquoise · Dragon red`. `"Mithril *"` → ~15+ gear pieces in mithril-blue.
- **Per-type tables** (≈ one colour per item, but compact + systematic): runes by element (fire red, water blue, nature green, blood crimson…), gems by stone (sapphire blue, emerald green, ruby red, diamond white, dragonstone magenta, onyx black, zenyte orange-red), logs by tree (oak tan, willow olive, maple amber, yew dark, magic cyan, redwood red).
- **Family-base** for varied groups (herbs/seeds green; food/potions a base hue, with per-item where systematic — salmon pink, lobster red, shark steel).

A category rule is then: `rule (name:[<patterns>] && value:>=<grade>) { <hue> at <grade emphasis> }`, one per grade (the §7 ladder tinted by the §9 hue).

---

## 10. Settings module + the tailoring seam

**Settings** (`/*@ define:input */` toggles, mirroring the reference filters): show world-spawns (`ownership:0`), show unowned (`ownership:2`), despawn timer, item-value display on/off, and per-category minimum-value knobs. These compile to `apply (!TOGGLE && cond) { hidden = true; }` guards.

**The account-state seam:** `generate_filter(account_state=None)` accepts an optional account state (skills / banked items / collection-log completion). **v1 ignores it** (assigned to `_`, noted in the filter's description). When wired (v2), it enables: beam the collection-log slots you still NEED (vs all clog items), hide items you've banked, and skill-aware value for the few processing-dependent items. The seam means that's additive — no signature or structure change.

---

## 11. Output, determinism & licensing

- **Output:** `outputs/gilded-tome-iron.rs2f` — a single self-contained filter, committed (byte-stable, regenerable like `drop_rates.json`); `scripts/lootfilter_demo.py` prints/writes it. Loadable in the plugin (paste/import) and editable in filterscape.
- **Determinism:** the generator sorts all id-lists + emits in a fixed module order, so re-running produces an identical file (a validator/CI gate, like the KG assemble).
- **Sounds:** v1 references the plugin's **built-in cache sound ids** (no bundled audio) where available; a custom-`.wav` pack is a v2 polish. (Disclosed.)
- **Licensing:** the rs2f **format/grammar is the plugin's** — emitting it is free. Storn's/Joe's/Jarnhopur's filters are **all-rights-reserved**: we use them as **design reference only** (the colour language, the category taxonomy, the iron-priority insight) and author entirely our own modules, names, lists, and colours. Our `meta.name`/module names are Gilded-Tome-branded.

---

## 12. Validation & testing

We cannot run the plugin's Java parser, so we validate **structurally** + with **golden assertions**:
- `data/validate_loot_filter.py` (committed gate): balanced `{}`/`/*@ */`; every `#define` referenced is defined; every colour is a valid 8-hex ARGB; every `rule`/`apply` has a condition + a body; every trophy `id:` resolves in `item_dictionary.json`; the filter is `accountType:1`-gated; module order is the §5 order. Exits non-zero on violation.
- **Unit tests:** the name-pattern matcher (mithril gear → metal:mithril/blue; "Grimy ranarr" → herb/green; "Fire rune" → rune/red; a non-resource → fallback); the palette grade↔style mapping; the clog id-list emission (a known clog item appears in a trophy `id:` rule with the trophy style + never-hidden guard).
- **Golden over the committed `.rs2f`:** assert the emitted file contains the trophy module gated to clog ids, a mithril-blue gear rule, a fire-rune-red rule, the SS→E fallback ladder, `accountType:1`, and the `meta`. Byte-stable re-generation (re-run == committed, zero diff).
- Full suite stays green; the 3 existing validators still exit 0; engine/overlays/KG untouched.

---

## 13. Scope boundaries / deferred to v2 (designed-for, not built)

- **Account tailoring** (the seam): beam the collection-log slots you still NEED; hide banked items; skill-aware value. Needs the collection-log/bank ingest (the deferred RuneLite bank-data ingestion follow-up).
- **Granular per-content supply curation** (per-boss hide-lists, supply-drop tuning) — the user customises, or v2.
- **Rarity sub-ranking** of trophies (`drop_rates.json` 1/N) once a clean per-item rarity signal is chosen.
- **Main-account variant** (the format supports `accountType` gating; v1 is iron-first).
- **Custom `.wav` sound pack** (v1 uses built-in cache sounds).
- **Live/auto-publish** to filterscape (v1 emits the file; sharing is manual).
