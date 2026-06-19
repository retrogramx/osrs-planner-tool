# Currency model — DRAFT (for `feat/kg-ingest` + the cost layer)

> Status: design sketch, 2026-06-18. Seeds the **currency dimension** so acquisition cost can be
> `{currency, amount}` instead of gold-only. Source index = the OSRS Wiki
> [Currencies](https://oldschool.runescape.wiki/w/Currencies) page (~50 currencies; human-readable
> tables — scrape or pull `Category:Currencies`). Prices come from item/shop pages; earn-rates from
> minigame pages. NOT committed to `feat/goal-engine`.

## Why

A purchase/unlock is denominated in *some* currency. Today the engine only knows gold. Real costs:
Fighter torso = **Honour points**, Tokkul gear = **Tokkul**, Graceful = **Marks of grace**, etc.
Modeling a currency dimension lets the cost layer answer "what does this cost" in the right unit, and
link "earn N of currency C" back to the **activity that produces C**.

## Schema (per currency)

```jsonc
{
  "id": "currency:honour-points",       // currency:<slug>
  "name": "Honour points",
  "category": "virtual",                // physical_tradeable | physical_untradeable | physical_fare | virtual
  "is_item": false,                     // physical = a real item (banked); virtual = "on record" only
  "ge_tradeable": false,                // can the CURRENCY itself be GE'd? (basically only coins/platinum)
  "observable": "plugin_or_unknown",    // can we read a player's BALANCE? hiscores | plugin | plugin_or_unknown | none
  "source_activity": "activity:barbarian-assault",  // KG node that PRODUCES it (links cost back into the graph)
  "earn_rate_per_hour": null,           // TODO from the minigame/activity page
  "self_earned_only": true,             // no market for the currency -> items priced in it CONVERGE main vs iron
  "example_sinks": [                     // what it buys (verified examples; not exhaustive)
    { "item": "item:10551", "name": "Fighter torso", "amount": 375, "note": "375 per role x4 + 1 Penance Queen kill" }
  ]
}
```

**`cost` on an acquisition method becomes:** `{ "currency": "currency:<id>", "amount": N }`.
Gold is just the default currency (`currency:coins`).

## Seed entries (8 — source/sinks/category verified from the Currencies page; prices/rates marked TODO)

| id | category | is_item | ge_tradeable | observable | source_activity | self_earned_only | verified sink anchor |
|---|---|---|---|---|---|---|---|
| `currency:coins` | physical_tradeable | yes | yes | plugin (bank/inv; **not** hiscores) | most activities | **no** (universal; earning differs by acct type) | scimitar 59k(GE)/100k(shop); B.gloves 130k(shop) |
| `currency:platinum-tokens` | physical_tradeable | yes | yes | plugin | any banker (1,000 gp : 1) | no | gp-equivalent (stacking) |
| `currency:honour-points` | virtual | no | no | plugin_or_unknown | `activity:barbarian-assault` | **yes** | **Fighter torso 375/role x4 (verified)** |
| `currency:tokkul` | physical_untradeable | yes | no | plugin (it's an item) | `activity:tzhaar` (Fight Caves / Mor Ul Rek / TzHaar slayer) | **yes** | Onyx, obsidian (toktz) weapons — price TODO |
| `currency:marks-of-grace` | physical_untradeable | yes | no | plugin | `minigame:rooftop-agility` | **yes** | Graceful outfit, amylase — price TODO |
| `currency:warrior-guild-tokens` | physical_untradeable | yes | no | plugin | `minigame:warriors-guild` | **yes** | Cyclopes access → defenders — rate TODO |
| `currency:slayer-reward-points` | virtual | no | no | plugin_or_unknown | `activity:slayer-tasks` | **yes** | task unlocks, Slayer helm unlock, herb sack — price TODO |
| `currency:nmz-reward-points` | virtual | no | no | plugin_or_unknown | `minigame:nightmare-zone` | **yes** | imbues (e.g. Berserker ring (i)), herb boxes — price TODO |

## How it plugs into the engine / cost layer

1. **Item acquisition method** carries `cost {currency, amount}` + a `channel` (shop / reward-chest / drop / activity-reward).
2. The cost overlay (`expand_for_account`) picks the cheapest **allowed** channel per account type — and for a
   currency that is `self_earned_only`, there's no cheaper main route, so it **converges** (this is *why* the
   Fighter torso / MA2 cape converged — it's structural, not coincidental).
3. `source_activity` lets "need 375x4 Honour points" expand into "play Barbarian Assault (~N games)" once
   `earn_rate_per_hour` is filled — the advisor/rate layer.

## Open questions (flagged, not resolved)

- **Observability:** a player's Honour-point / Slayer-point balance is **not on the Hiscores** (virtual = likely
  plugin-only, maybe unreadable). So a current balance is often **UNKNOWN** → the absence≠zero rule applies
  to currency balances too. Physical-item currencies (Tokkul, Marks) show in bank data (plugin).
- **Is `currency` a KG node-kind or a reference table?** Leaning **reference table** (a cost denomination, not a
  prerequisite) whose `source_activity` *points at* a KG node. Confirm during `feat/kg-ingest`.
- **Earn-rates + full price lists** are per-detail-page (minigame pages / shop pages) — a sourcing task, like the
  rest of the data foundation.

## Worked example — TzHaar-ket-om (obby maul): the divergence + the earn-rate trap (2026-06-18)

Twin accounts (low-level obby-mauler pures, 1 Att / 1 Def / 60 Str), same goal: wield a TzHaar-ket-om
(wield req = **60 Strength only**; **tradeable**, GE ~**209k**; Tokkul **75,001** / **65,001** with Karamja
gloves; or a **1/512** TzHaar-Ket drop). The **engine returns the identical verdict to both** ("get the maul";
60 Str ✓) — proof the engine is **account-type-blind on acquisition**; the twins diverge entirely in the cost layer:

| | Regular (main) | Ironman |
|---|---|---|
| GE allowed | ✅ | ❌ |
| Cheapest route | **GE ~209k coins** | **75,001 Tokkul** (65,001 w/ Karamja gloves) at the TzHaar store, or 1/512 drop |
| Real effort | trivial (gp is easy) | **grind ~75k Tokkul from TzHaar content — slow, and dangerous for a 1-Def/30-HP pure** |

**Two rules this nails:**
1. **The engine handles requirement structure; the cost layer (`expand_for_account`) handles account-type
   acquisition divergence.** Clean boundary — the twins are identical to the engine, different to the cost layer.
2. **Currencies are NOT comparable by face amount — normalize by earn-rate (time).** "75k Tokkul < 209k gp" is a
   TRAP: the smaller number is the *harder* cost (Tokkul is slow to earn; gp is fast). The cost overlay must
   convert each currency amount to **effort/time via its earn-rate**, not pick the smaller number. (And the main
   can't even use Tokkul-vs-gp as a choice — GE is just easier; the iron can't use GE at all.)
3. Bonus: the **Karamja gloves discount** (75,001→65,001 Tokkul) is another **account-STATE** cost modifier
   (cf. the Barrows-gloves Elite-Lumbridge-diary discount) — diary completion lowers a shop price.
