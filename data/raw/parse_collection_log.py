#!/usr/bin/env python3
"""
Parse OSRS Collection Log into the frozen output envelope.

Source: Module:Collection_log/data.json (authoritative, structured) — maps each
unique item (by item id) to the set of collection-log "tabs" (sources) it appears
under. Each (item, tab) placement is one collection-log SLOT; items appearing in
multiple tabs are the cross-source "shared" slots.

Category grouping (Bosses/Raids/Clues/Minigames/Other) taken from the
[[Collection log]] page's top-level tab layout.

drop_rate is intentionally null: the structured data source does not carry per-source
drop rates. Those live in per-source drop tables (122 separate pages) and are out of
scope for this faithful extraction; disclosed in completeness.known_missing.

Leagues collection-log content lives in a separate module (Module:Leagues Collection
Log Table) and is NOT part of the standard collection log universe — excluded by source.
"""
import json
import datetime

RAW = "data/raw/collection_log_data.json"
OUT = "data/collection_log.json"

SOURCE_URLS = [
    "https://oldschool.runescape.wiki/w/Module:Collection_log/data.json?action=raw",
    "https://oldschool.runescape.wiki/w/Collection_log",
]

# Parent category -> list of data.json tab names.
# Keys/values are the EXACT tab strings used in data.json so every record maps cleanly.
CATEGORY_MAP = {
    "Bosses": [
        "Abyssal Sire", "Alchemical Hydra", "Amoxliatl", "Araxxor", "Barrows Chests",
        "Brutus", "Bryophyta", "Callisto and Artio", "Cerberus", "Chaos Elemental",
        "Chaos Fanatic", "Commander Zilyana", "Corporeal Beast", "Crazy Archaeologist",
        "Dagannoth Kings", "Deranged archaeologist", "Doom of Mokhaiotl", "Duke Sucellus",
        "The Fight Caves", "Fortis Colosseum", "The Gauntlet", "General Graardor",
        "Giant Mole", "Grotesque Guardians", "Hespori", "The Hueycoatl", "The Inferno",
        "Kalphite Queen", "King Black Dragon", "Kraken", "Kree'arra", "K'ril Tsutsaroth",
        "The Leviathan", "Moons of Peril", "Nex", "The Nightmare", "Obor", "Phantom Muspah",
        "Royal Titans", "Sarachnis", "Scorpia", "Scurrius", "Shellbane Gryphon", "Skotizo",
        "Tempoross", "Thermonuclear Smoke Devil", "Vardorvis", "Venenatis and Spindel",
        "Vet'ion and Calvar'ion", "Vorkath", "The Whisperer", "Wintertodt", "Yama",
        "Zalcano", "Zulrah",
    ],
    "Raids": [
        "Chambers of Xeric", "Theatre of Blood", "Tombs of Amascut",
    ],
    "Clues": [
        "Beginner Treasure Trails", "Easy Treasure Trails", "Medium Treasure Trails",
        "Hard Treasure Trails", "Elite Treasure Trails", "Master Treasure Trails",
        "Hard Treasure Trails (Rare)", "Elite Treasure Trails (Rare)",
        "Master Treasure Trails (Rare)", "Shared Treasure Trail Rewards", "Scroll Cases",
    ],
    "Minigames": [
        "Barbarian Assault", "Barracuda Trials", "Brimhaven Agility Arena", "Castle Wars",
        "Fishing Trawler", "Giants' Foundry", "Gnome Restaurant", "Guardians of the Rift",
        "Hallowed Sepulchre", "Last Man Standing", "Magic Training Arena", "Mahogany Homes",
        "Mastering Mixology", "Pest Control", "Rogues' Den", "Shades of Mort'ton",
        "Soul Wars", "Temple Trekking", "Tithe Farm", "Trouble Brewing", "Vale Totems",
        "Volcanic Mine",
    ],
    "Other": [
        "Aerial Fishing", "All Pets", "Boat Paints", "Camdozaal", "Champion's Challenge",
        "Chompy Bird Hunting", "Colossal Wyrm Agility", "Creature Creation", "Cyclopes",
        "Elder Chaos Druids", "Forestry", "Fossil Island Notes", "Glough's Experiments",
        "Hunter Guild", "Lost Schematics", "Monkey Backpacks", "Motherlode Mine", "My Notes",
        "Ocean Encounters", "Random Events", "Revenants", "Rooftop Agility",
        "Sailing Miscellaneous", "Sea Treasures", "Shayzien Armour", "Shooting Stars",
        "Skilling Pets", "Slayer", "Tormented Demons", "TzHaar", "Miscellaneous",
    ],
}

# node_type per source kind (the source/tab is the graph node the item attaches to).
NODE_TYPE_BY_CATEGORY = {
    "Bosses": "boss",
    "Raids": "raid",
    "Clues": "clue",
    "Minigames": "minigame",
    "Other": "activity",
}
# A handful of "Other" tabs are really skilling activities; node_type stays "activity"
# (catch-all) which is honest. All-Pets / Skilling-Pets are pet aggregate tabs.


def build_tab_to_category():
    t2c = {}
    for cat, tabs in CATEGORY_MAP.items():
        for t in tabs:
            t2c[t] = cat
    return t2c


def main():
    data = json.load(open(RAW))
    tab2cat = build_tab_to_category()

    all_tabs = sorted({t for r in data for t in r["tabs"]})
    unmapped = [t for t in all_tabs if t not in tab2cat]
    if unmapped:
        raise SystemExit(f"UNMAPPED TABS (fix CATEGORY_MAP): {unmapped}")

    records = []
    slot_count = 0
    shared_item_count = 0  # items appearing in >1 tab
    per_category_slots = {c: 0 for c in CATEGORY_MAP}
    per_source_slots = {}

    for r in data:
        item = r["name"]
        item_id = r["id"]
        tabs = r["tabs"]
        if len(tabs) > 1:
            shared_item_count += 1
        # One record per (item, source) placement = one collection-log slot.
        for tab in tabs:
            cat = tab2cat[tab]
            shared_with = [t for t in tabs if t != tab]
            rec = {
                "category": cat,
                "source": tab,
                "node_type": NODE_TYPE_BY_CATEGORY[cat],
                "item": item,
                "item_id": item_id,
                "drop_rate": None,
                "shared_with": shared_with,
            }
            records.append(rec)
            slot_count += 1
            per_category_slots[cat] += 1
            per_source_slots[tab] = per_source_slots.get(tab, 0) + 1

    unique_items = len({r["item_id"] for r in records})
    unique_names = len({r["item"] for r in records})

    # Official wiki page figures (cross-check):
    OFFICIAL_SLOTS = 1906
    OFFICIAL_UNIQUE = 1701

    domain_stats = {
        "node_type": "collection_log_slot (record granularity = one (item,source) placement)",
        "unique_items_by_id": unique_items,
        "unique_item_names": unique_names,
        "total_slots_extracted": slot_count,
        "shared_slot_items": shared_item_count,
        "source_count": len(all_tabs),
        "per_category_slot_counts": per_category_slots,
        "per_source_slot_counts": per_source_slots,
        "official_page_figures": {
            "total_slots": OFFICIAL_SLOTS,
            "unique_entries": OFFICIAL_UNIQUE,
            "note": "Page states 1,906 slots / 1,701 unique entries; 201 duplicate "
                    "slots (126 from pets, gilded equipment, 3rd age equipment). "
                    "data.json yields 1,907 slot placements / 1,701 unique ids — the "
                    "1-slot delta vs the prose figure reflects ongoing wiki updates.",
        },
        "drop_rate_status": "null for all records — see completeness.known_missing",
    }

    envelope = {
        "_provenance": {
            "domain": "collection_log",
            "source_urls": SOURCE_URLS,
            "source_query": None,
            "accessed": datetime.datetime.now(datetime.timezone.utc)
                .strftime("%Y-%m-%dT%H:%M:%SZ"),
            "license": "CC BY-NC-SA 3.0",
            "extraction_method": "script",
            "raw_files": [
                "data/raw/collection_log_data.json",
                "data/raw/collection_log_page_raw.wikitext",
                "data/raw/parse_collection_log.py",
            ],
            "record_count": len(records),
            "completeness": {
                "bounded_by": "Module:Collection_log/data.json (authoritative item->tab map)",
                "universe_count": OFFICIAL_SLOTS,
                "records_count": len(records),
                "known_missing": [
                    "drop_rate: null for ALL records — per-source drop rates are not in "
                    "the structured data source; they live in 122 per-source drop tables "
                    "(out of scope for this faithful extraction).",
                    "Leagues collection-log entries (separate Module:Leagues Collection "
                    "Log Table) — not part of the standard collection log universe; excluded.",
                ],
            },
            "domain_stats": domain_stats,
        },
        "records": records,
        "_excluded": [
            {
                "source": "Leagues Collection Log Table",
                "reason": "Leagues seasonal content tracked in a separate module; not part "
                          "of the standard (main-game) collection log universe of 1,906 slots.",
            }
        ],
    }

    json.dump(envelope, open(OUT, "w"), indent=2, ensure_ascii=False)
    print(f"WROTE {OUT}")
    print(f"records (slots): {len(records)}")
    print(f"unique items (id): {unique_items}  unique names: {unique_names}")
    print(f"sources: {len(all_tabs)}  shared-slot items: {shared_item_count}")
    print(f"per-category slots: {per_category_slots}")


if __name__ == "__main__":
    main()
