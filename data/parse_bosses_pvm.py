#!/usr/bin/env python3
"""
bosses_pvm domain extractor for Gilded Tome.

SOURCE: OSRS Wiki — Money making guide combat rows (Bucket API, already cached at
data/raw/money_making_bucket_full.json) joined with the Boss list page
(data/raw/boss_page.wikitext for the bounded universe + per-boss metadata).

Sourcing rule: OSRS Wiki only. License CC BY-NC-SA 3.0.

Account-type gate: every money record is tagged with audience + pricing_basis.
A method whose income is realized by SELLING tradeable drops on the Grand
Exchange (the wiki's gp/hr is computed from GE 'gemw' prices) sets
requires_ge: true. Such methods are NOT iron-realizable as priced, so they are
copied into _excluded with a reason (irons must recompute via High Alch / value /
direct coins). Records remain in `records` for mains; the flag + _excluded entry
make the iron exclusion explicit per the shared rules.
"""
import json, re, datetime, os

ROOT = "/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool"
BUCKET = f"{ROOT}/data/raw/money_making_bucket_full.json"
BOSSPAGE = f"{ROOT}/data/raw/boss_page.wikitext"
OUT = f"{ROOT}/data/bosses_pvm.json"

# --------------------------------------------------------------------------
# 1. Bounded universe: the Boss list (structured wikitable rows on /w/Boss)
# --------------------------------------------------------------------------
def parse_boss_universe(text):
    start = text.index("==List of bosses==")
    section = text[start:]
    lines = section.split("\n")
    bosses = []
    sub = None
    in_table = False
    for i, ln in enumerate(lines):
        s = ln.strip()
        if s.startswith("==") and not s.startswith("==="):
            if "List of bosses" not in s:
                break
        if s.startswith("==="):
            sub = s.strip("= ").strip()
        if s.startswith("{|"):
            in_table = True
        if s.startswith("|}"):
            in_table = False
        if in_table:
            m = re.match(r"^\|\[\[([^\]|]+)(?:\|[^\]]+)?\]\]\s*$", s)
            if m:
                nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
                if "File:" in nxt:
                    bosses.append({"boss": m.group(1), "group": sub})
    return bosses

# --------------------------------------------------------------------------
# 2. Helpers for wikitext / skill-field parsing
# --------------------------------------------------------------------------
def strip_links(s):
    return re.sub(r"\[\[([^\]|]+\|)?([^\]]+)\]\]", r"\2", s)

def parse_skill_requirements(skill_field):
    """The bucket 'skill' field is wikitext bullets with data-skill / data-level
    spans. Extract (skill, level, note) faithfully."""
    out = []
    if not skill_field:
        return out
    # each <span class="scp" data-skill="X" data-level="Y"> ... trailing note
    # split on bullet markers to capture per-line notes
    for line in re.split(r"\n?\*\s*", skill_field):
        if not line.strip():
            continue
        m = re.search(r'data-skill="([^"]+)"(?:\s+data-level="([^"]+)")?', line)
        if not m:
            # textual-only line (e.g. "Quest X required")
            txt = strip_links(re.sub(r"<[^>]+>", "", line)).strip()
            if txt:
                out.append({"skill": None, "level": None, "note": txt})
            continue
        skill = m.group(1)
        level = m.group(2)
        # trailing prose after the span (e.g. "recommended", "(91 recommended)")
        after = line[m.end():]
        after = re.sub(r"</span>", "", after)
        after = strip_links(re.sub(r"<[^>]+>", "", after)).strip()
        # also catch additional skills mentioned in same bullet
        extra = re.findall(r'data-skill="([^"]+)"(?:\s+data-level="([^"]+)")?', line)
        for sk, lv in extra:
            note = after if (sk == skill) else None
            out.append({"skill": sk, "level": lv or None, "note": after or None if sk == skill else None})
        # de-dup: the first extra equals the primary; rebuild cleanly
    # rebuild cleanly to avoid double-count
    cleaned, seen = [], set()
    for line in re.split(r"\n?\*\s*", skill_field):
        if not line.strip():
            continue
        spans = re.findall(r'data-skill="([^"]+)"(?:\s+data-level="([^"]+)")?', line)
        note = strip_links(re.sub(r"<[^>]+>", "", re.sub(r'<span class="scp"[^>]*>.*?</span>', "", line))).strip()
        if not spans:
            txt = strip_links(re.sub(r"<[^>]+>", "", line)).strip()
            if txt and txt not in seen:
                seen.add(txt)
                cleaned.append({"skill": None, "level": None, "note": txt})
            continue
        for sk, lv in spans:
            key = (sk, lv)
            if key in seen:
                continue
            seen.add(key)
            cleaned.append({"skill": sk, "level": lv or None,
                            "note": note or None})
    return cleaned

# Drop classification ------------------------------------------------------
ALCHABLES_HINT = re.compile(
    r"(dragon |rune |adamant |granite |ahrim|karil|dharok|guthan|torag|verac|"
    r"bandos |armadyl |saradomin |zamorak|godsword|visage|helm|platebody|"
    r"platelegs|plateskirt|chainbody|kiteshield|shield|boots|gauntlets|"
    r"warhammer|maul|sword|scimitar|spear|halberd|crossbow|battleaxe|"
    r"sceptre|staff|robe|coif|leather|hauberk|cuisse|chaps|bow)", re.I)
UNTRADEABLE_HINT = re.compile(
    r"(pet |jar of|hilt|ornament kit|ranger boots|crystal|tome|"
    r"award|broken|dust$|chunk|ungael|sigil$|sigil )", re.I)

def classify_drop(name):
    nl = name.lower().strip()
    if "drop table" in nl:
        return "aggregate"        # pseudo-item, NOT a literal item
    if nl == "coins":
        return "coins"            # literal, iron-realizable
    if "scale" in nl and "zulrah" in nl:
        return "resource"         # Zulrah's scales (currency-like)
    if "rune" in nl and nl.endswith("rune"):
        return "rune"
    if UNTRADEABLE_HINT.search(nl):
        return "untradeable"
    if ALCHABLES_HINT.search(nl):
        return "gear_alchable"
    return "resource"

def realizable_for_iron(cls):
    # what an iron can still realize as income from this drop type
    return cls in ("coins", "gear_alchable", "resource", "rune")

# --------------------------------------------------------------------------
# 3. Build records from the combat bucket rows
# --------------------------------------------------------------------------
# keyword -> canonical boss / raid label (for joining MM rows to boss universe)
BOSS_KEYWORDS = [
    "Abyssal Sire","Alchemical Hydra","Amoxliatl","Araxxor","Blood Moon","Bryophyta",
    "Cerberus","Chaos Elemental","Chaos Fanatic","Commander Zilyana","Corporeal Beast",
    "crazy archaeologist","Doom of Mokhaiotl","Duke Sucellus","General Graardor","Giant Mole",
    "Grotesque Guardians","K'ril Tsutsaroth","Kalphite Queen","King Black Dragon","Kraken",
    "Kree'arra","Nex","Phantom Muspah","Royal Titans","Sarachnis","Scorpia","Scurrius",
    "Hueycoatl","The Leviathan","The Whisperer","Thermonuclear Smoke Devil","Vardorvis",
    "Vorkath","Yama","Zulrah","Callisto","Venenatis","Vet'ion","Spindel","Artio","Calvar'ion",
    "Dagannoth Kings","Phosani's Nightmare","Nightmare","Chambers of Xeric","Tombs of Amascut",
    "Theatre of Blood","Corrupted Gauntlet","Gauntlet","Fortis Colosseum","Moons of Peril",
    "Tormented Demons","Revenant","Contract of","Barrows",
]

def boss_label(activity):
    for kw in BOSS_KEYWORDS:
        if kw.lower() in activity.lower():
            return kw
    return None

# Wilderness / risky locations
WILD_HINT = re.compile(
    r"(wilderness|callisto|venenatis|vet'ion|spindel|artio|calvar'ion|revenant|"
    r"chaos fanatic|chaos elemental|scorpia|crazy archaeologist|lava dragon|"
    r"king black dragon|chasm of fire)", re.I)

def build_record(page_name, j):
    activity_raw = j.get("activity", "")
    activity = strip_links(activity_raw).strip()
    label = boss_label(activity)
    prices = j.get("prices") or {}
    kph = prices.get("default_kph")
    kph_text = prices.get("kph_text")
    members = bool(j.get("members"))

    # kc/hr only meaningful when kph_text is kills/raids per hour
    kc_hr = None
    kc_basis = kph_text
    if kph is not None:
        kc_hr = kph

    # gp/hr (volatile snapshot, GE-priced by the wiki)
    gp_hr = prices.get("default_value")

    # skills
    skills = parse_skill_requirements(j.get("skill", ""))

    # gear / consumable inputs (items required)
    items, gear = [], []
    for inp in j.get("inputs", []):
        nm = inp.get("name")
        if not nm:
            continue
        cls = classify_drop(nm)
        entry = {"item": nm, "qty_per_hr_or_kill": inp.get("qty"),
                 "value_each": inp.get("value"), "pricetype": inp.get("pricetype")}
        if cls in ("gear_alchable", "untradeable"):
            gear.append(entry)
        else:
            items.append(entry)

    # notable drops (outputs)
    notable, any_ge_sellable = [], False
    for o in j.get("outputs", []):
        nm = o.get("name")
        if not nm:
            continue
        cls = classify_drop(nm)
        is_aggregate = (cls == "aggregate")
        pt = o.get("pricetype")
        if pt == "gemw" and not is_aggregate and cls != "coins":
            any_ge_sellable = True
        notable.append({
            "name": nm,
            "drop_class": cls,                 # coins|gear_alchable|untradeable|resource|rune|aggregate
            "is_aggregate_pseudo_item": is_aggregate,
            "value_each": o.get("value"),
            "qty_per_hr_or_kill": o.get("qty"),
            "pricetype": pt,                   # gemw=GE price | value=item value
            "iron_realizable": realizable_for_iron(cls),
        })

    wilderness = bool(WILD_HINT.search(activity))

    # ACCOUNT-TYPE GATE (boss PvM):
    # Boss/raid killing is DIRECT-DROP income, NOT buy-process-sell / flipping, so it
    # is available to ALL account types -> requires_ge=false, audience='all'.
    # The wiki gp_hr is GE-priced (gemw), so an IRON realizes a different number: it
    # cannot GE-sell tradeable uniques, but keeps/alchs them. iron_income_note +
    # per-drop iron_realizable disclose the recompute; bosses are NOT iron-excluded.
    requires_ge = False
    iron_recompute = any_ge_sellable
    iron_realizable_drops = [d["name"] for d in notable if d["iron_realizable"]]
    iron_ge_only_drops = [d["name"] for d in notable
                          if (not d["iron_realizable"]) and d["pricetype"] == "gemw"
                          and not d["is_aggregate_pseudo_item"] and d["drop_class"] != "coins"]

    rec = {
        "boss": label or activity,
        "activity": activity,
        "method_page": f"Money making guide/{page_name.split('/',1)[-1]}" if "/" not in page_name else page_name,
        "combat_tier": j.get("category"),     # Combat/Low|Mid|High
        "members": members,
        "kc_hr": kc_hr,
        "kc_hr_basis": kc_basis,              # "Kills per hour" / "Trips per hour" / etc.
        "requirements": {
            "skills": skills,
            "quests": [],                      # see note: MM rows do not list quests as structured data; left honest-empty, see _provenance
            "items": items,
            "gear": gear,
        },
        "notable_drops": notable,
        "gp_hr": gp_hr,
        "gp_hr_unit": "gp/hr",
        "gp_hr_basis": "ge",                   # wiki computes gp_hr from GE (gemw) prices
        "gp_hr_volatile_snapshot": True,
        "audience": "all",                     # direct-drop PvM: all account types can do it
        "pricing_basis": "ge",                 # the gp_hr figure as published is GE-priced
        "requires_ge": requires_ge,            # false: not buy-process-sell; irons keep/alch drops
        "iron_income_recompute_needed": iron_recompute,
        "iron_realizable_drops": iron_realizable_drops,
        "iron_ge_only_drops": iron_ge_only_drops,
        "wilderness": wilderness,
        "risk": ("PvP/Wilderness risk — items can be lost on death" if wilderness else None),
    }
    return rec

# --------------------------------------------------------------------------
# Run
# --------------------------------------------------------------------------
def main():
    boss_text = open(BOSSPAGE).read()
    universe = parse_boss_universe(boss_text)
    universe_names = [b["boss"] for b in universe]

    bucket = json.load(open(BUCKET))["bucket"]
    combat_rows = []
    for row in bucket:
        try:
            j = json.loads(row["json"])
        except Exception:
            continue
        if (j.get("category") or "").startswith("Combat"):
            combat_rows.append((row["page_name"], j))

    records, excluded = [], []
    boss_money_count = 0
    for page_name, j in combat_rows:
        activity = strip_links(j.get("activity", "")).strip()
        label = boss_label(activity)
        if label is None:
            # Non-boss combat monster (regular Slayer/training): out of this domain
            excluded.append({
                "activity": activity,
                "method_page": f"Money making guide/{page_name.split('/',1)[-1]}",
                "combat_tier": j.get("category"),
                "reason": "non-boss combat monster (regular monster / Slayer creature); "
                          "not in the Boss-list universe for the bosses_pvm domain",
            })
            continue
        rec = build_record(page_name, j)
        records.append(rec)
        boss_money_count += 1

    # Iron-exclusion mirror: ONLY buy-process-sell / flipping methods are iron-excluded.
    # Boss/raid PvM is direct-drop income (requires_ge=false), so NONE are excluded for
    # irons here; irons simply recompute gp via alch/value (disclosed per-record).
    iron_excluded = [
        {
            "boss": r["boss"], "activity": r["activity"], "method_page": r["method_page"],
            "reason": "requires_ge=true (buy-process-sell / flipping) — not iron-realizable.",
        }
        for r in records if r["requires_ge"]
    ]

    # Which universe bosses have NO money-making record (known_missing within universe)
    def norm(x):
        return re.sub(r"^the\s+", "", x.lower()).strip()
    covered = set()
    for r in records:
        lbl = r["boss"]
        act_n = norm(r["activity"])
        for n in universe_names:
            if norm(n) in act_n or norm(n) == norm(lbl):
                covered.add(n)
    # raid sub-bosses are covered by whole-raid records
    raid_groups = {
        "Chambers of Xeric": ["Tekton","Vanguard","Vespula","Vasa Nistirio","Muttadile","Great Olm"],
        "Theatre of Blood": ["The Maiden of Sugadinti","Pestilent Bloat","Nylocas Vasilias","Sotetseg","Xarpus","Verzik Vitur"],
        "Tombs of Amascut": ["Akkha","Ba-Ba","Kephri","Zebak","Tumeken's Warden","Elidinis' Warden"],
    }
    raid_present = {
        "Chambers of Xeric": any("chambers of xeric" in r["activity"].lower() for r in records),
        "Theatre of Blood": any("theatre of blood" in r["activity"].lower() for r in records),
        "Tombs of Amascut": any("tombs of amascut" in r["activity"].lower() for r in records),
    }
    for grp, subs in raid_groups.items():
        if raid_present.get(grp):
            for s in subs:
                covered.add(s)
    # Gauntlet Hunllef
    if any("gauntlet" in r["activity"].lower() for r in records):
        covered.update(["Crystalline Hunllef", "Corrupted Hunllef"])
    if any("fortis colosseum" in r["activity"].lower() for r in records):
        covered.add("Sol Heredit")
    if any("moons of peril" in r["activity"].lower() for r in records):
        covered.update(["Blood Moon", "Blue Moon", "Eclipse Moon"])
    if any("dagannoth kings" in r["activity"].lower() for r in records):
        covered.update(["Dagannoth Supreme", "Dagannoth Rex", "Dagannoth Prime"])
    if any(r["activity"].strip().lower() == "barrows" for r in records):
        covered.update(["Ahrim the Blighted", "Karil the Tainted", "Dharok the Wretched",
                        "Guthan the Infested", "Torag the Corrupted", "Verac the Defiled"])

    known_missing = sorted(set(universe_names) - covered)

    # Disclose WHY each universe boss lacks a combat money-making record.
    skilling_bosses = {"Tempoross", "Wintertodt", "Zalcano"}
    km_reasons = {}
    for n in known_missing:
        if n in skilling_bosses:
            km_reasons[n] = ("skilling boss — its money-making guide row is in the Skilling "
                             "category, not Combat; out of scope for combat-sourced records "
                             "(exists in money_making.json under Skilling).")
        else:
            km_reasons[n] = ("no combat-category money-making guide row on the wiki "
                             "(niche/low-value, points-reward, or quest/sporadic boss); "
                             "killable but not listed as a money method.")

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    envelope = {
        "_provenance": {
            "domain": "bosses_pvm",
            "source_urls": [
                "https://oldschool.runescape.wiki/w/Boss",
                "https://oldschool.runescape.wiki/api.php?action=bucket&format=json&query=bucket('money_making_guide').select('page_name','value','recurring','json').limit(5000).run()",
            ],
            "source_query": "bucket('money_making_guide')...; combat rows (category startswith 'Combat') joined to /w/Boss list",
            "accessed": now,
            "license": "CC BY-NC-SA 3.0",
            "extraction_method": "script",
            "raw_files": [
                "data/raw/money_making_bucket_full.json",
                "data/raw/boss_page.wikitext",
            ],
            "record_count": len(records),
            "completeness": {
                "bounded_by": "OSRS Wiki Boss list (structured wikitable entries on /w/Boss)",
                "universe_count": len(universe_names),
                "records_count": len(records),
                "known_missing": known_missing,
                "known_missing_reasons": km_reasons,
            },
            "domain_stats": {
                "combat_money_rows_total": len(combat_rows),
                "boss_or_raid_money_records": boss_money_count,
                "non_boss_combat_rows_excluded": sum(1 for e in excluded if "non-boss" in e["reason"]),
                "requires_ge_records": sum(1 for r in records if r["requires_ge"]),
                "iron_doable_records": sum(1 for r in records if not r["requires_ge"]),
                "iron_income_recompute_needed_records": sum(1 for r in records if r["iron_income_recompute_needed"]),
                "members_records": sum(1 for r in records if r["members"]),
                "f2p_records": sum(1 for r in records if not r["members"]),
                "wilderness_records": sum(1 for r in records if r["wilderness"]),
                "universe_groups": sorted(set(b["group"] for b in universe)),
            },
            "notes": [
                "Records grain = one money-making ACTIVITY/method from the wiki Money making guide "
                "(so e.g. Vorkath has 3 gear-variant records; raids are one record per raid/mode).",
                "kc_hr is the wiki 'default_kph'; kc_hr_basis carries the wiki's kph_text "
                "('Kills per hour' for most; raids/Gauntlet/contracts may differ).",
                "gp_hr is a price-volatile snapshot the wiki recomputes from live GE (gemw) prices; "
                "gp_hr_basis='ge'. Treat as drift-prone.",
                "ACCOUNT GATE: boss/raid PvM is DIRECT-DROP income (not buy-process-sell), so every "
                "record has requires_ge=false and audience='all' — irons CAN do these bosses. The "
                "published gp_hr is GE-priced (pricing_basis='ge'); for irons the realized number "
                "differs, disclosed per-record via iron_income_recompute_needed + iron_realizable_drops "
                "(coins/alchables/resources/runes irons keep & alch/use) and iron_ge_only_drops "
                "(tradeable uniques an iron cannot GE-sell). Members carried per shared rules; "
                "the f2p record is Bryophyta. _excluded holds non-boss combat rows (no buy-process-sell "
                "boss methods exist, so the iron-exclusion mirror is empty).",
                "Drop classification: 'aggregate' = pseudo-item drop table (flagged, not a literal item); "
                "'coins' = literal direct coins (iron-realizable); gear_alchable/resource/rune are "
                "iron-realizable via alch/value; untradeable (pets, jars, hilts/crystals) are not income.",
                "requirements.quests is honest-empty: the Money making guide bucket rows do not expose "
                "quest prerequisites as structured data, and the Boss-list table requirements column could "
                "not be parsed reliably due to rowspan/multi-line cells. Quest gating should be sourced "
                "from per-boss infoboxes in a later pass (see known_missing handling).",
            ],
        },
        "records": records,
        "_excluded": excluded + iron_excluded,
    }

    with open(OUT, "w") as f:
        json.dump(envelope, f, indent=2)

    print(f"WROTE {OUT}")
    print(f"record_count = {len(records)}")
    print(f"universe_count = {len(universe_names)}")
    print(f"known_missing = {len(known_missing)}: {known_missing}")
    print(f"_excluded total = {len(excluded)+len(iron_excluded)} "
          f"(non-boss={len(excluded)}, iron-ge-mirror={len(iron_excluded)})")
    print("domain_stats:", json.dumps(envelope['_provenance']['domain_stats'], indent=2))

if __name__ == "__main__":
    main()
