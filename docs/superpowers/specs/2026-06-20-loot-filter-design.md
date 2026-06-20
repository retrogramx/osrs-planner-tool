# Loot-Filter Generator — Design (v2)

**Status:** v1 design approved 2026-06-20; **v2 revision 2026-06-20** folds in the plan-review findings (verified against Storn's real filter + `item_dictionary.json`) and promotes account **tailoring** into scope (now that `feat/account-ingest` is merged). Spec under review → revised implementation plan next.
**Brick:** `feat/loot-filter`. An OUTPUT product: generates a RuneLite "Loot Filters" (`riktenx/loot-filters`) `.rs2f` filter from our committed data + (optionally) a player's real `AccountState`.
**Builds on:** the merged collection-log + drop-rate data; `data/item_dictionary.json` (name→id); **`src/osrs_planner/account/`** (`build_account_state`, `AccountState.counts` + `clog_obtained`) for tailoring. Reference filters (Storn's Iron Filter, Joe's) are **all-rights-reserved — design reference ONLY**.

---

## 1. Purpose & scope

Auto-generate a genuinely-impressive, account-aware **ironman** loot filter: a coherent **two-axis visual language** (hue = *what it is*, emphasis = *how much you care*) over every drop, a **collection-log trophy layer** no existing filter has, and — the payoff — **tailoring to YOUR account** (beam the log slots you still need; optionally hide what you already bank).

**v2 delivers:**
- A **generic** filter (`generate_filter(account_state=None)`) — same for any iron, shareable.
- A **tailored** filter (`generate_filter(account_state=<from account-ingest>)`) — **missing** collection-log items get the full beam; **obtained** clog items dim to a quiet highlight; an opt-in toggle hides items already in your bank.
- Honest framing: the plugin computes `value`/`havalue`/`gevalue` **natively**, so value-tiering is not our edge. Our edge = (1) **collection-log awareness** (trophy layer + missing-slot beam) and (2) a curated, **item-accurate** visual language generated instead of hand-authored.

**v2 does NOT:** do granular per-content supply curation (per-boss hide-lists); rarity-sub-rank trophies; ship a main-account variant (it's `accountType:1`-gated, iron-first); bundle custom `.wav` audio (uses built-in cache sound ids). See §13.

---

## 2. Load-bearing decisions

1. **Iron-gated** via a `#define IRONMAN accountType:1` macro on every styling rule (incl. settings) — inert on a non-iron account. **NOT named `IRON`** (that collides with the plugin's built-in `IRON` colour keyword; macros are pure textual substitution — finding [3]).
2. **Two orthogonal axes:** **hue = identity** (material/type colour, or trophy gold/bronze) · **emphasis = value** (faded → colour → border → beam → +sound). Modelled on Storn's palette.
3. **General tiering uses `value` (max GE/HA), GE-inclusive.** `havalue` is reserved for alch-specific calls.
4. **Collection-log = the trophy + tailoring layer** (the differentiator).
5. **Resources get item-accurate colour, shown by default** (iron-usefulness ≠ value).
6. **Categories derived by NAME PATTERN, but explicitly enumerated, never bare globs** — `"Rune *"` over-matches 122 items (ammo/essence/pouch/Black mask/Dragon bones — findings [4][5][7]). Gear = explicit per-metal name-lists; ores/bars = a real-name table (`Bronze` doesn't exist as an ore; bars/ores use `Adamantite`/`Runite`, not `Adamant`/`Rune`).
7. **Nothing is hidden by default** (Storn's model): a `HIDE_FLOOR` toggle exists (default **off**), and tailoring's hide-owned toggle defaults **off**. The filter colours/tiers everything until the user opts into hiding (finding [6]).
8. **Modular filterscape rs2f**; our own modules/names/colours. The `/*@ define:module/input */` annotation syntax + the `apply (!SHOW_X && cond)` toggle idiom are **verified against Storn's real shipping filter** (NOT documented in the plugin's `filter-lang.md` — that was a wrong citation; the syntax itself is correct — findings [1][2]).

---

## 3. Architecture & boundary

`src/osrs_planner/lootfilter/` — assembles a `.rs2f` from committed config + data (+ optional account state):

| File | Responsibility |
|---|---|
| `palette.py` | material/type → colour map + value-grade styles + trophy ramp. Pure data. |
| `categories.py` | name-pattern → category rules (explicit enumerations; gear-word-gated) + `categorize()` matcher. |
| `emit.py` | the rs2f emitter (modules, `#define`s, `rule`/`apply`, `meta`, the IRONMAN gate). |
| `tailor.py` | **NEW:** account-aware rules — missing-clog beam, obtained-clog dim, hide-owned — from an `AccountState`. |
| `generate.py` | orchestrator `generate_filter(account_state=None) -> str` + `write_filter()`. |
| `data/validate_loot_filter.py` | committed structural validator. |
| `outputs/gilded-tome-iron.rs2f` | committed **generic** artifact (byte-stable). |
| `scripts/lootfilter_demo.py` | regenerates generic + prints a tailored example over the account fixtures. |

**Boundary:** `lootfilter/` imports stdlib + (for tailoring) `osrs_planner.account.state.AccountState` / reads `data/*.json`; it must NOT import the engine/cost/income overlay logic, and the KG is untouched. (`tailor.py` consumes an already-built `AccountState` — it does not call the ingestion itself.)

---

## 4. The rs2f target format

Custom text DSL. `meta { name=…; description=…; }` + `/*@ define:module:<id> … */` (grouping) + `/*@ define:input:<module> … */` (UI toggles) + C-style `#define`. `rule (<conds>) { <style> }` (terminal) / `apply (…) { … }` (non-terminal). Match: `value`/`gevalue`/`havalue`, `id:[…]`, `name:["…","* wild *"]`, `quantity`, `ownership:<n>`, `accountType:<n>`, joined `&& || !`. Style: `textColor`/`backgroundColor`/`borderColor`/`lootbeamColor` (8-hex ARGB), `showLootbeam`/`showValue`/`showDespawn`/`hidden`/`notify` (bool), `fontType` (1-3), `textAccent` (1-4), `menuSort` (int), `sound` (cache-id int or `"x.wav"`). Value matching is stack-total.

**Verified toggle idiom (Storn):** `#define SHOW_GLOBAL_DROPS true` then `apply (!SHOW_GLOBAL_DROPS && ownership:0) { hidden = true; }` — a `#define`'d bool negated inside a condition IS valid. The `/*@ define:module:<id>` block fields seen in Storn: `name:`, `subtitle:`, `description:`, `hidden:`; `/*@ define:input:<module>` fields: `label:`, `type: boolean`, `group:`.

---

## 5. Module structure (emit order = evaluation order)

```
meta { … }                #define IRONMAN accountType:1  +  colour/threshold #defines
module: settings          # toggles (show/value/despawn/HIDE_FLOOR), all IRONMAN-gated (finding [8])
module: tailoring         # ONLY when account_state given: missing-clog beam, obtained dim, hide-owned (§9)
module: trophies          # collection-log -> gold/bronze + beam + sound, never-hide guard
module: categories        # name-pattern groups, item-hue coloured, value-graded
module: fallback          # the SS->E value ladder + the optional HIDE_FLOOR cut
```

`tailoring` sits **above** `trophies` so a missing-clog beam / hide-owned decision wins over the generic trophy style.

---

## 6. The two-axis visual language

**HUE = what it is** (material/type colour; gold/bronze trophy; value-red for an uncategorised high-value drop). **EMPHASIS = how much you care**, by value grade: `faded → coloured text → +border → +loot beam → +sound`, rendered in the item's hue. A valuable mithril item = bright blue + blue beam + sound; a cheap one = dim blue.

---

## 7. Value model, grade ladder & hide floor

Grades by `value` (Storn's breakpoints): SS ≥10m, S ≥1m, A ≥100k, B ≥10k, C ≥1k, D ≥100, E <100. Escalation: **beam at S+, sound at A+**. The `fallback` ladder applies it uncoloured; `categories`/`trophies` apply the same ladder tinted by hue.

**Hide floor (finding [6], default OFF):** `#define HIDE_FLOOR 0` with a `define:input` knob; emit, ABOVE the E grade, `rule (IRONMAN && value:<HIDE_FLOOR) { hidden = true; }`. With the default `0` nothing is hidden (Storn's model); a user raises it to prune clutter. Trophies + tailoring sit above fallback, so the floor never hides a clog item or a beamed missing-slot.

---

## 8. Collection-log trophy layer

For each `collection_log.json` item id (1,907): the **gold/bronze "unique" palette** (distinct from value-red), **always `showLootbeam` + a `sound`**, graded SS–C by `value`; plus a non-terminal `apply (IRONMAN && id:[…]) { hidden = false; }` never-hide guard (so even a cheap clog item pops, and the hide floor can't bury it). Emitted as `id:[…]` lists (ids via `item_dictionary.json`). Rarity sub-rank deferred.

---

## 9. Tailoring (NEW — the payoff)

`tailor.py` turns an `AccountState` (from `account.build_account_state`) into a `tailoring` module. Only emitted when `account_state` is provided (the generic filter omits it entirely).

- **Missing-clog beam:** `missing = {clog ids in collection_log.json} − account_state.clog_obtained`. Emit `rule (IRONMAN && id:[missing]) { gold beam + sound + notify }` — "you still need this." (~1,433 ids for the user.)
- **Obtained-clog dim:** `rule (IRONMAN && id:[obtained ∩ clog]) { quiet highlight, NO beam }` — "you have it." (Sits in the tailoring module above the generic trophy beam, so obtained items don't beam.)
- **Hide-owned (opt-in, default OFF):** `#define HIDE_OWNED false` + a `define:input` toggle; `apply (IRONMAN && HIDE_OWNED && id:[bank ids]) { hidden = true; }`, where `bank ids = account_state.counts` keys **minus the ENTIRE collection-log** (never hide a trophy you own, missing or obtained) **and minus high-value** (≥ A grade) — never hides something collection-relevant or valuable.
- IDs are resolved from the `"item:<n>"` keys (strip the prefix → int for `id:[…]`).

**Determinism:** all id-lists sorted. The tailored filter is NOT committed (it's account-specific, personal data — §11); only the generic one is.

---

## 10. Settings module

`/*@ define:input */` toggles, all **IRONMAN-gated** (finding [8]), mirroring Storn: show world-spawns (`SHOW_WORLD_SPAWNS` default **true**), show unowned drops (`SHOW_UNOWNED` default **true** — unlike Storn, we never hide other-players' drops by default, per the user's "don't auto-hide anything"), despawn timer (`showDespawn`), **item-value display** (`SHOW_VALUE → showValue`, finding [9]), and the **HIDE_FLOOR** knob (§7, default 0). **No toggle hides anything at its default value** — every hide is opt-in. Per-category min-value knobs are **disclosed-deferred** (a v2.1 add — finding [9]).

---

## 11. Output, determinism & licensing

- **Generic** `outputs/gilded-tome-iron.rs2f` — committed, byte-stable (fixed module order + sorted id-lists; a CI gate). The **tailored** output is generated on demand from the user's `AccountState` and **never committed** (personal data, like the bank/clog inputs).
- **Sounds:** built-in cache sound ids (no bundled audio). **Licensing:** the rs2f format is the plugin's (free to emit); reference filters are all-rights-reserved → our own modules/names/lists/colours.

---

## 12. Validation & testing

`data/validate_loot_filter.py` (committed gate, run on the generic artifact): balanced `{}`/`/*@ */`; every `#define` referenced is defined; every colour a valid 8-hex ARGB; every `rule`/`apply` has a condition + body; every trophy `id:` resolves in `item_dictionary.json`; **every `rule (` AND settings/trophy `apply (` is `IRONMAN`-gated** (finding [8]); module order is §5; the `HIDE_FLOOR` default keeps nothing hidden. Plus unit tests: the categoriser (mithril *gear-word* → metal:mithril/blue; `Rune arrow`/`Rune essence`/`Black mask` → NOT metal-gear; `Crystal weapon seed` → NOT seeds; real ore/bar names only), the palette, the trophy id-list, and `tailor.py` (missing beam, obtained dim, hide-owned excludes missing + high-value). Byte-stable generic re-gen. Full suite green; the existing validators still exit 0.

---

## 13. Deferred to a later version
Granular per-content supply curation; rarity sub-ranking of trophies; main-account variant; custom `.wav` pack; per-category min-value knobs; live/auto-publish to filterscape; banked-XP-aware value.
