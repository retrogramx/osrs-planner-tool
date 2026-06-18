# OSRS Wiki Source-of-Truth Catalog for Gilded Tome

This catalog maps, per domain, the canonical Old School RuneScape Wiki pages and APIs that Gilded Tome should treat as source-of-truth data inputs. Every entry was verified live against the wiki (page existence, URL resolution, API responses, and schema/field names). **Sourcing is OSRS Wiki only** (`oldschool.runescape.wiki` plus the wiki's official `prices.runescape.wiki` real-time price API); no third-party scrapers or community sites. All OSRS Wiki content is licensed **CC BY-NC-SA 3.0** — non-commercial use, attribution, and share-alike apply to any ingested data and derived works. **Status: provisional research input.** These maps inform the ingest pipeline design; they are not a committed schema. The wiki's data layer is mid-migration (Semantic MediaWiki `action=ask` is hard-deprecated and replaced by the Bucket API), and editorial/hand-maintained sources drift with game updates, so periodic re-scrape and revision checks are required.

Shape legend: `api` (queryable JSON endpoint), `module` (Lua/JSON data page, fetch via `?action=raw`), `wikitable` (rendered/wikitext table), `template` (data-encoding template family), `infobox`, `mixed`, `prose`, `category`, `calculator`. Parseable: `yes` (clean structured), `partial` (structured wrapper, free-text inside), `no` (prose).

> **Provenance note:** §1 (Skill training) was produced by a standalone re-run after the main audit's verify pass hit a transient socket error; the other 13 domains came from the main fan-out (map + adversarial verify, 29 agents). The structured per-domain maps are saved alongside this file as `wiki-source-catalog.maps.json`.

---

## 1. Skill training methods + XP rates

| Page | URL | Data | Shape | Parseable | Account-type variants |
|------|-----|------|-------|-----------|----------------------|
| Skill training guides (hub) | https://oldschool.runescape.wiki/w/Skill_training_guides | Index/hub linking every per-skill guide; columns by account type (Members, F2P, Ironman, UIM); no rates itself | Hub (links + nav templates) | Partial | Main, F2P, Ironman, UIM |
| Category:Training guides | https://oldschool.runescape.wiki/w/Category:Training_guides | Authoritative flat list (~92 pages) of all per-skill guides incl. P2P/F2P/Ironman/UIM; use for page discovery via category API | Category | Yes | Main, F2P, Ironman, UIM |
| Pay-to-play Woodcutting training (representative per-skill guide) | https://oldschool.runescape.wiki/w/Pay-to-play_Woodcutting_training | Per-method XP/h-by-level wikitables under "Fastest experience" | Wikitable (hand-authored) + prose | Partial | Main |
| Thieving training (representative general guide) | https://oldschool.runescape.wiki/w/Thieving_training | Level-banded method tables w/ XP/h columns; some embed chart template | Wikitable + prose + some chart template | Partial | Main |
| Theoretical experience rates | https://oldschool.runescape.wiki/w/Theoretical_experience_rates | ~25 computed XP/hr-vs-level charts (Thieving & WC); richest concentration of structured chart-template data | Template invocations → embedded JSON scatter charts | Yes | — |
| Template:Skilling experience rate chart (+ /doc) | https://oldschool.runescape.wiki/w/Template:Skilling_experience_rate_chart | Structured XP/hr encoding: xpPerAction, ticksPerAction, failurePenalty, xpBonus, per-method low/high/req/label; doc gives formula | Template (named params) | Yes | — |
| Module:Skilling experience rate chart | https://oldschool.runescape.wiki/w/Module:Skilling_experience_rate_chart | Lua calc logic: rate=(3600/tickDelay)*xpPerAction*(1+xpBonus) adjusted for success/failure; no stored rate values | Module (Lua logic) | Yes | — |
| Module:Skilling success chart | https://oldschool.runescape.wiki/w/Module:Skilling_success_chart | Lua interpolation logic for success prob by level; data passed via params | Module (Lua logic) | Yes | — |
| Experience rate (methodology) | https://oldschool.runescape.wiki/w/Experience_rate | Explains 3-factor model (actions/hr × xp/action × cost); ~3 example rows | Prose + small wikitable | No | — |
| Calculators hub + Calculator:<Skill> | https://oldschool.runescape.wiki/w/Calculators | Per-skill calculators (~20 skills); goal-based (items/XP to reach level), GE-price aware | Calculator | Partial | — |

**Best machine-readable entry point:** `{{Skilling experience rate chart}}` template invocations fetched via `https://oldschool.runescape.wiki/w/<Page>?action=raw` (e.g. `Theoretical_experience_rates` and many training guides). Named params (`xpPerAction`, `ticksPerAction`, `failurePenalty`, `xpBonus`, per-method `low/high/req`) deterministically yield XP/hr-by-level via the formula in `Module:Skilling experience rate chart`. Discover target pages via `Category:Training guides`. Coverage is partial — many per-skill guides use hand-authored XP/h wikitables instead (also parseable via `?action=raw`).

**Gaps:**
1. No single page/module holds XP/hr for all 23 skills — scattered across ~92 guide pages with inconsistent formats.
2. The chart template covers only a subset of methods/skills (heavily Thieving & Woodcutting); most guides use non-standardized manual wikitables.
3. No account-type field in the data — main/Ironman/HCIM/UIM/GIM differences are separate guide pages (`Ironman_Guide/*`, `UIM_Guides`); HCIM/GIM thinnest.
4. Several skills (Agility, Construction, Farming, Fletching, Herblore, Hunter, Slayer) lack the F2P/P2P split — single general guide only.
5. Per-skill Calculator pages are goal-based, not XP/hr-by-band — no substitute for rate data.
6. Success-rate values aren't stored in the Lua modules (logic only) — they live inline in each template invocation; no central data dump.

**Confidence:** high

---

## 2. Optimal quest order

The editorial "minimise training" order is hand-curated wikitext (parse `?action=raw`, not rendered HTML — cumulative levels are computed at render time via `{{#vardefine}}` and shown as icons). The structured dependency graph lives in `Module:Questreq/data` (topo-sort it for any valid order + account-type-aware gating).

| Page | URL | Data | Shape | Parseable | Account-type variants |
|---|---|---|---|---|---|
| Optimal quest guide | https://oldschool.runescape.wiki/w/Optimal_quest_guide | Canonical recommended quest order for members mains; ordered wikitable + inline `{{Optimal quest\|skill=xp}}` / `{{Optimal quest/train}}` / `{{Optimal quest/qp}}` templates; "Notable quest unlocks" prose | wikitable | partial | main |
| Module:Questreq/data | https://oldschool.runescape.wiki/w/Module:Questreq/data | Per-quest (+ miniquest/diary) prerequisite quests + `[skill, level]` reqs with `ironman`/`boostable` modifiers (~1,900 entries). The dependency DAG | module | yes | main, ironman |
| Module:Questreq | https://oldschool.runescape.wiki/w/Module:Questreq | Logic layer over /data (recursive prereq expansion, flags ironman/boostable). Documents field semantics; does NOT topo-sort | module | yes | main, ironman |
| Optimal quest guide/Ironman | https://oldschool.runescape.wiki/w/Optimal_quest_guide/Ironman | Recommended order for standard Ironman (de-facto HCIM/GIM too); same template encoding | wikitable | partial | ironman |
| Optimal quest guide/Free-to-play | https://oldschool.runescape.wiki/w/Optimal_quest_guide/Free-to-play | F2P main order (~23 quests, ends Dragon Slayer I) + GE cost table | wikitable | partial | main |
| Optimal quest guide/Free-to-play/Ironman | https://oldschool.runescape.wiki/w/Optimal_quest_guide/Free-to-play/Ironman | F2P Ironman order (~25 rows, 49 QP); carries `{{Incomplete}}` banner — treat order as provisional | wikitable | partial | ironman |
| Template:Optimal quest (+ /qp, /train, /action) | https://oldschool.runescape.wiki/w/Template:Optimal_quest | Per-quest skill XP encoding; `skill=xp` pairs for 24 skills (incl. Sailing); uses `{{#vardefine}}`, not Lua | template | partial | main, ironman |
| Template:Optimal quest guide/Recommended Quests | https://oldschool.runescape.wiki/w/Template:Optimal_quest_guide/Recommended_Quests | Transcluded "notable quest unlocks" prose (skill/area/transport/equipment) | template | no | main, ironman |
| Ultimate Ironman Guide/Quests | https://oldschool.runescape.wiki/w/Ultimate_Ironman_Guide/Quests | UIM quest reference (item/weight/inventory obstacles); NOT an order | mixed | partial | ultimate ironman |
| Quests/List | https://oldschool.runescape.wiki/w/Quests/List | Catalog of all quests (difficulty, length, QP, series, release). NOT an order; good join table | wikitable | yes | — |

---

## 3. Quest data (per-quest requirements, XP rewards, item & access unlocks, quest points)

No single source has everything — a JOIN is mandatory: Bucket `quest` (core details) + `Module:Questreq/data` (clean req DAG) + `Quests/List` (QP/release/members) + `Quest experience rewards` (XP) + `Quest item rewards` / per-quest `{{Quest rewards}}` (item/access unlocks).

| Page | URL | Data | Shape | Parseable | Account-type variants |
|---|---|---|---|---|---|
| Bucket API — quest bucket | https://oldschool.runescape.wiki/api.php?action=bucket&format=json&query=bucket('quest').select('page_name','official_difficulty','official_length','start_point','requirements','items_required','enemies_to_defeat','ironman_concerns','description','json').run() | Per-quest metadata: difficulty, length, start_point, requirements, items_required, enemies_to_defeat, ironman_concerns, description (reqs/items/enemies are inline wikitext). Omits QP, XP, release, members | api | partial | main, ironman |
| Module:Questreq/data | https://oldschool.runescape.wiki/w/Module:Questreq/data | Normalized prereq quests + `{skill, level, flags}` (ironman/boostable). E.g. Animal Magnetism: Crafting 19, Prayer 31 (ironman), Ranged 30, Slayer 18, Woodcutting 35. No XP/items/QP/unlocks | module | yes | main, ironman |
| Quest experience rewards | https://oldschool.runescape.wiki/w/Quest_experience_rewards | Per-skill XP reward tables (~23 skills) + "Skill choice" (flexible lamps/books) section. Hand-maintained, hardcoded values | wikitable | partial | main |
| Quest experience rewards (F2P) | https://oldschool.runescape.wiki/w/Quest_experience_rewards_(F2P) | F2P-only fixed-skill + lamp XP (12 quests) | wikitable | partial | main |
| Quests/List | https://oldschool.runescape.wiki/w/Quests/List | Master roster: QP, difficulty, length, series, release, members (180 quests / 335 QP). Best QP source | wikitable | yes | main |
| Quests/Requirements by quest | https://oldschool.runescape.wiki/w/Quests/Requirements_by_quest | Quest-indexed reqs by tier (skills/quests/QP/combat/enemy) + DPL overall list. Ironman notes as footnotes | mixed | partial | main, ironman |
| Quests/Requirements by skill | https://oldschool.runescape.wiki/w/Quests/Requirements_by_skill | Inverse index: per skill, quests requiring it (Quest/Level/Boostable). Ironman special cases as footnotes | wikitable | partial | main, ironman |
| Per-quest pages: `{{Quest details}}` + `{{Quest rewards}}` (e.g. Animal Magnetism) | https://oldschool.runescape.wiki/w/Animal_Magnetism | Fullest single-quest picture: start/difficulty/length/reqs/items/enemies/ironman + qp + rewards blob (XP, item unlocks, ACCESS/FEATURE unlocks). Semi-structured free text | template | partial | main, ironman |
| Module:QuestDetails (logic) / Bucket:Quest (schema) | https://oldschool.runescape.wiki/w/Bucket:Quest | Schema for the quest bucket (all TEXT fields). Confirms QP/XP/release/members are NOT indexed. `ironman_concerns` is the account-type field | api | partial | main, ironman |
| Quest item rewards | https://oldschool.runescape.wiki/w/Quest_item_rewards | Per-quest ITEM rewards (weapons/armour/misc/cosmetics/coins). Tagged incomplete, hand-maintained, no quantity/members cols | wikitable | partial | main |
| Quest items/Need for quest | https://oldschool.runescape.wiki/w/Quest_items/Need_for_quest | Item-indexed inverse of item REQUIREMENTS (found-in/used-in/needed/used-for). Cross-check only, no quantities | wikitable | partial | main |

---

## 4. Bosses / PVM rates (kc/hr by method, entry requirements, notable drops/unlocks)

Join two Bucket tables on boss/page name: `money_making_guide` (kc/hr + profit + reqs + drops, all inside the `json` blob) and `infobox_monster` (combat/slayer entry reqs + weaknesses, real top-level columns).

| Page | URL | Data | Shape | Parseable | Account-type variants |
|---|---|---|---|---|---|
| Bucket API — money_making_guide (kc/hr + reqs + drops) | https://oldschool.runescape.wiki/api.php?action=bucket&format=json&query=bucket('money_making_guide').select('page_name','value','json').where('page_name','Money making guide/Killing Zulrah').run() | `json` blob holds `prices.default_kph` (Zulrah 20, Cerberus 50), profit, members, skill/quest reqs (text), category, intensity, inputs (supplies), outputs (drops). Only 4 top-level fields: page_name, value, recurring, json | api | yes | main |
| Bucket:Money making guide (schema) | https://oldschool.runescape.wiki/w/Bucket:Money_making_guide | Confirms 3 declared fields (value TEXT, recurring BOOLEAN, json TEXT) + page_name. kc/hr lives inside json | module | yes | main |
| Module:Mmgtable / Template:Mmgtable | https://oldschool.runescape.wiki/w/Module:Mmgtable | Lua source: params kph, `kph name`, Skill, Quest, Item, Members, Category, Input1..75, Output1..75. Writes `put({value, recurring, json})` | module | partial | main |
| Money making guide (index) | https://oldschool.runescape.wiki/w/Money_making_guide | Sortable index (profit/hr, skills, category, intensity, members). Shows profit, NOT kc/hr | wikitable | partial | main |
| Per-boss guides ("Killing X", e.g. Cerberus) | https://oldschool.runescape.wiki/w/Money_making_guide/Killing_Cerberus | Baseline kph + profit + structured inputs/outputs. Per-gear-setup kc/hr (Tbow ~40, Scythe ~52) is PROSE only | mixed | partial | main |
| Bucket API — infobox_monster (combat/slayer reqs) | https://oldschool.runescape.wiki/api.php?action=bucket&format=json&query=bucket('infobox_monster').select('page_name','combat_level','hitpoints','slayer_level','slayer_experience','elemental_weakness','max_hit').where('page_name','Cerberus').run() | Per-monster combat/entry data (Cerberus: cb 318, hp 600, slayer 91, weakness Water). ~3,210 records. Real top-level columns | api | yes | main |
| Bestiary/Bosses | https://oldschool.runescape.wiki/w/Bestiary/Bosses | 200+ bosses by combat level: stats, defence bonuses, weakness. Same data as infobox_monster | wikitable | yes | main |
| Boss (overview/enumeration) | https://oldschool.runescape.wiki/w/Boss | Categorised boss list (World/Slayer/Raids/etc.) with level/hp/style/location/reqs/collection log. Best list seed | wikitable | partial | main |
| Ironman money making guide | https://oldschool.runescape.wiki/w/Ironman_money_making_guide | Tiered prose tables of self-sufficient PvM; no structured kc/hr column | prose | no | ironman, HCIM, UIM |

---

## 5. Account-type cost split (GP/XP vs gather)

Two backbones: `money_making_guide` bucket (methods: empty `inputs[]` = gather/ironman-friendly, GP-valued `inputs[]` = main GP cost) and `Module:Skill calc/<Skill>` (uniform per-skill training methods with xp + materials). Gather-vs-buy is DERIVED, not a labeled field. Price layer: `Module:GEPrices/data.json` (name-keyed) or the Real-time Prices API (id-keyed).

| Page | URL | Data | Shape | Parseable | Account-type variants |
|---|---|---|---|---|---|
| Bucket API — money_making_guide | https://oldschool.runescape.wiki/api.php?action=bucket&format=json&query=bucket('money_making_guide').select('value','recurring','json').run() | 627 rows; `json` holds activity/members/category/skill/intensity/quest/inputs[]/outputs[] (each `{name, value, qty, pricetype}`). `where()` cannot LIKE/substring the json — filter client-side | api | yes | main, ironman |
| Module:Mmgtable | https://oldschool.runescape.wiki/w/Module:Mmgtable | Canonical MMG data model (inputs = GP cost, outputs = gather value); GE tax 2% capped 5M. XP via internal handleXP() (not guaranteed per row) | module | yes | main, ironman |
| Module:Skill calc/<Skill> (e.g. Smithing) | https://oldschool.runescape.wiki/w/Module:Skill_calc/Smithing?action=raw | Uniform Lua: per-method `{name, level, xp, materials[], outputItem, members, type}` (~170 Smithing entries; ~20 skills). Better than Pay-to-play wikitables | module | yes | main |
| Module:GEPrices/data.json | https://oldschool.runescape.wiki/w/Module:GEPrices/data.json?action=raw | Name-keyed `{item: price}` JSON + `%LAST_UPDATE%` ts. Wiki-internal price source for cost recompute | module | yes | main |
| RuneScape:Real-time Prices (API) | https://prices.runescape.wiki/api/v1/osrs/latest | id-keyed live GE prices (`/latest`, `/mapping`, `/5m`, `/1h`, `/timeseries`) + volume + highalch. Use `/mapping` highalch for ironman alch valuation | api | yes | main, ironman |
| Money making guide (hub) | https://oldschool.runescape.wiki/w/Money_making_guide | Rendered index (profit/skills/category/intensity/members); per-method sub-pages carry input/output detail. Parse the bucket, not HTML | mixed | partial | main, ironman |
| Ironman money making guide | https://oldschool.runescape.wiki/w/Ironman_money_making_guide | Hand-maintained tables: Method/Profit/Hourly XP/Resources/Reqs/Notes + UIM/HCIM badge icons. Not bucket-backed | wikitable | partial | ironman, HCIM, UIM |
| Free-to-play Ironman guide | https://oldschool.runescape.wiki/w/Free-to-play_Ironman_guide | F2P ironman self-sourced money + gather training (XP rates, GP/XP, resource cost). Covers all 4 ironman sub-variants | mixed | partial | ironman, HCIM, UIM, GIM |
| Skill training guides (index) | https://oldschool.runescape.wiki/w/Skill_training_guides | Per-skill links (P2P / F2P / Ironman / UIM); 24 skills, conditional links. Navigation only | category | partial | main, ironman, UIM |
| Pay-to-play <Skill> training (e.g. Smithing) | https://oldschool.runescape.wiki/w/Pay-to-play_Smithing_training | Main-account training tables (XP/h, GP/h, GP/XP, profit). Custom per-method layout; prefer Module:Skill calc | wikitable | partial | main |
| Ironman Guide/<Skill> (e.g. Crafting) | https://oldschool.runescape.wiki/w/Ironman_Guide/Crafting | Per-skill ironman training, gather vs buy paths. Prose-dominant, sparse tables | prose | partial | ironman, HCIM |
| Ironman guide (+ Ultimate Ironman Guide) | https://oldschool.runescape.wiki/w/Ironman_guide | Top-level strategy hubs; enumerate variant sub-pages + restriction context | prose | no | ironman, HCIM, UIM, GIM |
| Group Ironman Mode | https://oldschool.runescape.wiki/w/Group_Ironman_Mode | Canonical GIM: trade caps, shared storage unlock task table, HCGIM rules. Closes the GIM gap | mixed | partial | GIM, HCIM |

---

## 6. Items / equipment requirements + gear progression

Two official APIs: the Bucket API for STATS (`infobox_bonuses` joined with `infobox_item` on page name) and the Real-time Prices API for PRICES + an item dictionary. Gear recommendations: `recommended_equipment` bucket (parse wikilink strings). **Wield/skill-to-wield requirements have NO structured source** — prose-extract or source externally (RuneLite/cache).

| Page | URL | Data | Shape | Parseable | Account-type variants |
|---|---|---|---|---|---|
| Bucket API — infobox_bonuses | https://oldschool.runescape.wiki/api.php?action=bucket&format=json&query=bucket('infobox_bonuses').select('stab_attack_bonus','slash_attack_bonus','crush_attack_bonus','range_attack_bonus','magic_attack_bonus','stab_defence_bonus','slash_defence_bonus','crush_defence_bonus','range_defence_bonus','magic_defence_bonus','strength_bonus','ranged_strength_bonus','magic_damage_bonus','prayer_bonus','equipment_slot','weapon_attack_speed','weapon_attack_range','combat_style').run() | 18 equipment-stat fields (attack/defence bonuses, str, rstr, mdmg, prayer, slot, speed, style). No wield reqs. Bare `.run()` errors — must select fields | api | yes | — |
| Bucket API — infobox_item | https://oldschool.runescape.wiki/api.php?action=bucket&format=json&query=bucket('infobox_item').select('item_name','item_id','is_members_only','weight','value','high_alchemy_value','buy_limit','tradeable','quest','examine').limit(3).run() | 17 metadata fields (item_id, is_members_only, high_alchemy_value, buy_limit, tradeable, weight, value, release/removal, league_region, version_anchor). No `type`/`slot`/req fields. Booleans return `''`/`'true'` | api | yes | — |
| Real-time Prices API — /mapping + /latest /5m /1h /timeseries | https://prices.runescape.wiki/api/v1/osrs/mapping | `/mapping`: id/name/members/limit/value/highalch/lowalch/examine/icon. Best itemId↔name↔members dictionary + live GE cost | api | yes | — |
| Bucket API — recommended_equipment | https://oldschool.runescape.wiki/api.php?action=bucket&format=json&query=bucket('recommended_equipment').select('json','page_name').limit(2).run() | Per-activity/boss loadouts: slot→ordered item alternatives (wikitext link strings to parse) + page_name + optional style. Queryable field is `json` | api | partial | — |
| Bucket API — recipe | https://oldschool.runescape.wiki/api.php?action=bucket&format=json&query=bucket('recipe').select('uses_material','uses_skill','uses_tool','uses_facility','production_json').limit(2).run() | Structured production recipes; `production_json` has skill+level+xp to CRAFT (not wield). Closest structured skill-level gate for crafted gear | api | partial | — |
| Bucket API — exchange | https://oldschool.runescape.wiki/api.php?action=bucket&format=json&query=bucket('exchange').select('id','name','value','high_alch','low_alch','limit','is_alchable').limit(3).run() | Static GE/valuation: id, value, high_alch, low_alch, limit, is_alchable. Same layer as stats queries | api | yes | — |
| RuneScape:Bucket (system docs) | https://oldschool.runescape.wiki/w/RuneScape:Bucket | Query syntax, SMW deprecation, bucket discovery (`Special:AllPages?namespace=9592`) | prose | no | — |
| Template:Infobox Bonuses (+ /doc) | https://oldschool.runescape.wiki/w/Template:Infobox_Bonuses | Source template (params astab/str/mdmg/slot/speed…). Template→bucket rename layer; no req params | template | partial | — |
| Module:FetchItemStats / Equipment / Used in recommended equipment | https://oldschool.runescape.wiki/w/Module:FetchItemStats | Renderers/fetchers over the buckets — NOT data sources. Confirm reqs absent here too | module | partial | — |
| Slot tables (e.g. Two-handed) + Category:Slot tables | https://oldschool.runescape.wiki/w/Two-handed_slot_table | Per-slot stat tables (HTML equivalent of infobox_bonuses). No reqs column; redundant fallback | wikitable | partial | — |
| Armour/Highest bonuses (+ Melee/Ranged/Magic) | https://oldschool.runescape.wiki/w/Armour/Highest_bonuses | Curated best-per-stat-per-slot tables. Style-based, not req-annotated, not a path | wikitable | partial | — |
| Guide:Melee/Ranged/Magic Gear Progression | https://oldschool.runescape.wiki/w/Guide:Melee_Gear_Progression | Tiered BiS narrative (F2P→endgame) as image widgets + prose; only end-of-page cost table semi-parseable | mixed | no | main |
| Ironman/UIM equipment guides | https://oldschool.runescape.wiki/w/Ultimate_Ironman_Guide/Equipment | Account-type-aware gear advice/constraints — prose only, the sole account-type gear source | prose | no | ironman, HCIM, UIM, GIM |

---

## 7. Unlocks, area access & transport (account unlocks, area access, fairy rings, spirit trees, teleports with prerequisites)

No single machine-readable page; SMW `ask` API is DISABLED. Layer the standard MediaWiki API: `action=parse&prop=wikitext` for tables, `action=raw` for modules. The wiki tracks only Members vs F2P; ironman-family nuances are prose only.

| Page | URL | Data | Shape | Parseable | Account-type variants |
|---|---|---|---|---|---|
| Unlockable content | https://oldschool.runescape.wiki/w/Unlockable_content | Master cross-domain index (19 sections incl. Locations/Transportation/Magics/Diaries) — Content / Members / Requirements / Notes. Strongest single entry point (incomplete for Sailing) | wikitable | yes | main, f2p |
| Transportation | https://oldschool.runescape.wiki/w/Transportation | All member transport hub. Teleport/jewellery/tablet sections are wikitables; fairy rings/spirit trees/gliders are PROSE | mixed | partial | main, f2p |
| Teleportation spells | https://oldschool.runescape.wiki/w/Teleportation_spells | All teleport spells by spellbook: icon/spell/Level/runes/XP/Members/Notes. Quest/diary prereqs in Notes (linked) | wikitable | yes | main, f2p |
| Module:Fairycode | https://oldschool.runescape.wiki/w/Module:Fairycode | Lua dict: fairy ring code → "Region: Location" string. NO coords, NO requirements | module | yes | main |
| Fairy rings | https://oldschool.runescape.wiki/w/Fairy_rings | Per-ring tables (Code/Map/Location/PoI) + global unlock (Fairytale I + dramen/lunar staff or elite L&D Diary). Per-ring gates as cell prose | wikitable | partial | main |
| Spirit tree | https://oldschool.runescape.wiki/w/Spirit_tree | Network + plantable patch locations with quest/Farming prereqs. Bulleted PROSE; access-vs-plant not separated | prose | no | main |
| Gnome glider | https://oldschool.runescape.wiki/w/Gnome_glider | Route table (Symbol/Name/Location = place name). Per-route quest gates in prose | wikitable | partial | main |
| Free-to-play transportation | https://oldschool.runescape.wiki/w/Free-to-play_transportation | F2P-only transport (teleports/canoes/items/NPCs/shortcuts) as consistent wikitables. Cleanest F2P subset | wikitable | yes | f2p |
| Ironman guide (Transportation section) | https://oldschool.runescape.wiki/w/Ironman_guide | Only page with account-type-specific (ironman-family) transport guidance. Prose, derive nuances | prose | no | ironman, HCIM, UIM, GIM |
| Map:Transportation | https://oldschool.runescape.wiki/w/Map:Transportation | Visual Leaflet map/legend of transport systems. NO GeoJSON/coordinate layer exposed | mixed | no | main |

---

## 8. Achievement Diaries

No official Module/Lua data namespace for diary tasks — both `Achievement_Diary/All_achievements` and the per-region pages are hand-written wikitables (parse `?action=raw`, resolve `{{SCP}}`/`{{NA}}`/`{{RuneReq}}`/`{{Boostable}}`). The only Lua diary data is a user sandbox (WIP, sub-modules 404). Recommended: parse per-region pages as authoritative, cross-check against All_achievements.

| Page | URL | Data | Shape | Parseable | Account-type variants |
|---|---|---|---|---|---|
| Achievement Diary/All achievements | https://oldschool.runescape.wiki/w/Achievement_Diary/All_achievements | Every task across 12 regions/4 tiers, grouped into 23 skill sections + special sections. Hand-written wikitables (no Sailing, no master template) | wikitable | partial | main, ironman |
| Achievement Diary (hub) | https://oldschool.runescape.wiki/w/Achievement_Diary | Overview (492 tasks, 12 regions, 4 tiers), region summary table (taskmaster + reward type), per-tier req sections | mixed | partial | main, ironman |
| Template:Achievement diary (navbox) | https://oldschool.runescape.wiki/w/Template:Achievement_diary | Cleanest index of all 12 region page URLs + per-tier reward item names. No task reqs | template | yes | main, ironman |
| Varrock Diary (representative per-region) | https://oldschool.runescape.wiki/w/Varrock_Diary | One region: 4 tier task tables (Task + Requirements via `{{SCP}}`/`{{NA}}`/`{{Boostable}}`) + reward subsections. Ironman footnotes | wikitable | partial | main, ironman |
| Kourend & Kebos Diary (canonical name) | https://oldschool.runescape.wiki/w/Kourend_%26_Kebos_Diary | Same structure as Varrock; pins the one region whose name varies (ampersand, `%26`) | wikitable | partial | main, ironman |
| Achievement Diary/Rewards | https://oldschool.runescape.wiki/w/Achievement_Diary/Rewards | Per-tier reward items + antique lamp XP (Easy 2,500 / Med 7,500 / Hard 15,000 / Elite 50,000) + Bonuses wikitable (reward equipment stats) | mixed | partial | main, ironman |
| Category:Achievement diaries | https://oldschool.runescape.wiki/w/Category:Achievement_diaries | ~92 diary-ecosystem pages (regions + reward items + NPCs). Completeness checklist; filter to `*_Diary` | category | partial | main |
| Module:Sandbox/User:Jakesterwars/Diary calculator | https://oldschool.runescape.wiki/w/Module:Sandbox/User:Jakesterwars/Diary_calculator | Unofficial WIP Lua calc; per-region data sub-modules 404. NOT source of truth | module | no | main |
| RuneScape:WikiSync | https://oldschool.runescape.wiki/w/RuneScape:WikiSync | Per-player diary TASK completion (not definitions). API explicitly NOT for third-party use | api | partial | main, ironman |

---

## 9. Combat Achievements

The `combat_achievement` Bucket is THE authoritative store. **Pass an explicit `.limit(5000)`** — the default row cap silently truncates. Point value is derived from tier (easy=1…grandmaster=6), not stored. Base CAs are universal across account types; the only variant axis is Leagues.

| Page | URL | Data | Shape | Parseable | Account-type variants |
|---|---|---|---|---|---|
| Bucket API — combat_achievement | https://oldschool.runescape.wiki/api.php?action=bucket&format=json&query=bucket('combat_achievement').select('id','name','monster','task','tier','type','league_region').limit(5000).run() | Every CA task: id, name, monster, task, tier (Capitalized), type, league_region. Tasks generate all rendered pages. No reqs field | api | yes | — |
| Module:Combat Achievements | https://oldschool.runescape.wiki/w/Module:Combat_Achievements | Logic only: canonical query + tier→points map + `leagueautocompletes` backfill. Read for schema, query the bucket | module | partial | — |
| Module:Combat Achievements/completion.json | https://oldschool.runescape.wiki/w/Module:Combat_Achievements/completion.json | id → completion %. Sparse non-contiguous keys. Join on id (optional community stat) | module | yes | — |
| Module:Combat Achievements/leaguecompletion.json | https://oldschool.runescape.wiki/w/Module:Combat_Achievements/leaguecompletion.json | id → Leagues completion %. Empty `{}` outside an active League | module | yes | Leagues |
| Combat Achievements (main) | https://oldschool.runescape.wiki/w/Combat_Achievements | Authoritative tier counts (41/60/85/162/168/121 = 637) + cumulative reward thresholds (Easy 41 … GM 2630). Bucket lacks these | mixed | partial | — |
| Combat Achievements/All tasks | https://oldschool.runescape.wiki/w/Combat_Achievements/All_tasks | Single 637-row table (Monster/Name/Description/Type/Tier/Comp%). Cross-check / row-count source | wikitable | yes | — |
| Combat Achievements/Tasks by boss | https://oldschool.runescape.wiki/w/Combat_Achievements/Tasks_by_boss | Tasks grouped by boss (~70 sections) with per-boss point subtotals | wikitable | yes | — |
| Combat Achievements/Tasks by region | https://oldschool.runescape.wiki/w/Combat_Achievements/Tasks_by_region | Tasks grouped by game region; cross-check for the bucket's league_region field | wikitable | yes | — |
| Per-tier pages (Easy…Grandmaster) | https://oldschool.runescape.wiki/w/Combat_Achievements/Easy | Per-tier filtered views (no points column). Fallback | wikitable | yes | — |
| Template:Leagues Combat Achievements / League CA pages | https://oldschool.runescape.wiki/w/Template:Leagues_Combat_Achievements | Leagues variant of CAs (League-specific tasks/points/regions) on per-League subpages | template | partial | Leagues |

---

## 10. Money-making methods

The `money_making_guide` bucket (~744 rows; multi-Version methods = one row each) is the single best entry point. Only `page_name`/`value`/`recurring`/`json` are top-level — members/category/intensity/skill live inside the `json` TEXT blob and CANNOT be filtered server-side. Default page size 500; paginate with `.limit()`/`.offset()`. Profit is point-in-time (live GE, 2% tax capped 5M).

| Page | URL | Data | Shape | Parseable | Account-type variants |
|---|---|---|---|---|---|
| Bucket API — money_making_guide | https://oldschool.runescape.wiki/api.php?action=bucket&format=json&query=bucket('money_making_guide').select('page_name','value','recurring','json').limit(500).offset(0).run() | All methods; `json` holds skill (rendered HTML), quest, category, intensity, inputs[]/outputs[], prices{default_kph…}. value is TEXT (numeric where unreliable); recurring=false omitted in select | api | yes | main |
| Bucket:Money making guide (schema) | https://oldschool.runescape.wiki/w/Bucket:Money_making_guide | Schema + live preview; confirms value(TEXT)/recurring(BOOLEAN)/json(TEXT) | api | yes | main |
| RuneScape:Bucket (API docs) | https://oldschool.runescape.wiki/w/RuneScape:Bucket | Query syntax, lowercase+underscore rule, SMW deprecation | api | yes | main |
| Special:Bucket (query UI) | https://oldschool.runescape.wiki/w/Special:Bucket | Interactive Select/Where/Limit/Offset builder for prototyping | api | yes | main |
| Money making guide (index) | https://oldschool.runescape.wiki/w/Money_making_guide | Rendered master table (lossy: no inputs/outputs/quests). Sub-pages /Collecting //Combat //Processing //Skilling //Recurring //Free-to-play | wikitable | partial | main |
| Money making guide/Free-to-play | https://oldschool.runescape.wiki/w/Money_making_guide/Free-to-play | Cleanest ready-made F2P list (bucket can't server-side filter members) | wikitable | partial | main, ironman |
| Individual method pages (e.g. Killing green dragons) | https://oldschool.runescape.wiki/w/Money_making_guide/Killing_green_dragons | `{{Mmgtable}}` authoring source (one or, with Version tabs, multiple bucket rows) | template | partial | main |
| Template:Mmgtable | https://oldschool.runescape.wiki/w/Template:Mmgtable | Authoring schema/field reference (Activity/Version/Skill/Item/Quest/Input#/Output#/kph/isperkill) | template | no | main |
| Module:Mmgtable | https://oldschool.runescape.wiki/w/Module:Mmgtable | Renderer + bucket writer; gp/hr math incl. GE tax (2% capped 5M). recurring is a real boolean | module | no | main |
| Ironman money making guide | https://oldschool.runescape.wiki/w/Ironman_money_making_guide | Hand-maintained tables (Method/Profit/Hourly XP/Resources/Reqs) + UIM/HCIM badges. NOT bucket-backed, no GIM | mixed | partial | ironman, UIM, HCIM |

---

## 11. Clue scrolls (Treasure Trails): tiers, step types, requirements, drop sources, rewards

The Bucket API supersedes hard-deprecated SMW. Drop sources & reward rows are unified in `Bucket:Dropsline` (detail nested in the `drop_json` blob). No single Lua module holds all clue data.

| Page | URL | Data | Shape | Parseable | Account-type variants |
|---|---|---|---|---|---|
| Treasure Trails | https://oldschool.runescape.wiki/w/Treasure_Trails | Canonical hub: difficulty/step-count table (beginner 1-3 … master 6-8), step-type matrix, antagonists, average-value, ranks, milestone tables | mixed | partial | — |
| Clue scroll (hard) (representative per-tier item) | https://oldschool.runescape.wiki/w/Clue_scroll_(hard) | `{{Infobox Item}}` + `{{Drop sources}}` (Lua/Bucket-backed 150+ sources) for easy/med/hard/elite. Infobox `id = N/A` (get item_id from Bucket). Master/beginner are casket/activity-sourced | infobox | yes | — |
| Reward casket (master) (representative reward casket) | https://oldschool.runescape.wiki/w/Reward_casket_(master) | Reward tables (roll counts, uniques/standard/shared/tertiary, per-roll rarity, GE price, high alch). `{{DropsLineReward}}` rows; some rarities via `{{#expr}}` | wikitable | yes | — |
| Bucket API — dropsline + infobox_item | https://oldschool.runescape.wiki/api.php?action=bucket&format=json&query=bucket('dropsline').select('item_name','drop_json','rare_drop_table').where('item_name','Clue scroll (hard)').limit(2).run() | Drop sources/rewards: `drop_json` has Dropped item/from, Rarity, Drop Quantity, Drop level, Rolls, League region. Most machine-parseable layer (supersedes SMW) | api | yes | — |
| Treasure Trails/Full guide/All (+ per-step-type/tier subpages) | https://oldschool.runescape.wiki/w/Treasure_Trails/Full_guide/All | Clue STEPS: text/solution/location/requirements via `{{Cryptics}}`/`{{Anagrams}}`/`{{Emotes}}`/`{{Coordinates}}`. Notes field bundles reqs as prose | template | partial | — |
| Module:DropsLine / Template:Drop sources (engine) | https://oldschool.runescape.wiki/w/Module:DropsLine | Drop-row engine writing Bucket:Dropsline; `{{Drop sources}}` reads it via Module:Get drop info. Schema/engine, not data | module | yes | — |

---

## 12. Minigames

For the LIST + (incomplete) members: `infobox_activity` bucket (thin schema: page_name/page_name_sub/image/is_members_only/default_version — cross-check the per-page `members` param). For REWARDS: the `storeline` bucket (NOT `store`). For REQUIREMENTS: parse `{{Infobox Activity}}` params per page via `?action=raw` (many reqs are body prose only).

| Page | URL | Data | Shape | Parseable | Account-type variants |
|---|---|---|---|---|---|
| Minigames (hub) | https://oldschool.runescape.wiki/w/Minigames | Curated taxonomy (Combat/Skilling/Both/Minigame-like bosses) — region/classification/skills/description/rewards (prose) | wikitable | partial | — |
| Category:Minigames | https://oldschool.runescape.wiki/w/Category:Minigames | ~52 minigame articles + 48 subcategories. Cleanest membership set (`list=categorymembers`) | category | yes | — |
| Bucket:Infobox activity | https://oldschool.runescape.wiki/w/Bucket:Infobox_activity | ~99 entries; queryable list + members flag (often empty/unreliable). Thin schema; no reqs/skills/currency/location | api | yes | main, ironman |
| Module:Infobox Activity (+ Template) | https://oldschool.runescape.wiki/w/Module:Infobox_Activity | Lua source-of-truth for params (type enum, requirements/skills/currency in wikitext, not bucketed) | module | partial | — |
| Reward shops via Template:StoreLine → `storeline` bucket | https://oldschool.runescape.wiki/w/Bucket:Storeline | Reward shops (~6,237 rows): sold_by, sold_item, store_buy_price, store_currency, store_stock. Best rewards source (currency strings must match exactly) | api | yes | main |
| Currencies | https://oldschool.runescape.wiki/w/Currencies | Minigame reward currencies (Honour points, Zeal Tokens, etc.) → activity. Join table to `store_currency` | wikitable | partial | — |
| Ultimate Ironman Guide/Minigames | https://oldschool.runescape.wiki/w/Ultimate_Ironman_Guide/Minigames | Only dedicated account-type minigames subpage (UIM death/item limitations). Prose; HCIM/GIM notes inline on pages | prose | no | ironman, HCIM, UIM, GIM |

---

## 13. Live Grand Exchange prices

`/latest` (live feed, keyed by numeric item ID) paired with `/mapping` (id→name/limit/alch join table). The economy is shared, so prices are identical across account types (but ironman-family accounts cannot use the GE — GE gp is informational/relative-value for them). **A descriptive custom User-Agent is required** (default client UAs like python-requests/curl are blocked); trust live endpoint field names over the prose docs.

| Page | URL | Data | Shape | Parseable | Account-type variants |
|---|---|---|---|---|---|
| RuneScape:Real-time Prices (docs) | https://oldschool.runescape.wiki/w/RuneScape:Real-time_Prices | Spec: base URLs (osrs + dmm), all endpoints, JSON shapes, required UA + blocked default UAs. Prose field names are loose | api | yes | main (osrs), Deadman/DMM (/api/v1/dmm) |
| /latest endpoint | https://prices.runescape.wiki/api/v1/osrs/latest | All tradeable items keyed by id: `{high, highTime, low, lowTime}`. Null/absent for thin/never-traded items. One GET, don't loop per-id | api | yes | main |
| /mapping endpoint | https://prices.runescape.wiki/api/v1/osrs/mapping | JSON ARRAY: `{examine, id, members, lowalch, limit, value, highalch, icon, name}`. Required to resolve ids→names + GE buy limits. Cache it | api | yes | main |
| /5m, /1h endpoints | https://prices.runescape.wiki/api/v1/osrs/5m | Time-averaged `{avgHighPrice, avgLowPrice, highPriceVolume, lowPriceVolume}`. Volume = liquidity check. Optional `?timestamp=` | api | yes | main, DMM |
| /timeseries endpoint | https://prices.runescape.wiki/api/v1/osrs/timeseries?id=4151&timestep=5m | Up to 365 points per id: `{timestamp, avgHighPrice, avgLowPrice, …Volume}` + itemId. timestep 5m/1h/6h/24h | api | yes | main, DMM |
| Module:GEPrices/data.json | https://oldschool.runescape.wiki/w/Module:GEPrices/data.json?action=raw | Name-keyed `{item: price}` + `%LAST_UPDATE%`/`%LAST_UPDATE_F%`. Periodic (~daily) snapshot fallback; strip metadata keys | module | yes | main |
| Module:GEVolumes/data.json | https://oldschool.runescape.wiki/w/Module:GEVolumes/data.json?action=raw | Name-keyed `{item: daily volume}` (~5,000+); snapshot liquidity companion to GEPrices | module | yes | main |
| Module:GEIDs/data.json | https://oldschool.runescape.wiki/w/Module:GEIDs/data.json?action=raw | Name→numeric id map (~4,000+). Redundant with /mapping for live pipelines | module | yes | main |
| Module:Exchange + per-item subpages | https://oldschool.runescape.wiki/w/Module:Exchange/Abyssal_whip | Static per-item metadata (itemId/limit/alch/value); field is `item` not `name`, `value`=base not market. No live price | module | partial | main |

---

## Best machine-readable entry points (target these FIRST)

The ingest pipeline should prioritise the structured query/data layers below over scraping rendered HTML. Three families:

**A. OSRS Wiki Bucket API** — `https://oldschool.runescape.wiki/api.php?action=bucket` (the official replacement for hard-deprecated SMW `action=ask`, returns JSON; syntax `bucket('name').select(...).where(...).limit(n).run()`, all bucket/field names lowercase_with_underscores; requires a descriptive User-Agent). Target buckets:
- `quest` — per-quest core details (difficulty/length/start/reqs/items/enemies/ironman_concerns).
- `infobox_monster` — boss/monster combat & slayer entry reqs + weaknesses (real top-level columns; ~3,210 rows; dedupe on page_name).
- `infobox_bonuses` (18 fields) joined with `infobox_item` (17 fields) on page name — equipment stats + item metadata. `recipe` for structured production skill levels; `exchange` for static GE limits/alch.
- `money_making_guide` — kc/hr + profit + reqs + inputs(supplies)/outputs(drops) (4 top-level fields; decode the `json` blob; pass explicit `.limit()`/`.offset()` to paginate ~744 rows; cannot LIKE/substring-filter the json — filter client-side).
- `combat_achievement` — all CA tasks (**must pass `.limit(5000)`** or it silently truncates; derive points from tier).
- `dropsline` — clue/monster drop sources + reward-casket rows (detail nested in `drop_json`).
- `infobox_activity` (thin: list + members) and `storeline` (minigame/shop rewards: item + cost + currency, ~6,237 rows).
- Discover/monitor all buckets at `https://oldschool.runescape.wiki/w/Special:AllPages?namespace=9592`; read each `Bucket:<Name>` schema page before building queries (field names are exact and unforgiving).

**B. Module:/Lua + JSON data pages** (fetch via `?action=raw`; enumerate the namespace via `action=query&list=allpages&apnamespace=828`):
- `Module:Questreq/data` — the quest + diary requirement DAG (skills + prereq quests, with `ironman`/`boostable` flags). The cleanest progression-logic source.
- `Module:Skill calc/<Skill>` — uniform per-skill training methods (name/level/xp/materials); strictly better than the bespoke Pay-to-play wikitables.
- `Module:Experience/data` — XP curve (procedural — execute the Lua or reimplement `total=floor(total + i + 300*2^(i/7))`, `ret=floor(total/4)`).
- `Module:Collection log/data.json` — clean collection-log structure (id/name/tabs).
- `Module:User hiscores` — account-type alias → Hiscores table map (main/ironman/hardcore/ultimate/skiller/pure).
- `Module:Fairycode` — fairy ring code → location strings.
- `Module:GEPrices/data.json` (+ `GEVolumes`, `GEIDs`) — name-keyed wiki price/volume/id snapshots.

**C. Calculators** — `https://oldschool.runescape.wiki/w/Calculators` (per-skill XP, Combat level, DPS, etc.). The calculator UIs are not directly DB-parseable; target their **backing data modules** (`Module:Skill calc/<Skill>`) instead of scraping the pages.

**D. Real-time Prices API** — `https://prices.runescape.wiki/api/v1/osrs/` (the wiki's official live GE feed; descriptive User-Agent required, default client UAs blocked). Pull `/latest` (live prices by item id) + `/mapping` (id↔name↔limit↔alch dictionary) in single bulk calls (do NOT loop per-id); use `/5m`, `/1h`, `/timeseries` for smoothed prices + volume. This is the canonical cost/valuation layer; reconcile its id-space with the Bucket layer (`infobox_item.item_id`, `exchange.id`) via numeric id, falling back to canonical name.

---

## Gaps & risks

**Editorial / unstructured data the wiki does not cleanly provide:**
- **Optimal quest ORDER** is hand-curated wikitext only (no Lua/JSON). A *valid* order is machine-derivable (topo-sort `Module:Questreq/data`), but the editorial "minimise training" optimisation is wikitext-parse-only and changes with updates (`{{Sync}}` markers). Recommended skill LEVELS at each step are computed cumulatively via `{{#vardefine}}` and rendered as icons; raw wikitext stores only per-quest XP deltas (replay accumulation or read flat levels from Questreq/data).
- **Quest ACCESS/FEATURE unlocks** (area access, fairy rings, spellbooks, teleports, shop access) have NO normalized/queryable store — free text in each quest's `{{Quest rewards}}` blob. Quest ITEM rewards have a partial dedicated page (`Quest item rewards`) but it is incomplete/hand-maintained.
- **Wield/skill-to-wield requirements** for equipment have NO structured source anywhere (absent from `infobox_bonuses`, `infobox_item`, slot tables). Prose-only (e.g. Abyssal whip "Attack 70"); the `recipe` bucket gives skill levels to PRODUCE, not wield. Must be regex/LLM-extracted or sourced externally (RuneLite/cache item defs).
- **Gear progression** is only partially machine-readable: `recommended_equipment` gives per-activity loadouts (with wikilink strings to parse) but is not a tiered F2P→endgame DAG; the tiered narrative (`Guide:*_Gear_Progression`) is prose/image-widgets.
- **Transport node requirements** (fairy rings, spirit trees, gnome gliders) are embedded as inline prose in table cells; spirit trees have no table at all. NO transport Module (only `Module:Fairycode`, code→location with no coords/reqs). SMW `ask` is DISABLED on this wiki — all structured extraction must use `action=parse`/`action=raw`. No geographic-coordinate data layer is exposed (`Map:Transportation` is a visual legend only).
- **Achievement diary tasks** have no official Lua/Bucket store — hand-written wikitables (resolve `{{SCP}}`/`{{NA}}`/`{{RuneReq}}`/`{{Boostable}}`); the only Lua diary calc is a user sandbox (404s). Reward effects/benefits are prose (only equipment-stat bonuses are tabular).
- **Per-task CA requirements** are not stored; point values and reward-tier thresholds live only on the main CA page (scrape separately). The `league_region` field is partly in-module backfilled and can be sparse.
- **Clue STEP requirements** are free prose inside step-template Notes; per-clue step count is a range only.
- **Minigame requirements** (incl. quest prereqs and many level reqs) are often body prose, not in the infobox; the `infobox_activity` `is_members_only` flag is unreliable/empty for many rows — cross-check the per-page `members` param.

**Account-type granularity (a cross-cutting gap):**
- Structured data distinguishes only **main vs ironman** (`ironman` flags in `Module:Questreq/data`, `ironman_concerns` in `Bucket:Quest`). There is NO structured HCIM/UIM/GIM requirement variance; those modes inherit ironman, and GIM/HCGIM are absent even from `Module:User hiscores`.
- **Account-type cost/viability** (GP-buy vs gather) is DERIVED, not labeled: empty `inputs[]` / self-gatherable materials = ironman-friendly. UIM/HCIM viability appears only as inline chat-badge icon IMAGES on prose ironman guides; GIM economy (group trading caps, shared storage) lives only on `Group_Ironman_Mode` as prose + one table.
- No **account-type-aware kc/hr** anywhere — `money_making_guide` assumes a main with buyable supplies.

**Pricing, freshness & operational risks:**
- All profit/cost/GP-per-XP values are point-in-time (live GE; rendered pages additionally serve cached prices). Any ingest must record a fetch/price timestamp and re-poll; `Module:GEPrices/data.json` carries `%LAST_UPDATE%` (strip the synthetic metadata keys). The two price spaces (name-keyed wiki modules vs id-keyed Real-time API) require the `/mapping` endpoint to join.
- The Real-time Prices API blocks default client User-Agents (python-requests, curl, Java, etc.) and applies discretionary blocking for sustained high-frequency querying — set a descriptive UA with contact info and cache aggressively. `/latest` field SHAPE is the breaking-change signal; values changing is normal. Live `/5m`/`/1h`/`/timeseries` field names (`avgHighPrice`/`avgLowPrice`/`highPriceVolume`/`lowPriceVolume`) differ from the prose docs — trust the endpoints.
- **Bucket footguns:** template params (`astab`, `str`) ≠ bucket columns (`stab_attack_bonus`, `strength_bonus`); `infobox_item` uses `is_members_only`/`high_alchemy_value` and has no `type`/`slot` field; `recommended_equipment`/`money_making_guide` queryable field is `json`; a bare `.run()` without `.select()` errors; boolean fields return `''`/`'true'` strings (coerce); `where()` supports equality only (no `~`/LIKE, no nested `json.*` keys); `combat_achievement` needs explicit `.limit(5000)`; `money_making_guide` defaults to 500 rows (paginate). Multi-version items produce multiple bucket rows per page name (handle `version_anchor`/Version).
- All listed sources are hand-syncable / editorial-prone and drift with game updates (quest counts, QP totals, task counts, new releases). Periodic re-scrape + revision/`%LAST_UPDATE%` checks are mandatory, and a sample of `Module:Questreq/data` should be validated against `{{Quest details}}` after each update.
- **WikiSync** (per-player quest/diary/CA completion) is explicitly off-limits for third-party API use — not a viable completion-state source. The official Hiscores do not track diary points/CA progress.
