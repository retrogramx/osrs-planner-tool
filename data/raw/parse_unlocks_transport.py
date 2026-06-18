#!/usr/bin/env python3
"""Parse OSRS Wiki transportation/unlock data into the frozen domain envelope.

Domain: unlocks_transport
Source: OSRS Wiki (oldschool.runescape.wiki) ?action=raw wikitext for
  - Transportation (master index)
  - Fairy rings (per-node code table)
  - Spirit tree (per-node locations)
  - Gnome glider (per-node locations)

Each record: { unlock, type: transport|area|feature,
               requirements{quests,skills,items}, notes }

Fairy-ring node requirements are parsed deterministically from the POI cell text
(quest links + "Requires ... [[Quest]]", Agility level, visited-area gating).
System/feature/spell records are hand-encoded faithfully from the source pages
(no fact paraphrasing; notes quote the source intent).
"""
import json
import re
import datetime

RAW = "/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/data/raw"
OUT = "/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/data/unlocks_transport.json"

ACCESSED = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

SOURCE_URLS = [
    "https://oldschool.runescape.wiki/w/Transportation?action=raw",
    "https://oldschool.runescape.wiki/w/Fairy_rings?action=raw",
    "https://oldschool.runescape.wiki/w/Spirit_tree?action=raw",
    "https://oldschool.runescape.wiki/w/Gnome_glider?action=raw",
]
RAW_FILES = [
    "data/raw/transportation_raw.wikitext",
    "data/raw/Fairy_rings_raw.wikitext",
    "data/raw/Spirit_tree_raw.wikitext",
    "data/raw/Gnome_glider_raw.wikitext",
]


def strip_links(text):
    """Convert [[Page|label]] / [[Page]] to label/Page; drop simple templates."""
    # piped links -> label
    text = re.sub(r"\[\[[^\]|]+\|([^\]]+)\]\]", r"\1", text)
    # plain links -> page
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    # {{plink|X}} / {{plinkp|X}} -> X (first arg)
    text = re.sub(r"\{\{plinkp?\|([^}|]+)[^}]*\}\}", r"\1", text)
    # remove remaining templates
    text = re.sub(r"\{\{[^}]*\}\}", "", text)
    text = text.replace("'''", "").replace("''", "")
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_quests(raw_cell):
    """Return list of quest names referenced in a POI/notes cell.

    Heuristic: capture [[Quest]] links that are followed by the word 'quest',
    'miniquest', or appear in a 'Requires ... completion of [[X]]' clause, and
    explicit known-quest patterns. We keep this conservative to avoid pulling in
    location links.
    """
    quests = []
    # Drop "during (and after) the [[X]] quest" USAGE clauses: these mean the ring
    # is used in a quest sequence, not that the quest gates normal access to it.
    cleaned = re.sub(
        r"during(?: and after)? the \[\[[^\]]+\]\]\s*\[\[(?:quest|Quests|miniquest)[^\]]*\]\]",
        " ",
        raw_cell,
    )
    cleaned = re.sub(r"used during the \[\[[^\]]+\]\]\s*\[\[(?:quest|Quests|miniquest)[^\]]*\]\]", " ", cleaned)
    # Special: "Unlocked by entering ... in the beginning of [[Quest]]" -> the quest
    # is the link AFTER 'beginning of', not the location after 'entering'.
    for m in re.finditer(r"beginning of\s+(?:the\s+)?\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", cleaned):
        quests.append(m.group(1))
    cleaned = re.sub(r"Unlocked by entering[^.]*?beginning of[^.]*\.", " ", cleaned)
    # Pattern: completion / partial completion / completed ... of [[Quest]]  (case-insensitive anchor)
    for m in re.finditer(
        r"(?i:completion of|partial completion of|completed)\s+(?:the\s+)?\[\[([^\]|]+)(?:\|[^\]]+)?\]\]",
        cleaned,
    ):
        quests.append(m.group(1))
    # Pattern: [[Quest]] must be completed / is required (quest named BEFORE the clause)
    for m in re.finditer(
        r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]\s*(?:\[\[(?:quest|Quests|miniquest)[^\]]*\]\]\s*)?(?:must be completed|is required)",
        cleaned,
    ):
        quests.append(m.group(1))
    # Pattern: [[Quest]] [[quest]]  (link immediately followed by the word quest/miniquest)
    for m in re.finditer(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]\s*\[\[(?:quest|Quests|miniquest)", cleaned):
        quests.append(m.group(1))
    # dedupe preserving order
    seen = set()
    out = []
    for q in quests:
        q = q.strip()
        if q and q not in seen and q.lower() not in ("quest", "quests", "miniquest"):
            seen.add(q)
            out.append(q)
    return out


def extract_agility(raw_cell):
    """Return Agility level int only when it gates using/exiting the ring itself.

    The fairy-ring tables mention Agility in two senses: (a) a level needed to
    leave/exit the ring's island/area to make the destination usable
    ("needed to jump off the island", "required to exit the agility course"),
    which is a real ring requirement; and (b) a downstream shortcut beyond the
    ring ("shortcut to enter Mort Myre, requiring level 50 Agility"), which is a
    POI note, not a requirement. We only return (a).
    """
    for m in re.finditer(r"(\d+)\s*\[\[Agility\]\]", raw_cell):
        level = int(m.group(1))
        ctx = raw_cell[max(0, m.start() - 120): m.end() + 120].lower()
        if any(k in ctx for k in ("jump off", "to exit", "required to exit", "to leave", "off the island")):
            return level
    # also handle "Agility is needed to jump off" worded before the number
    m = re.search(r"(\d+)\s*\[\[Agility\]\] is needed to jump off", raw_cell)
    if m:
        return int(m.group(1))
    return None


# ---------------------------------------------------------------------------
# Fairy rings
# ---------------------------------------------------------------------------
def parse_fairy_rings():
    with open(f"{RAW}/Fairy_rings_raw.wikitext", encoding="utf-8") as f:
        wt = f.read()

    records = []
    # Each node row begins "|{{Fairycode|XXX}}" and has a Location and POI cell.
    # Rows are delimited by "|-" within the combination tables.
    # We split on Fairycode occurrences within rows that also contain a Location.
    # Simpler: iterate over rows split by "\n|-" markers across the whole file,
    # keep those that contain a {{Fairycode|...}} as the first data cell.
    rows = re.split(r"\n\|-", wt)
    for row in rows:
        codes = re.findall(r"\{\{Fairycode\|([A-Z]{3})\}\}", row)
        if not codes:
            continue
        # Skip the 'Sequences' aggregate row (multiple codes, hideout)
        if len(codes) > 1:
            continue
        code = codes[0]
        # Cells separated by lines starting with '|' (not '|-')
        # Pull location and POI: the table has columns Code|Map|Location|POI.
        # Find the Location line (first link after the Map cell) and POI text.
        # Split row into pipe-cells on newlines beginning with '|'
        cells = re.split(r"\n\s*\|", row)
        # cells[0] holds the Fairycode (after the leading '|' was consumed by split on \n|-)
        # Identify Map cell (contains {{Map) and skip; Location is next; POI follows.
        # Build a flat list of cell texts after removing the code/map cells.
        data_cells = []
        for c in cells:
            c = c.strip()
            if not c:
                continue
            data_cells.append(c)
        # data_cells[0] -> code, find map index
        loc = None
        poi_parts = []
        # Heuristic: location cell is the first data cell after a Map cell that is
        # a location link and not a map/code. POI = remaining.
        # Find index of map cell
        idx_after_map = None
        for i, c in enumerate(data_cells):
            if "{{Map" in c or "{{Fairycode" in c or c.endswith(".png]]") or "[[file:" in c.lower():
                idx_after_map = i
        if idx_after_map is None:
            continue
        rest = data_cells[idx_after_map + 1 :]
        if not rest:
            continue
        loc_raw = rest[0]
        loc = strip_links(loc_raw)
        poi_raw = "\n".join(rest[1:])
        poi = strip_links(poi_raw)

        # Requirements from BOTH location-cell and POI-cell raw text
        req_source = loc_raw + "\n" + poi_raw
        quests = extract_quests(req_source)
        agility = extract_agility(req_source)
        skills = {}
        if agility is not None:
            skills["Agility"] = agility

        items = []
        # Greegree gating for Ape Atoll (CLR)
        if "greegree" in req_source.lower():
            items.append("Ninja monkey greegree or Kruk monkey greegree")

        # Visited-area gating (Kourend / Great Conch / Grimstone) -> note, not quest
        visited_note = None
        mv = re.search(r"must have visited \[\[([^\]|]+)", req_source)
        if mv:
            visited_note = f"Requires having visited {strip_links('[[' + mv.group(1) + ']]')} at least once."
        elif "available once Grimstone has been visited" in poi_raw:
            visited_note = "Requires having visited Grimstone at least once."

        notes_bits = []
        if visited_note:
            notes_bits.append(visited_note)
        if poi:
            notes_bits.append("Points of interest / access notes: " + poi)
        notes = " ".join(notes_bits) if notes_bits else None

        records.append(
            {
                "unlock": f"Fairy ring {code} ({loc})",
                "type": "transport",
                "requirements": {
                    "quests": quests,
                    "skills": skills,
                    "items": items,
                },
                "notes": notes,
                "domain_group": "fairy_ring_node",
                "code": code,
            }
        )
    return records


# ---------------------------------------------------------------------------
# Spirit tree locations
# ---------------------------------------------------------------------------
def parse_spirit_trees():
    with open(f"{RAW}/Spirit_tree_raw.wikitext", encoding="utf-8") as f:
        wt = f.read()
    records = []
    # Permanent locations are a bulleted list under "Permanent locations:".
    seg = wt.split("Permanent locations:", 1)[1].split("Self-grown spirit tree locations", 1)[0]
    for line in seg.splitlines():
        line = line.strip()
        if not line.startswith("*"):
            continue
        bullet = line.lstrip("* ").strip()
        # remove trailing {{Map ...}}
        bullet_raw = re.sub(r"\{\{Map[^}]*\}\}", "", bullet).strip()
        label = strip_links(bullet_raw)
        if not label:
            continue
        quests = extract_quests(bullet_raw)
        skills = {}
        ms = re.search(r"(\d+)\s*\[\[Sailing\]\]", bullet_raw)
        if ms:
            skills["Sailing"] = int(ms.group(1))
        notes = label
        records.append(
            {
                "unlock": "Spirit tree: " + re.split(r"\(", label)[0].strip(),
                "type": "transport",
                "requirements": {"quests": quests, "skills": skills, "items": []},
                "notes": notes,
                "domain_group": "spirit_tree_node",
            }
        )
    return records


# ---------------------------------------------------------------------------
# Gnome glider locations
# ---------------------------------------------------------------------------
def parse_gnome_gliders():
    with open(f"{RAW}/Gnome_glider_raw.wikitext", encoding="utf-8") as f:
        wt = f.read()
    records = []
    seg = wt.split("Gnome gliders are located at:", 1)[1].split("==Efficient travel==", 1)[0]
    cur = None
    for line in seg.splitlines():
        s = line.strip()
        if s.startswith("* '''"):
            # top-level glider node
            name = re.search(r"\*\s*'''([^']+)'''", s)
            desc = strip_links(s)
            cur = {
                "unlock": "Gnome glider: " + (name.group(1).strip() if name else desc),
                "type": "transport",
                "requirements": {"quests": ["The Grand Tree"], "skills": {}, "items": []},
                "notes": desc,
                "domain_group": "gnome_glider_node",
            }
            records.append(cur)
        elif s.startswith("**") and cur is not None:
            sub = strip_links(s)
            q = extract_quests(s)
            for qq in q:
                if qq not in cur["requirements"]["quests"]:
                    cur["requirements"]["quests"].append(qq)
            if "kudos" in s:
                cur["notes"] += " | Note: " + sub
            elif sub:
                cur["notes"] += " | " + sub
    return records


# ---------------------------------------------------------------------------
# Hand-encoded system / feature / spell records (faithful to source pages)
# ---------------------------------------------------------------------------
def manual_records():
    R = []

    def rec(unlock, typ, quests=None, skills=None, items=None, notes=None, group="system"):
        return {
            "unlock": unlock,
            "type": typ,
            "requirements": {
                "quests": quests or [],
                "skills": skills or {},
                "items": items or [],
            },
            "notes": notes,
            "domain_group": group,
        }

    # --- Transportation SYSTEMS (network-level unlocks) ---
    R.append(rec(
        "Fairy ring network",
        "transport",
        quests=["Fairytale I - Growing Pains", "Fairytale II - Cure a Queen"],
        items=["Dramen staff or lunar staff (to use rings; not needed with Elite Lumbridge & Draynor Diary)"],
        notes="Members. Network of 55 fairy rings. Fairytale I - Growing Pains MUST be completed; Fairytale II - Cure a Queen need only be STARTED (permission from the Fairy Godfather) to access the network - it does not need to be completed, and no skill requirements are needed. A dramen staff or lunar staff is required to enter a ring unless the Elite Lumbridge & Draynor Diary is completed.",
    ))
    R.append(rec(
        "Spirit tree network",
        "transport",
        quests=["Tree Gnome Village"],
        notes="Members. Completion of Tree Gnome Village is required for access to the network. Additional completion of The Grand Tree is required to travel FROM the Tree Gnome Stronghold tree (not required to travel TO it). Several specific trees require further quests/skills (see spirit_tree_node records).",
    ))
    R.append(rec(
        "Gnome glider network",
        "transport",
        quests=["The Grand Tree"],
        notes="Members. Gnome gliders are available after completing The Grand Tree. Can be combined with teleport spells, spirit trees and the fairy ring network. Some individual gliders need further quests (see gnome_glider_node records).",
    ))
    R.append(rec(
        "Wilderness Obelisks",
        "transport",
        notes="Six Wilderness Obelisks teleport anyone standing on the pad to a randomly chosen obelisk; completing the Hard Wilderness Diary allows choosing the arrival point. An obelisk can also be built in a player-owned house but cannot be used to teleport out of the Wilderness. WILDERNESS / risk flag: located in the Wilderness.",
    ))
    R.append(rec(
        "Lovakengj Minecart Network",
        "transport",
        items=["20 coins per ride (waived permanently after The Forsaken Tower)"],
        notes="Members. Rapid transit serving twelve destinations across Kourend and Kebos. 20 coins per ride; the fee is waived permanently upon completion of The Forsaken Tower (which is then a free, iron-realizable convenience - the coin cost is a sink, not income).",
    ))
    R.append(rec(
        "Quetzal Transport System",
        "transport",
        quests=["Twilight's Promise"],
        notes="Members. Transportation within Varlamore. During Twilight's Promise players are gifted their own quetzal, Renu. Eight landing sites available after Twilight's Promise plus six more that can be built.",
    ))
    R.append(rec(
        "Mycelium Transportation System",
        "transport",
        notes="Members. System of Magic Mushtrees allowing transport around Fossil Island (four mushtrees: House on the Hill, Verdant Valley, Sticky Swamp, Mushroom Meadow). Fossil Island access is gained via Bone Voyage.",
    ))
    R.append(rec(
        "Keldagrim minecart system",
        "transport",
        notes="Members. Listed under Other Transportation Systems on the Transportation page.",
    ))
    R.append(rec(
        "Magic carpet network (Kharidian Desert)",
        "transport",
        notes="Members. Magic carpets in the Kharidian Desert. Listed under Other Transportation Systems.",
    ))
    R.append(rec(
        "Eagle transport system",
        "transport",
        quests=["Eagles' Peak"],
        notes="Members. Eagle transport system; unlocked via the Eagles' Peak quest (per Eagle transport system page / Transportation listing).",
    ))
    R.append(rec(
        "Balloon transport system (hot air balloon)",
        "transport",
        quests=["Enlightened Journey"],
        skills={"Firemaking": 20},
        items=["One log of the appropriate type per flight"],
        notes="Members. Hot air balloon transport requires completion of Enlightened Journey; individual destinations unlock as the quest/related steps are done and require logs to fly.",
    ))
    R.append(rec(
        "Charter ships",
        "transport",
        items=["Coins (fare varies by route)"],
        notes="Members. Charter ship network between many ports; fares paid in coins (iron-realizable sink).",
    ))
    R.append(rec(
        "Canoe system",
        "transport",
        skills={"Woodcutting": 12},
        items=["Axe"],
        notes="Canoes (River Lum). Higher Woodcutting allows larger canoes reaching farther destinations; the Waka canoe can reach the Wilderness pond (destination only). Available in free-to-play and members.",
    ))

    # --- Teleport spellbooks (unlock = ability to cast that book's teleports) ---
    R.append(rec(
        "Ancient Magicks spellbook (teleports)",
        "feature",
        quests=["Desert Treasure I"],
        notes="Members. Players must have completed Desert Treasure I to use Ancient Magicks. Unlocks Paddewwa, Senntisten, Kharyrll, Lassar, Dareeyak, Carrallanger, Annakarl and Ghorrock teleports (several land in the Wilderness - risk flag).",
    ))
    R.append(rec(
        "Lunar spellbook (teleports)",
        "feature",
        quests=["Lunar Diplomacy"],
        notes="Members. Players must have completed Lunar Diplomacy to use Lunar spells. Ourania Teleport additionally requires speaking to Baba Yaga to unlock.",
    ))
    R.append(rec(
        "Arceuus spellbook (teleports)",
        "feature",
        quests=["Client of Kourend"],
        notes="Members. The Arceuus spellbook is unlocked via Client of Kourend (Tower of Magincta). Individual teleports have further gates: West Ardougne Teleport requires Biohazard; Harmony Island Teleport requires The Great Brain Robbery.",
    ))

    # --- Notable spell-level teleports with explicit quest gates (from tables) ---
    R.append(rec(
        "Camelot Teleport (standard)",
        "feature",
        skills={"Magic": 45},
        notes="Members. Teleports south of Camelot castle, or to Seers' Village bank upon completion of the Hard Kandarin Diary.",
    ))
    R.append(rec(
        "Kourend Castle Teleport (standard)",
        "feature",
        quests=["Client of Kourend"],
        skills={"Magic": 48},
        notes="Members. Requires completion of Client of Kourend. Teleports to Kourend Castle courtyard.",
    ))
    R.append(rec(
        "Ardougne Teleport (standard)",
        "feature",
        quests=["Plague City"],
        skills={"Magic": 51},
        notes="Members. Requires completion of Plague City. Teleports to centre of Ardougne.",
    ))
    R.append(rec(
        "Watchtower Teleport (standard)",
        "feature",
        quests=["Watchtower"],
        skills={"Magic": 58},
        notes="Members. Requires completion of Watchtower. Teleports to the Watchtower near Yanille.",
    ))
    R.append(rec(
        "Varrock Teleport (standard)",
        "feature",
        skills={"Magic": 25},
        notes="Free-to-play. Teleports to centre of Varrock, or Grand Exchange upon completion of the Medium Varrock Diary.",
    ))

    # --- Quest-related teleport items (require the named quest to obtain) ---
    R.append(rec(
        "Ectophial (teleport to Ectofuntus)",
        "feature",
        quests=["Ghosts Ahoy"],
        notes="Members. Obtained during Ghosts Ahoy. Unlimited teleport to the Ectofuntus; automatically refilled on arrival.",
    ))
    R.append(rec(
        "Royal seed pod (teleport to Grand Tree)",
        "feature",
        quests=["Monkey Madness II"],
        notes="Members. Obtained from Monkey Madness II. Unlimited teleport to the Grand Tree.",
    ))
    R.append(rec(
        "Drakan's medallion (Morytania teleports)",
        "feature",
        quests=["A Taste of Hope"],
        notes="Members. Obtained during A Taste of Hope. Unlimited teleports to Ver Sinhaza and Darkmeyer; a Slepey tablet unlocks an unlimited teleport to the Sisterhood Sanctuary.",
    ))
    R.append(rec(
        "Kharedst's memoirs (Kourend teleports)",
        "feature",
        quests=["X Marks the Spot", "The Queen of Thieves", "The Depths of Despair", "Tale of the Righteous", "The Forsaken Tower", "A Kingdom Divided"],
        notes="Members. Book teleports to Great Kourend cities; each city page is added by completing the associated Kourend quest. Recharged by inspecting the Old Memorial with law/body/mind/soul runes.",
    ))
    R.append(rec(
        "Mythical cape (teleport to Myths' Guild)",
        "feature",
        quests=["Dragon Slayer II"],
        notes="Members. Obtained from the Myths' Guild after Dragon Slayer II. Unlimited teleport to the Myths' Guild.",
    ))
    R.append(rec(
        "Enchanted lyre (Fremennik teleports)",
        "feature",
        quests=["The Fremennik Trials"],
        notes="Members. Obtained during The Fremennik Trials. Teleports to Rellekka (and Waterbirth Island/Neitiznot/Jatizso once unlocked). Recharged at Fossegrimen's altar.",
    ))

    # --- Achievement-diary / cape transport features (skill/diary gated) ---
    R.append(rec(
        "Fairy ring use without a staff",
        "feature",
        notes="Members. Players who have completed the Elite Lumbridge & Draynor Diary no longer need a dramen or lunar staff to use a fairy ring.",
    ))
    R.append(rec(
        "Fairy ring (player-owned house, Construction)",
        "feature",
        skills={"Construction": 85},
        items=["Watering can (>=1 dose water)", "Fairy enchantment", "10 unnoted mushrooms"],
        notes="Members. A fairy ring can be grown in the POH superior garden at 85 Construction (boostable).",
    ))
    R.append(rec(
        "Spirit tree (player-owned house, Construction)",
        "feature",
        quests=["Tree Gnome Village"],
        skills={"Construction": 75, "Farming": 83},
        items=["Spirit sapling"],
        notes="Members. A spirit tree can be planted in the POH superior garden at 75 Construction (also requires 83 Farming). Grows instantly and does not count toward the player-grown spirit tree limit.",
    ))
    R.append(rec(
        "Spirit tree & fairy ring (Spiritual Fairy Tree, POH)",
        "feature",
        quests=["Tree Gnome Village", "Fairytale I - Growing Pains"],
        skills={"Construction": 95, "Farming": 83},
        notes="Members. At 95 Construction (and 83 Farming) players can build a Spiritual Fairy Tree in the POH, granting access to both the spirit tree and fairy ring networks at once.",
    ))
    R.append(rec(
        "Player-grown spirit trees (Farming patches)",
        "feature",
        quests=["Tree Gnome Village"],
        skills={"Farming": 83},
        items=["Spirit sapling (from untradeable spirit seed)"],
        notes="Members. At 83 Farming players can grow spirit trees in five patches (Etceteria, Brimhaven, Port Sarim, Hosidius, Farming Guild advanced tier). Limit: 1 at 83, 2 at 88, 3 at 93, 4 at 96, unlimited at 99 (boostable).",
    ))

    # --- Area access (notable quest-gated regions reachable via transport) ---
    R.append(rec(
        "Fossil Island access",
        "area",
        quests=["Bone Voyage"],
        notes="Members. Fossil Island (and its Mycelium Transportation System / rowboats) is unlocked by completing Bone Voyage.",
    ))
    R.append(rec(
        "Lunar Isle access",
        "area",
        quests=["Lunar Diplomacy"],
        items=["Seal of passage (before Lunar Diplomacy completion)"],
        notes="Members. Reached by boat (Lady Zay from Pirates' Cove). A seal of passage is required to remain on the island until Lunar Diplomacy is completed.",
    ))
    R.append(rec(
        "Prifddinas access",
        "area",
        quests=["Song of the Elves"],
        notes="Members. The elf city Prifddinas (with its spirit tree and teleport crystal destinations) is unlocked by completing Song of the Elves.",
    ))
    R.append(rec(
        "Great Kourend access",
        "area",
        notes="Members. Great Kourend / Kebos (and many Arceuus/Kourend transport features) become available after travelling there (e.g. via Veos). Several fairy rings in the region require having visited Great Kourend at least once.",
    ))
    R.append(rec(
        "Weiss access (Icy basalt teleport)",
        "area",
        quests=["Making Friends with My Arm"],
        notes="Members. Weiss is unlocked via Making Friends with My Arm; the Icy basalt provides a one-use teleport to Weiss (rechargeable basalt obtained there).",
    ))

    return R


def main():
    fairy = parse_fairy_rings()
    trees = parse_spirit_trees()
    gliders = parse_gnome_gliders()
    manual = manual_records()

    records = manual + fairy + trees + gliders

    # domain stats
    by_type = {}
    by_group = {}
    members_only = 0
    f2p_or_mixed = 0
    quest_gated = 0
    skill_gated = 0
    item_gated = 0
    for r in records:
        by_type[r["type"]] = by_type.get(r["type"], 0) + 1
        g = r.get("domain_group", "")
        by_group[g] = by_group.get(g, 0) + 1
        if r["requirements"]["quests"]:
            quest_gated += 1
        if r["requirements"]["skills"]:
            skill_gated += 1
        if r["requirements"]["items"]:
            item_gated += 1

    fairy_codes = sorted({r["code"] for r in fairy})

    envelope = {
        "_provenance": {
            "domain": "unlocks_transport",
            "source_urls": SOURCE_URLS,
            "source_query": None,
            "accessed": ACCESSED,
            "license": "CC BY-NC-SA 3.0",
            "extraction_method": "script",
            "raw_files": RAW_FILES,
            "record_count": len(records),
            "completeness": {
                "bounded_by": "OSRS Wiki Transportation page + per-feature pages (Fairy rings, Spirit tree, Gnome glider). Transport is an open-ended semi-structured domain; this captures the major networks/systems, the full fairy-ring node table, all spirit-tree and gnome-glider nodes, the three alternate spellbook unlocks, and notable quest-gated teleport items and area-access unlocks.",
                "universe_count": None,
                "records_count": len(records),
                "known_missing": [
                    "Standard-spellbook basic/teleother/tele-group teleport spells without quest/area gates (level-only) are summarised, not enumerated per spell.",
                    "Enchanted jewellery (glory/games necklace/ring of dueling/skills necklace/combat bracelet/digsite pendant etc.) destinations are not enumerated as individual records.",
                    "Portal nexus / magic tablets / teleport scrolls catalogue (per-destination items) not enumerated individually.",
                    "Achievement-diary and combat-achievement reward teleport items beyond the examples given are not all enumerated.",
                    "Ship/boat/two-way-shuttle and one-way transportation lists are captured at system level only, not as per-route records.",
                    "Account-type axes (members/f2p) noted in record notes rather than as a structured field; nearly all listed transport systems are members-only (carry 'members').",
                ],
            },
            "domain_stats": {
                "records_by_type": by_type,
                "records_by_group": by_group,
                "quest_gated_records": quest_gated,
                "skill_gated_records": skill_gated,
                "item_gated_records": item_gated,
                "fairy_ring_nodes_parsed": len(fairy),
                "fairy_ring_codes": fairy_codes,
                "spirit_tree_nodes_parsed": len(trees),
                "gnome_glider_nodes_parsed": len(gliders),
                "note": "Value/price fields are not applicable to this domain (transport unlocks). Coin fares (e.g. Lovakengj minecart, charter ships) are noted as sinks in record notes, not income; no money records here.",
            },
        },
        "records": records,
        "_excluded": [
            {
                "unlock": "Grand Exchange-dependent transport convenience",
                "reason": "No GE-buy/sell transport methods exist in this domain; account-type income gate (requires_ge) is not triggered for unlock/transport records. Listed here only to document that the account-type exclusion rule was evaluated and found N/A.",
            }
        ],
    }

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(envelope, f, indent=2, ensure_ascii=False)

    print(f"record_count={len(records)}")
    print(f"by_type={by_type}")
    print(f"by_group={by_group}")
    print(f"fairy_nodes={len(fairy)} codes={len(fairy_codes)}")
    print(f"spirit_trees={len(trees)} gliders={len(gliders)}")
    print(f"quest_gated={quest_gated} skill_gated={skill_gated} item_gated={item_gated}")


if __name__ == "__main__":
    main()
