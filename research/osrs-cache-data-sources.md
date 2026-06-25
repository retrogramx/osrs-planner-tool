<!-- Research input: can cached OSRS data make building the world entity-graph trivial?
Generated 2026-06-24 by verifying the public sources via WebFetch. Two data planes:
(A) world/content graph = the big build; (B) account/player state = already covered (Hiscores/bank). -->

## Verified source status

| Source | Status | Plane | Node layer |
|---|---|---|---|
| OpenRS2 Archive | live-maintained | world-content | yes |
| RuneLite cache tooling | live-maintained | world-content | partly |
| osrsbox-db | live-unmaintained | world-content | yes |
| OSRS Wiki structured data | live-maintained | world-content | yes |
| WikiSync | live-maintained | account-state | no |
| Other cache-dump tools/data | live-maintained | world-content | partly |

---

# Can cached OSRS data make building the world entity-graph trivial?

## 1. TL;DR

**Partly — and exactly in the half that's currently the most tedious.** The game CACHE (via OpenRS2 + a decoder) trivializes plane (A)'s **NODE layer**: the existence and intrinsic attributes of every item (incl. equipment stats), NPC, object, and map location become a one-time **bulk import** with authoritative, stable IDs — replacing perpetual page-by-page wiki transcription. But the cache gives you **zero edges**: which NPC runs which shop, shop stock, drop tables/mechanics, quest+diary requirement DAGs, diary-gated discounts, transport conditions, and lore are **not in the cache** and still require the Wiki (Bucket/Lua) + curation. So cache and wiki are **complementary, not either/or**. Note for the record: the "browser AI" answer that pointed at WikiSync was answering about **plane (B) account/player state** (one player's skills/quests/diaries) — that's the lane we already cover via Hiscores + bank export, and it does **not** build the world graph at all.

## 2. Pull this to make the node layer trivial

**Pipeline:** `OpenRS2 Archive (download a dated OSRS cache + XTEA keys)` → `RuneLite net.runelite.cache decoder` (or `Joshua-F/osrs-dumps` pre-decoded JSON) → **bulk per-entity JSON** for items / NPCs / objects / map.

| Stage | Source | Access | Licensing | Status |
|---|---|---|---|---|
| Cache snapshot + XTEA keys | OpenRS2 Archive (`archive.openrs2.org`) | Public HTTP, no auth; rsync mirror + DB dumps for bulk | Tooling ISC; **cache contents = Jagex IP** (preservation posture, no rights grant) | **live-maintained** |
| Decoder (cache → JSON) | RuneLite `cache/` Gradle subproject (`net.runelite.cache.Cache --items/--npcs/--objects`) | Clone + Gradle build + CLI; one JSON per entity id | **BSD-2-Clause** (tooling only; decoded data is Jagex IP) | **live-maintained** |
| Shortcut (skip the decode) | `Joshua-F/osrs-dumps` (pre-dumped JSON of all caches) | Clone-and-read GitHub, no client needed | Cache content = Jagex IP | live (verify freshness vs live build before relying) |

**What each entity type gets for free:**
- **Items → the item/equipment-stats layer we deferred.** id, name, examine, equip slot (`wearPos`), weight, stackable/tradeable/members flags, noted/placeholder links, store/alch value field. ⚠️ Caveat: RuneLite's `ItemDefinition` does **not** expose a decoded attack/strength/defence/prayer **combat bonus block** (it's slot + a raw params map) — osrsbox/osrsreboxed or the Wiki still supply usable equipment bonuses. So "items+stats for free" = roster + intrinsic attributes; the full combat-bonus table is a join, not a gimme.
- **NPCs.** id, name, combat level, size, examine, race/aggression flags, transmog configs; `stats[6]` is base levels, not a full combat block.
- **Objects/scenery.** id, name, examine, interaction action strings ("Mine"/"Open"/"Climb"), varbit/varp config, placed instances per map square.
- **Map/locations.** Region geometry, area definitions, world-map elements (needs XTEA keys to decrypt regions). Gives raw tiles/region ids — **not** semantic places like "Edgeville" / "in the Wilderness" (that naming is editorial).

**Canonical-ID win:** cache ids are the clean join key to Hiscores, bank export, and the Wiki — adopt them as the primary key for every node.

## 3. Still needs the wiki + curation (the edges the cache can't give)

The cache is flat per-id attributes; the planner reasons over **edges and conditionals**, none of which are in it:

- **Which-NPC-runs-which-shop** — shop operator binding is not a clean cache field.
- **Shop stock / restock / price** — `bucket:storeline` lists stock lines (Wiki), not in cache.
- **Drop tables AND drop mechanism** — drop rates are **server-side, never in the cache**. `bucket:dropsline` gives a flat `(item, monster, rate)` table but **does not encode RDT/GDT vs direct vs on-task** — reuse the repo's **Option-A "expose flat, never fabricate the condition"** policy.
- **Quest + diary requirement DAGs** — live in `Module:Questreq/data` Lua, not a relational bucket; must be transcribed/curated as traversable edges.
- **Diary-gated discounts / boosts / conditionals** — e.g. "medium CAs → Ghommal's hilt 2 → negates Barrows prayer drain" is **unsayable** from cache or buckets; pure curation.
- **Transport conditions, route `prepares-for` edges, lore.** Editorial — hand/source-grounded (and per the repo's own lesson, **every connective edge must be grounded, never fabricated for demo shape**).

**This is precisely where the Varrock pilot earns its keep:** the pilot's value was never the node roster — it's authoring exactly these edges (shop operators, gated discounts, transport, drop conditions) with source grounding. Cache + Wiki are complementary halves of plane (A).

## 4. Don't bother / be careful

- **`osrsbox/osrsbox-db` (original) — DON'T.** Functionally abandoned: last push **2022-08-07** (~4 yrs stale), `api.osrsbox.com` / static host effectively dead (403). It is **not** GitHub-flagged "archived" and its README still self-claims "up-to-date" — **misleading; do not trust that claim.**
- **`0xNeffarion/osrsreboxed-db` (successor) — usable with a caveat.** Maintained continuation (last push **2025-01-07**, includes original author), and it's the **best pre-decoded shortcut** for items+monsters+prayers **and a strong first-pass at monster drop tables**. But it **lags live OSRS by ~1.5 yrs** → reconcile anything added after early 2025 against the live Wiki. **GPL-3.0 copyleft** is a redistribution consideration for a public project.
- **WikiSync — wrong plane AND off-limits.** It's plane (B) (one player's state), and the Wiki explicitly says the API is *"intended for use by the wiki, and not by third-party developers"* / *"Please do not use the WikiSync API in your own projects."* Do not consume it for the world graph (or at all).
- **Viewers are not exports.** Chisel **MOID** and **RuneMonk Entity Viewer** are browse-one-entity web UIs (great for spot-check/QA and grabbing an id) — **no documented bulk JSON API**, so they cannot drive ingestion. (RuneMonk's per-model GLTF has broken UVs/colours; Chisel's separate GE-price dump is prices, not the entity graph.)
- **Licensing seam to keep straight:** decoder tooling (BSD/ISC) ≠ cache contents (**Jagex IP**) ≠ Wiki text (**CC BY-NC-SA 3.0, NonCommercial**). The NC clause is fine for a vibe-coded non-commercial planner but a **blocker if Gilded Tome ever monetizes**. Cache dumps do **not** inherit the wiki license; treat decoded content as "derive-your-own from the public cache."

## 5. Recommended plan change

**Invert the build order: nodes first (bulk, automated), edges second (curated, onto known nodes).**

1. **Bulk-import the cache NODE layer first.** Pull a recent OSRS cache from **OpenRS2**, decode with the **RuneLite cache module** (or seed faster from `Joshua-F/osrs-dumps` / `osrsreboxed`), and emit existence-nodes for **every item (with intrinsic attrs + equip slot), every NPC, every object, every map region/location**, keyed by **cache id**. This single step closes the deferred **item/equipment node layer** and guarantees roster completeness (no missed entities) — something page-by-page transcription never gives.
2. **Join equipment combat bonuses** from `osrsreboxed` / Wiki onto those item nodes (cache gives slot, not the bonus block).
3. **Then run the Wiki/Bucket/Lua + LLM/curation pass to add ONLY the EDGES** onto already-existing, id-stable nodes: shop-operator + stock, drop lines (flat, Option-A), quest/diary req DAGs, diary-gated discounts, transport, routes. Adding edges to known nodes is **far less work** than transcribing nodes-and-edges together, and it removes a whole class of errors (mismatched/missing entities, id drift).
4. **Promote the Varrock pilot to the edge-authoring template.** It stops being a "build a city from scratch" exercise and becomes the **repeatable pattern for authoring grounded edges over cache-imported nodes** — the unit of work that scales the graph city-by-city / domain-by-domain.

**Net:** the cache makes the *node* layer trivially bulk-importable and gives a clean canonical id backbone; it makes the *edge/conditional/editorial* layer **no easier** — that remains the real Gilded Tome build (Wiki + grounded curation), and it's exactly what the Varrock pilot is for.

**Status flags:** OpenRS2, RuneLite cache module, OSRS Wiki Bucket, WikiSync = **live-maintained** (verified). `osrsbox-db` original = **stale/effectively dead** (avoid). `osrsreboxed-db` successor = **live but ~1.5 yr behind** (reconcile post-early-2025 content). `Joshua-F/osrs-dumps` freshness should be verified against the target build before relying on it as the shortcut.
