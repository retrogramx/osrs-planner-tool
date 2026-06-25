# Town / Place Authoring Template — Field Guide

> **Purpose.** A hand-authoring format for the entity graph (see
> `docs/superpowers/specs/2026-06-24-entity-graph-ontology-v1.md`) that drops straight into the
> data pipeline with **zero re-modeling**. You flesh out ONE town (Varrock) by hand — it becomes the
> pilot, the schema stress-test, and the **gold-standard truth-set** that future LLM extraction is
> measured against. Author in `varrock.json`; this guide explains every field.

> **Prefer your outline style?** If hand-writing JSON is annoying, say so and I'll write an
> outline→JSON converter so you can keep authoring in the nested-bullet form from `OSRS Ontology.md`.
> Otherwise, `varrock.json` IS the deliverable — copy a record, change the values.

---

## The big idea

A town is **a place plus everything inside it**. This one file captures a complete *vertical slice* —
`World ▸ Kingdom ▸ City ▸ NPC ▸ Shop ▸ Item` + the diary/quest **conditions** that modify it. Every
record carries its **outgoing relationships inline** (an NPC lists the shops it operates; a shop lists
what it sells). A builder later flattens this into the graph's nodes + typed edges.

## Universal rules

- **`id`** = `<kind-prefix>:<slug>` — lowercase, dashes, drop apostrophes. `npc:zaff`,
  `place:varrock`, `shop:zaffs-superior-staffs`. Reuse the SAME id everywhere you reference the thing.
- **`located_in`** = the `id` of the immediately-containing place (the one `contains`/`located_in` edge).
- **`source_url`** = the OSRS wiki page for that entity (provenance — required; this is what keeps the
  graph grounded). Add a verbatim **`source_token`** wherever a number/claim needs proof (prices, conditions).
- **Don't look up item IDs.** Write `item_name`; leave `item_id: null`. The builder resolves names → ids
  and flags anything it can't (so unresolved items surface, never silently wrong).
- Leave a field **out** (or `null`) if unknown — partial is fine; the validator will WARN, not block.

---

## Sections & fields

### `places[]` — the geography hierarchy (the "place template")
One recursive kind for every geographic level, distinguished by `place_type`.

| field | meaning | → ontology |
|---|---|---|
| `id` | `place:<slug>` | node `kind=region`, `data.place_type` |
| `place_type` | `world \| continent \| ocean \| island \| kingdom \| city \| town \| settlement \| district \| dungeon` | `data.place_type` |
| `name` | display name | node `name` |
| `located_in` | parent place id (or `null` for the world root) | `located_in` edge → parent |
| `ruled_by` | *(optional)* `npc:<slug>` of the ruler | `ruled_by` edge → npc |
| `faction` | *(optional)* dominant race/polity string, e.g. `"humans"`, `"vampyres"` | `data.faction` |
| `attributes` | *(optional)* gameplay flags, e.g. `["pvp", "members"]` | `data.attributes` |
| `source_url` | wiki page | provenance |

A `district` is just a `place` with `located_in` = the city. Add as many as the town has
(Varrock Square, Varrock Palace, the Champions'/Cooks' Guild, the south-east mine, the slums…).

### `npcs[]` — non-combat characters (shopkeepers, rulers, quest-givers, bankers)
| field | meaning | → ontology |
|---|---|---|
| `id` | `npc:<slug>` (add the place if names collide: `npc:bob-lumbridge`) | node `kind=npc` |
| `name` / `role` | display + role (`shopkeeper`, `ruler`, `banker`, `quest-giver`…) | `name`, `data.role` |
| `located_in` | place id where they stand | `located_in` edge |
| `operates` | *(optional)* list of `shop:<slug>` ids they run | `operates` edges → shops |
| `source_url` | wiki page | provenance |

### `shops[]` — stores, with their stock (this is where the **conditional** lives)
| field | meaning | → ontology |
|---|---|---|
| `id` / `name` | `shop:<slug>` + display | node `kind=shop` |
| `located_in` / `operator` | place id + `npc:<slug>` owner | `located_in` + `operates` (reciprocal) |
| `currency` | usually `"coins"` (or `"tokkul"`, `"trading sticks"`…) | `data.currency` |
| `sells[]` | one object per stocked item (see below) | a `sells` edge per entry |

**A `sells[]` entry** = one offer. A plain stock line and a diary-gated discount are both just `sells`
entries — the gate is the `condition` field:
```jsonc
{ "item_name": "Battlestaff", "item_id": null, "base_price": 7000, "stock": 5 }          // normal stock
{ "item_name": "Battlestaff (noted)", "item_id": null,
  "price": 7000, "qty": 60, "frequency": "daily", "noted": true,
  "condition": { "type": "achievement_diary", "ref": "varrock:hard", "state": "completed" }, // ← the gate
  "dispenser": "barrel on the ground floor of the shop",
  "source_token": "buy noted battlestaves at a discounted price of 7,000 coins each once per day",
  "source_url": "https://oldschool.runescape.wiki/w/Varrock_Diary" }
```
- `condition` → becomes the `cond_group` on the `sells` edge (the SAME atom mechanism the diary tiers
  use). Tier-scaled offers (qty 15/30/60/120) = **one `sells` entry per tier**, each with its own
  `condition.ref` (`varrock:easy|medium|hard|elite`).
- `condition.type` can be `achievement_diary`, `quest`, `skill_level`, etc. — mirror the existing atoms.
- A normal (ungated) stock line just omits `condition`.

### `monsters[]` — attackable creatures found here
`{ id: "monster:<slug>", name, located_in, source_url }`. (Drop tables come from the existing drops
brick later — just place them for now.)

### `activities[]` — facilities & activities at the town (bank, anvil, range, altar, Grand Exchange, museum…)
`{ id: "activity:<slug>", name, activity_type, located_in, source_url }`.
`activity_type` ∈ `bank | range | anvil | furnace | altar | grand_exchange | minigame | skilling | misc`.

---

## Deferred (the builder handles — don't hand-author)
- **Transport/teleport access** (Varrock Teleport, the GE, lodestones) → a later `gives_access` pass.
- **Item-id resolution** (`item_name` → `item_id`).
- **Drop tables** (`monster → drops → item`) → the existing drops brick.

## How to flesh out Varrock (checklist)
1. Districts → `places[]` (located_in `place:varrock`).
2. Every shop → `shops[]` with full `sells[]` (incl. the diary-gated Zaff/Aubury/etc. offers).
3. Shopkeepers + notable NPCs (rulers, bankers, quest-givers) → `npcs[]`, wired via `operates`.
4. Monsters that spawn in town → `monsters[]`.
5. Facilities (bank, anvils, range, GE, Champions'/Cooks' Guild, museum) → `activities[]`.
6. Anything diary/quest-gated → put the `condition` on the relevant `sells`/entry, with a `source_token`.

When it's done: I wire the builder + a domain/range validator + competency questions ("after Varrock
Hard, where/price/qty can I buy noted battlestaves?") and we prove the whole ontology on this one town.
