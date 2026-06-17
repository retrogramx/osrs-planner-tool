#!/usr/bin/env python3
"""
Build data/account_cost_split.json for the Gilded Tome KG.

DOMAIN: account_cost_split
Demonstrates the per-skill cost contrast between account families:
  - main (Pay-to-play / generic <Skill> training pages): pay GP per XP (buy consumables on GE)
  - ironman (Ironman Guide/<Skill> pages): gather the materials yourself (gather-time, no GE)

Each record: { skill, account_family, method, cost_basis, value?, notes }
  cost_basis ∈ {"gp_per_xp", "gather"}  (the domain's two cost bases)
  value: snapshot object for gp_per_xp methods where the wiki renders a clean
         per-xp figure (price-volatile), else null (honest null).

SOURCING: OSRS Wiki only.
  main pages:  Pay-to-play_<Skill>_training  (or generic <Skill>_training where no PTP page exists)
  iron pages:  Ironman_Guide/<Skill>

ACCOUNT-TYPE GATE: every "main" GP/XP method here relies on buying consumables on the
Grand Exchange => requires_ge=true, audience="main", pricing_basis="ge".
Every "ironman" method is gather-based (no GE) => requires_ge=false, audience="ironman",
pricing_basis="value" (materials self-supplied), realized via gather-time not coins.
HCIM/GIM reuse the ironman family; UIM also gathers (bank-constraint noted where relevant).
"members" carried as the assumed game mode (the buyable-skill split is a members concern;
f2p contrasts noted where they exist).
"""
import json, datetime

ACCESSED = "2026-06-17T18:16:56Z"
SNAPSHOT_BASIS = "gp/xp, GE prices via OSRS Wiki {{GEP}} live templates, snapshot @ 2026-06-17 (price-volatile)"

def gpxp(v, item):
    """snapshot gp-per-xp value object (price-volatile)."""
    return {"gp_per_xp": v, "basis": SNAPSHOT_BASIS, "priced_item": item,
            "pricing_basis": "ge", "note": "Snapshot; wiki recomputes from live GE prices and drifts."}

# ---- records: (skill, family, method, cost_basis, value, requires_ge, audience, notes) ----
R = []
def add(skill, family, method, cost_basis, value, requires_ge, audience, notes):
    rec = {
        "skill": skill,
        "account_family": family,
        "method": method,
        "cost_basis": cost_basis,
        "value": value,
        "requires_ge": requires_ge,
        "audience": audience,
        "pricing_basis": "ge" if requires_ge else "value",
        "realization": "gp_per_xp_spend" if cost_basis == "gp_per_xp" else "gather_time",
        "notes": notes,
    }
    R.append(rec)

# ============================ PRAYER ============================
add("Prayer", "main",
    "Offer bones (e.g. dragon / superior dragon bones) at a gilded altar in a POH with both incense burners lit (350% xp/bone)",
    "gp_per_xp", gpxp(11.77, "Dragon bones"), True, "main",
    "Fastest Prayer is buying bones on the GE and burning them at a gilded altar. Wiki snapshot: dragon bones ~11.77 gp/xp, superior dragon bones ~42.78 gp/xp. Requires 75 Construction (boostable) for the altar. 'Most Prayer training methods are relatively expensive.'")
add("Prayer", "ironman",
    "Gather bones yourself (kill green/blue/red/frost dragons, bosses, Slayer) then offer at Chaos altar / gilded altar / Ectofuntus",
    "gather", None, False, "ironman",
    "Wiki: 'Prayer is a slower skill to train for ironmen due to having to obtain bones themselves.' Chaos altar (lvl 38 Wilderness, 700% effective xp/bone w/ no-consume) is most efficient but risky; HCIM advised to use Ectofuntus instead. Dragon bones from Wilderness/Myths' Guild/blue dragons. gp_hr null: cost is gather-time, not coins.")

# ============================ CONSTRUCTION ============================
add("Construction", "main",
    "Build & remove furniture (e.g. mahogany/teak) using GE-bought planks; Mahogany Homes or oak larders at lower levels",
    "gp_per_xp", gpxp(14.55, "Mahogany plank"), True, "main",
    "Mains buy planks on the GE. Wiki snapshot gp/xp: oak plank ~7.93, teak plank ~9.21, mahogany plank ~14.55. 'Using planks costs money... use the highest-tier planks for the fastest experience rates, or look into cheaper alternatives if trying to save money.'")
add("Construction", "ironman",
    "Make planks yourself (sawmill / Plank Make spell from gathered logs) then build furniture; Mahogany Homes for plank efficiency",
    "gather", None, False, "ironman",
    "Irons cut/convert their own logs into planks (sawmill or Plank Make) rather than buying planks on the GE. Mahogany Homes recommended to stretch limited self-made planks. Cost is woodcutting + plank-making gather-time + sawmill coins (store), not GE plank spend.")

# ============================ HERBLORE ============================
add("Herblore", "main",
    "Buy herbs + secondaries on the GE, clean & make potions (e.g. attack/strength/prayer/super potions)",
    "gp_per_xp", gpxp(6.38, "Attack potion(4)/2 + Roe (attack mix example)"), True, "main",
    "Mains buy grimy herbs and secondaries on the GE. Per-potion gp/xp varies by potion; example attack mix ~6.38 gp/xp (wiki table snapshot). Many high-tier potions cost notably more per xp.")
add("Herblore", "ironman",
    "Grow/gather herbs (farming herb runs, farming contracts, Master Farmer pickpocket, Managing Miscellania, Slayer drops) + gather secondaries; or Mastering Mixology",
    "gather", None, False, "ironman",
    "Wiki: ingredients come from 'farming, monster drops, and minigames (notably Managing Miscellania).' Farming contracts (45 Farming) are the best herb-seed source; Master Farmer pickpocketing (38 Thieving). Mastering Mixology (60+/81) needs no specific herbs/secondaries. Cost is herb/secondary gather-time, not GE spend.")

# ============================ FARMING ============================
add("Farming", "main",
    "Buy seeds + compost on the GE and run tree/herb patches (herb runs, tree runs)",
    "gp_per_xp", None, True, "main",
    "Mains buy tree seeds, herb seeds and compost/supercompost on the GE; gp/xp varies enormously by run type and seed prices (tree seeds especially expensive). Wiki gives per-run costs rather than a single gp/xp; left null (honest null).")
add("Farming", "ironman",
    "Gather seeds yourself (farming contracts, bird nests, Master Farmer pickpocket, mole parts, Tithe Farm) and make own compost",
    "gather", None, False, "ironman",
    "Wiki 'Obtaining seeds': farming contracts (best), bird nests, Master Farmer pickpocketing, etc. Irons make their own compost and run patches with self-gathered seeds. Cost is seed/compost gather-time, not GE spend.")

# ============================ COOKING ============================
add("Cooking", "main",
    "Buy raw food on the GE and cook (e.g. cooked karambwan, jugs of wine, bake pie, cooking fish)",
    "gp_per_xp", None, True, "main",
    "Mains buy raw fish / ingredients on the GE; many Cooking methods are cheap or even profitable per xp (selling cooked food). gp/xp varies by food; left null. Karambwan cooking 30-99 is the standard fast route.")
add("Cooking", "ironman",
    "Catch/gather the raw food yourself (Fishing, hunter, farming sweetcorn, karambwans) then cook",
    "gather", None, False, "ironman",
    "Wiki iron route: sardines -> trout/salmon -> sweetcorn -> cakes -> karambwans, all self-caught/grown. Cost is fishing/farming gather-time, not GE spend. Burn-rate management matters since raw food is hand-gathered.")

# ============================ CRAFTING ============================
add("Crafting", "main",
    "Buy materials on the GE (molten glass, d'hide, battlestaves, gems, gold bars) and craft",
    "gp_per_xp", gpxp(-1.40, "Molten glass (glassblowing)"), True, "main",
    "Mains buy molten glass / dragonhide / battlestaves / gems on the GE. Glassblowing snapshot ~ -1.40 gp/xp (slightly profitable). Battlestaves/d'hide are higher gp/xp. Many Crafting methods are cheap or profitable for mains.")
add("Crafting", "ironman",
    "Gather materials yourself: make molten glass (buckets of sand + soda ash, or Superglass Make), gather gold/silver ore, hides from Slayer/PvM, gems from mining",
    "gather", None, False, "ironman",
    "Wiki iron route: glassblowing 35-99 buying buckets of sand + soda ash from stores (store, not GE) then Superglass Make 61+, plus self-gathered gold/silver ore and hides. Cost is ore/hide/sand gather-time (+ store coins), not GE material spend.")

# ============================ SMITHING ============================
add("Smithing", "main",
    "Buy bars/ore on the GE and smith (Blast Furnace gold bars, dart tips, cannonballs, Giants' Foundry, 3-bar rune items)",
    "gp_per_xp", None, True, "main",
    "Mains buy ore/bars on the GE. Blast Furnace gold bars 40-99 is the standard fast main route (buy gold ore). gp/xp varies by product; some high-level routes (rune items + High Alch) approach break-even. Left null due to per-product variance.")
add("Smithing", "ironman",
    "Mine your own ore, smelt bars (Blast Furnace), then smith; Giants' Foundry, cannonballs, Zalcano",
    "gather", None, False, "ironman",
    "Irons mine ore and smelt their own bars before smithing. Iron dart tips 15-30/40, then Gold Ore Blast Furnace 40-99 (self-mined gold). Cost is mining/smelting gather-time, not GE bar spend.")

# ============================ MAGIC ============================
add("Magic", "main",
    "Buy runes (+ items to alch) on the GE: High Level Alchemy, enchanting bolts, Magic Imbue, splashing",
    "gp_per_xp", gpxp(2.30, "Astral rune x2 (Magic Imbue)"), True, "main",
    "Mains buy runes (and alch fodder) on the GE. High Level Alchemy is the staple passive route and is often net-profitable per cast. Magic Imbue snapshot ~2.30 gp/xp. Enchanting bolts 4-55/99 also buyable.")
add("Magic", "ironman",
    "Gather/craft own runes (Runecraft, GotR, drops, shop) and alch fodder; combat/utility spells via Slayer & quests",
    "gather", None, False, "ironman",
    "Irons supply their own runes (runecrafting, Guardians of the Rift, monster drops, Magic shops - store not GE) and alch fodder from drops. Bursting/barraging 65-99 via Slayer doubles as Magic xp. Cost is rune gather-time (+ store), not GE rune spend.")

# ============================ RANGED ============================
add("Ranged", "main",
    "Buy ammo on the GE (chinchompas for chinning, cannonballs, bolts/arrows) and train (Chinning, dwarf multicannon, NMZ)",
    "gp_per_xp", None, True, "main",
    "Mains buy chinchompas / cannonballs / bolts on the GE. Chinning maniacal/skeletal monkeys 45-99 with bought red/black chinchompas is the fast (expensive) route. gp/xp depends on chin/ammo price; left null.")
add("Ranged", "ironman",
    "Catch own chinchompas (Hunter) and make own ammo; Dorgeshuun crossbow, bosses/monsters, crabs, NMZ",
    "gather", None, False, "ironman",
    "Irons catch their own chinchompas via Hunter (box trapping) and fletch/make their own ammo. Chinchompas 55+ self-caught. Cost is hunter/ammo gather-time, not GE chin/ammo spend.")

# ============================ FLETCHING ============================
add("Fletching", "main",
    "Buy materials on the GE (logs, bow strings, gems for bolt tips, dart tips) and fletch (bows, broad arrows, darts, tipping bolts)",
    "gp_per_xp", None, True, "main",
    "Mains buy logs/bowstrings/gems on the GE. Fletching is frequently profitable per xp for mains (e.g. bolts, bows). gp/xp varies and is often negative (profit); left null.")
add("Fletching", "ironman",
    "Gather materials yourself: cut own logs, spin own bow strings (flax/Crafting), cut own gems for bolt tips; broad arrows via Slayer points",
    "gather", None, False, "ironman",
    "Irons cut their own logs, make their own bow strings, and cut their own gems. Broad arrows 52-99 use Slayer-reward broad arrowheads. Cost is log/string/gem gather-time, not GE material spend.")

# ============================ FIREMAKING ============================
add("Firemaking", "main",
    "Buy logs on the GE and burn them (line-burning) or make pyre logs; Wintertodt 50+",
    "gp_per_xp", None, True, "main",
    "Mains buy logs on the GE and burn them; pure cost (logs are consumed for no return) so gp/xp is positive but logs are cheap. Wintertodt 50+ avoids buying logs and gives supplies. gp/xp varies by log tier; left null.")
add("Firemaking", "ironman",
    "Cut own logs (Woodcutting) and burn them; Wintertodt 50+ (no logs needed) is the staple",
    "gather", None, False, "ironman",
    "Irons cut their own logs. Wintertodt 50+ is the recommended iron route since it needs no pre-gathered logs and rewards supplies/loot. Cost is woodcutting gather-time, not GE log spend.")

# ============================ GATHERING SKILLS (split = self-supply vs marginal/no GE buy-in) ============================
# Mining / Fishing / Woodcutting: gathering skills. Mains and irons both gather XP the same way;
# the split is marginal (mains may BUY stamina/teleports/gear, but XP itself is gathered).
# Included to show the gather-time basis is identical, with the contrast called out in notes.
add("Mining", "main",
    "Mine ore directly (iron ore powermining, 3-tick granite, Motherlode Mine, Volcanic Mine)",
    "gather", None, False, "main",
    "Mining is a gathering skill: XP is gathered, not bought, for BOTH families. The only main/iron split is incidental GE spend on stamina potions, teleports and pickaxe/gear upgrades; no buyable-XP route exists. cost_basis = gather for both. Included to show no meaningful gp_per_xp route.")
add("Mining", "ironman",
    "Mine ore directly (iron ore, 3-tick granite, sandstone, Motherlode Mine, Volcanic Mine)",
    "gather", None, False, "ironman",
    "Identical gather route to mains. Irons additionally rely on Mining as the upstream supply for Smithing/Crafting. Cost is gather-time.")

add("Fishing", "main",
    "Fish directly (fly fishing, Barbarian Fishing, Tempoross, 2-tick swordfish/tuna, minnows)",
    "gather", None, False, "main",
    "Fishing is a gathering skill: XP gathered, not bought, for BOTH families. Marginal main/iron split is only stamina/teleport/gear GE spend; no buyable-XP route. cost_basis = gather for both.")
add("Fishing", "ironman",
    "Fish directly (fly fishing 20-58, Barbarian Fishing 58-99, Tempoross, karambwans, minnows)",
    "gather", None, False, "ironman",
    "Identical gather route to mains; also the upstream supply for Cooking. Cost is gather-time.")

add("Woodcutting", "main",
    "Chop trees directly (regular -> teak; Wintertodt 50-60 for supplies; Forestry events)",
    "gather", None, False, "main",
    "Woodcutting is a gathering skill: XP gathered, not bought, for BOTH families. Marginal main/iron split is only axe/log-basket/Lumberjack-outfit GE spend; no buyable-XP route. cost_basis = gather for both.")
add("Woodcutting", "ironman",
    "Chop trees directly (regular up to ~50, Wintertodt 50-60, teak 35-99); upstream supply for Construction/Firemaking/Fletching",
    "gather", None, False, "ironman",
    "Identical gather route to mains; also the upstream supply for Firemaking/Fletching/Construction. Cost is gather-time.")

# ============================ RUNECRAFT (split: buyable shortcut vs pure gather) ============================
add("Runecraft", "main",
    "Guardians of the Rift, or craft runes from bought pure/daeyalt essence (lavas, bloods/souls); buy essence on the GE",
    "gp_per_xp", None, True, "main",
    "Mains can buy pure essence (and historically daeyalt) on the GE to power runecrafting (lava runes 23-99, blood/soul 77-99). Essence cost per xp is low but nonzero; left null due to method variance. GotR is the standard route for both families.")
add("Runecraft", "ironman",
    "Gather essence yourself (mine pure essence, daeyalt) and craft; Guardians of the Rift; Arceuus blood/soul runes",
    "gather", None, False, "ironman",
    "Wiki: 'Acquiring essence' is the iron gating step - mine your own pure/daeyalt essence. GotR 10-99 needs no pre-bought essence and is HCIM-friendly. Cost is essence gather-time, not GE essence spend.")

R_OUT = R

# ---------------- EXCLUDED ----------------
EXCLUDED = [
    {"skill": "Agility", "reason": "No meaningful main-vs-iron cost split: Agility is trained the same way (rooftop courses, Hallowed Sepulchre, Brimhaven) for all account families; XP is neither bought (gp_per_xp) nor materially gathered. No GP/XP route exists for mains.", "account_families": ["main", "ironman"]},
    {"skill": "Thieving", "reason": "No meaningful main-vs-iron cost split: pickpocketing/stalls (blackjacking, artefacts) is identical for all families; no consumables bought per xp and nothing gathered. Thieving is itself a supply method (coins/seeds) rather than a cost-split skill.", "account_families": ["main", "ironman"]},
    {"skill": "Hunter", "reason": "No meaningful main-vs-iron cost split: birdhouses, Hunters' Rumours, chinchompas, herbiboar are trapped the same way for all families; XP is gathered, not bought. (Hunter is the upstream supply for iron Ranged chinchompas, noted under Ranged.)", "account_families": ["main", "ironman"]},
    {"skill": "Slayer", "reason": "No meaningful gp_per_xp-vs-gather split: Slayer XP is earned by killing assigned monsters for all families. Mains may spend on supplies/gear but there is no buy-XP route; the iron difference is self-supplied gear/consumables, not a per-xp cost basis.", "account_families": ["main", "ironman"]},
    {"skill": "Attack/Strength/Defence/Hitpoints (Melee)", "reason": "Combat XP is earned by fighting; no gp_per_xp-vs-gather cost split. Main/iron difference is gear/consumable sourcing, not a per-xp training cost. (NMZ/quests common to both.)", "account_families": ["main", "ironman"]},
]

# ---------------- ENVELOPE ----------------
PTP_URLS = {
    "Prayer": "https://oldschool.runescape.wiki/w/Pay-to-play_Prayer_training",
    "Construction": "https://oldschool.runescape.wiki/w/Construction_training",
    "Herblore": "https://oldschool.runescape.wiki/w/Herblore_training",
    "Farming": "https://oldschool.runescape.wiki/w/Farming_training",
    "Cooking": "https://oldschool.runescape.wiki/w/Pay-to-play_Cooking_training",
    "Crafting": "https://oldschool.runescape.wiki/w/Pay-to-play_Crafting_training",
    "Smithing": "https://oldschool.runescape.wiki/w/Pay-to-play_Smithing_training",
    "Magic": "https://oldschool.runescape.wiki/w/Pay-to-play_Magic_training",
    "Ranged": "https://oldschool.runescape.wiki/w/Pay-to-play_Ranged_training",
    "Fletching": "https://oldschool.runescape.wiki/w/Fletching_training",
    "Firemaking": "https://oldschool.runescape.wiki/w/Pay-to-play_Firemaking_training",
    "Mining": "https://oldschool.runescape.wiki/w/Pay-to-play_Mining_training",
    "Fishing": "https://oldschool.runescape.wiki/w/Pay-to-play_Fishing_training",
    "Woodcutting": "https://oldschool.runescape.wiki/w/Pay-to-play_Woodcutting_training",
    "Runecraft": "https://oldschool.runescape.wiki/w/Pay-to-play_Runecraft_training",
}
IRON_URLS = {s: f"https://oldschool.runescape.wiki/w/Ironman_Guide/{s}" for s in
             ["Prayer","Construction","Herblore","Farming","Cooking","Crafting","Smithing",
              "Magic","Ranged","Fletching","Firemaking","Mining","Fishing","Woodcutting","Runecraft"]}

source_urls = sorted(set(PTP_URLS.values()) | set(IRON_URLS.values()))

skills_covered = sorted({r["skill"] for r in R_OUT})

raw_files = ["data/raw/account_cost_split/ptp_%s.wikitext" % s for s in
             ["Prayer","Construction","Herblore","Farming","Cooking","Crafting","Smithing","Magic",
              "Ranged","Fletching","Firemaking","Mining","Fishing","Woodcutting","Runecraft",
              "Agility","Thieving","Hunter"]]
raw_files += ["data/raw/account_cost_split/iron_%s.wikitext" % s for s in
              ["Prayer","Construction","Herblore","Farming","Cooking","Crafting","Smithing","Magic",
               "Ranged","Fletching","Firemaking","Mining","Fishing","Woodcutting","Runecraft",
               "Agility","Thieving","Hunter","Slayer"]]

# domain stats
from collections import Counter
by_family = Counter(r["account_family"] for r in R_OUT)
by_basis = Counter(r["cost_basis"] for r in R_OUT)
with_value = sum(1 for r in R_OUT if r["value"] is not None)

envelope = {
    "_provenance": {
        "domain": "account_cost_split",
        "source_urls": source_urls,
        "source_query": None,
        "accessed": ACCESSED,
        "license": "CC BY-NC-SA 3.0",
        "extraction_method": "agent",
        "raw_files": raw_files,
        "record_count": len(R_OUT),
        "completeness": {
            "bounded_by": "OSRS skills where the main(GP/XP)-vs-ironman(gather) cost split is meaningful (the buyable + gathering skills)",
            "universe_count": 15,
            "records_count": len(R_OUT),
            "known_missing": [
                "Agility, Thieving, Hunter, Slayer, and the Melee combat skills (Attack/Strength/Defence/Hitpoints) are intentionally NOT given paired records: they have no gp_per_xp-vs-gather split (see _excluded).",
                "Mining/Fishing/Woodcutting are included as gather=gather for BOTH families (no buyable-XP route); they are inside the 15-skill universe but their split is marginal (only incidental gear/teleport GE spend), as noted per record.",
                "Per-method gp/xp values are NOT exhaustively rendered: only headline buyable methods carry a snapshot 'value' (Prayer, Construction, Herblore, Crafting, Magic). Others use honest nulls because the wiki computes per-product gp/xp from live GE prices across many sub-methods.",
                "Snapshot gp/xp values are price-volatile (basis recorded per value); they will drift as GE prices change."
            ],
        },
        "domain_stats": {
            "skills_covered": skills_covered,
            "skills_covered_count": len(skills_covered),
            "records_by_account_family": dict(by_family),
            "records_by_cost_basis": dict(by_basis),
            "records_with_snapshot_value": with_value,
            "ptp_pages_used": PTP_URLS,
            "iron_pages_used": IRON_URLS,
        },
    },
    "records": R_OUT,
    "_excluded": EXCLUDED,
}

OUT = "/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/data/account_cost_split.json"
with open(OUT, "w") as f:
    json.dump(envelope, f, indent=2, ensure_ascii=False)

print("WROTE", OUT)
print("record_count:", len(R_OUT))
print("universe_count:", envelope["_provenance"]["completeness"]["universe_count"])
print("known_missing_count:", len(envelope["_provenance"]["completeness"]["known_missing"]))
print("skills_covered:", skills_covered)
print("by_family:", dict(by_family), "by_basis:", dict(by_basis), "with_value:", with_value)
print("excluded:", len(EXCLUDED))
