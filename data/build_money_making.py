#!/usr/bin/env python3
"""Build data/money_making.json from the OSRS Wiki money_making_guide bucket.

Source: oldschool.runescape.wiki MediaWiki bucket API.
License: CC BY-NC-SA 3.0 (OSRS Wiki content).

Faithful extraction (no paraphrasing of facts). Keeps raw_json, splits
inputs/outputs, and applies the ACCOUNT-TYPE GATE: methods that require
buying a tradeable material from the GE and selling a tradeable product to
the GE (buy-process-sell / flipping) get requires_ge:true and are EXCLUDED
for ironmen (moved to _excluded with a reason).

Run from anywhere:  python3 data/build_money_making.py
"""
import json
import datetime
import os
import re
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))          # .../data
RAW = os.path.join(HERE, "raw", "money_making_guide_bucket.json")
OUT = os.path.join(HERE, "money_making.json")
RAW_REL = "data/raw/money_making_guide_bucket.json"        # repo-relative, for provenance
SOURCE_URL = ("https://oldschool.runescape.wiki/api.php?action=bucket&format=json&"
              "query=bucket('money_making_guide').select('page_name','value','recurring','json')"
              ".limit(5000).run()")

# --- requires_ge (buy-process-sell / flipping) classifier -------------------
# A method is GE-dependent for income realisation when its profit comes from
# buying a tradeable MATERIAL (GE) and selling a tradeable PRODUCT (GE).
# Combat/Collecting/Farming/Hunter generate their primary output from the
# world (drops/picks/grows), so they are iron-doable (irons just realise
# value via alch/value, not GE) and are NOT flagged here.
PROCESSING_CATS = {"Processing", "Processing (Sapling)", "Cooking (Brewing)"}
# Processing/conversion skills: their money methods BUY a material and convert it
# into a product (buy-process-sell), so a GE-priced material input means the
# method's published profit needs the GE. Gathering skills (Mining/Fishing/
# Woodcutting/Hunter/Thieving/Runecraft/Agility/Farming/Sailing/Slayer) produce
# their output from the world and are iron-doable, so they are NOT gated even
# when they consume a GE-priced supply (teleport/bait/essence).
PROC_SKILLS = {"Crafting", "Fletching", "Cooking", "Smithing", "Herblore", "Firemaking", "Magic"}
GATHER_SKILLS = {"Mining", "Fishing", "Woodcutting", "Hunter", "Thieving",
                 "Runecraft", "Agility", "Farming", "Sailing", "Slayer"}


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def has_gemw_input(j):
    """Any GE-priced (gemw) input with positive value, excluding Coins.

    NOTE: this deliberately does NOT filter out 'consumable'-looking names.
    In a Processing recipe the bought item IS the processed material — e.g.
    'Battlemage potion(4)' is the material for 'Divine battlemage potion(4)'.
    A previous name-based consumable filter suppressed exactly these, which let
    GE-arbitrage potions (divine super-combat/battlemage/bastion/magic/ranging)
    slip past the iron gate while their siblings made from 'Super attack(4)'
    etc. were correctly excluded. Processing skills never overlap with
    combat/gathering methods (different skillcategory), so no suppression is
    needed here — any gemw material in a processing recipe means GE-arbitrage.
    """
    return any(
        i.get("pricetype") == "gemw" and _num(i.get("value")) > 0
        and (i.get("name", "").lower() != "coins")
        for i in (j.get("inputs") or [])
    )


def _skills_in_req(j):
    return set(re.findall(r'data-skill="([^"]+)"', str(j.get("skill") or "")))


def is_processing_method(j):
    """True if the method is a buy-process-sell conversion (vs gathering/combat).

    Uses skillcategory; when it is missing, falls back to the skill requirement.
    e.g. 'Smithing oathplate armour' has skillcategory=None but requires Smithing
    (processing -> gated), while 'Killing Zalcano' requires Mining (gathering ->
    not gated). Magic conversion (enchant/alch/tan/spin/plank/charge/tablets) is
    processing; its Coins-output methods (high-alch/forge) are caught here even
    though they have no gemw OUTPUT, because the gemw INPUT is bought on the GE.
    """
    # Only "Skilling" methods can be buy-process-sell here. Combat ("Combat/*"),
    # Collecting, Farming, Hunter, Minigame etc. produce world output and must NOT
    # be gated even when they consume GE-priced supplies (food/potions/runes) or
    # require a processing skill (e.g. Magic for barrage).
    if j.get("category") != "Skilling":
        return False
    sc = j.get("skillcategory")
    if sc in PROC_SKILLS:
        return True
    if sc is None:
        req = _skills_in_req(j)
        return bool(req & PROC_SKILLS) and not (req & GATHER_SKILLS)
    return False


def realization_channel_for(outputs):
    """How the method's OUTPUT value is realized (the money-domain gate field).

    coins = only direct Coins output (iron-realizable as-is);
    ge    = only priced non-coin outputs (realized via GE sale / item value);
    mixed = both direct coins and priced non-coin outputs.
    Outputs here are normalise_io() dicts (is_coins + pricing_basis set).
    """
    has_coins = any(o["is_coins"] for o in outputs)
    has_priced_noncoin = any(
        (not o["is_coins"]) and o.get("pricing_basis") in ("ge", "store")
        for o in outputs
    )
    if has_coins and not has_priced_noncoin:
        return "coins"
    if has_coins and has_priced_noncoin:
        return "mixed"
    return "ge"


def requires_ge(j, page):
    act = (j.get("activity") or "").lower()
    pg = (page or "").lower()
    if "flip" in act or "flipping" in pg:
        return True
    if j.get("category") in PROCESSING_CATS:
        return True
    # a processing/conversion method that buys a GE-priced material is GE-arbitrage
    # (sells the product on the GE, OR alchs/forges it to coins — either way the
    # bought input needs the GE), so it is not iron-realizable as priced.
    if is_processing_method(j) and has_gemw_input(j):
        return True
    return False


# --- aggregate / pseudo-item detection --------------------------------------
AGGREGATE_RE = re.compile(r"(drop table|loot|rewards?|casket|clue|reward casket|pinata)", re.I)
WILDERNESS_RE = re.compile(r"wilderness|revenant|\bwildy\b|deep wild", re.I)


def is_aggregate_output(name):
    return bool(AGGREGATE_RE.search(name or ""))


def is_wilderness(page, j):
    blob = (page or "") + " " + (j.get("activity") or "") + " " + (j.get("version") or "")
    return bool(WILDERNESS_RE.search(blob))


def normalise_io(io, basis_default):
    """Faithful copy of an input/output line + a pricing_basis tag."""
    pt = io.get("pricetype")
    pricing_basis = "ge" if pt == "gemw" else ("store" if pt == "value" else pt)
    name = io.get("name")
    return {
        "name": name,
        "value": io.get("value"),            # gp per unit (price-volatile snapshot)
        "qty": io.get("qty"),                # per kill/action when isperkill, else per hour
        "isph": io.get("isph"),              # is-per-hour flag from source
        "pricetype": pt,
        "pricing_basis": pricing_basis,
        "is_aggregate": is_aggregate_output(name),
        "is_coins": (name or "").lower() == "coins",
    }


def build():
    with open(RAW) as f:
        raw = json.load(f)
    rows = raw["bucket"]

    records = []
    excluded = []
    cat_counter = Counter()
    members_counter = Counter()
    requires_ge_count = 0
    recurring_count = 0
    aggregate_outputs = 0
    coins_outputs = 0
    wilderness_count = 0

    for r in rows:
        j = json.loads(r["json"])
        page = r["page_name"]
        name = page.replace("Money making guide/", "")

        inputs = [normalise_io(i, "ge") for i in (j.get("inputs") or [])]
        outputs = [normalise_io(o, "ge") for o in (j.get("outputs") or [])]

        if any(o["is_aggregate"] for o in outputs):
            aggregate_outputs += 1
        if any(o["is_coins"] for o in outputs):
            coins_outputs += 1

        prices = j.get("prices") or {}
        gp_hr = prices.get("default_value")  # gp/hr snapshot (GE-priced dataset)

        rge = requires_ge(j, page)

        # recurring: top-level field present (empty string) OR has recurrence
        is_recurring = ("recurring" in r) or ("recurrence" in j)

        rec = {
            "page_name": page,
            "name": name,
            "url": "https://oldschool.runescape.wiki/w/" + page.replace(" ", "_"),
            "category": j.get("category"),
            "skillcategory": j.get("skillcategory"),
            "members": j.get("members"),
            "activity": j.get("activity"),
            # account-type gate -------------------------------------------------
            "audience": "main",            # dataset is GE-priced -> mains
            "pricing_basis": "ge",         # default; per-output basis carried in inputs/outputs
            "requires_ge": rge,            # buy-process-sell / flipping
            "iron_eligible": not rge,      # quick flag for downstream
            "realization_channel": realization_channel_for(outputs),  # coins|ge|mixed
            "wilderness": is_wilderness(page, j),   # risk flag (PKers / item loss on death)
            # value (price-volatile snapshot) ----------------------------------
            "gp_hr": gp_hr,                # gp/hour, basis=ge, snapshot (volatile)
            "gp_hr_basis": "ge",
            "gp_hr_note": "price-volatile snapshot; GE prices at accessed time",
            "value": _num(r.get("value")) if r.get("value") not in (None, "") else None,
            # method detail -----------------------------------------------------
            "intensity": j.get("intensity"),
            "quest": j.get("quest"),
            "skill_requirements_html": j.get("skill"),   # kept raw (wiki HTML)
            "other_requirements_html": j.get("other"),   # kept raw (wiki HTML)
            "isperkill": j.get("isperkill"),
            "kph": prices.get("default_kph"),
            "kph_text": prices.get("kph_text"),
            "input_perkill": prices.get("input_perkill"),
            "output_perkill": prices.get("output_perkill"),
            "input_perhour": prices.get("input_perhour"),
            "output_perhour": prices.get("output_perhour"),
            # versioned methods -------------------------------------------------
            "variant": j.get("version"),
            # recurring methods -------------------------------------------------
            "recurring": is_recurring,
            "recurrence": j.get("recurrence"),
            "recurrence_time_units": j.get("time"),
            # inputs/outputs kept split ----------------------------------------
            "inputs": inputs,
            "outputs": outputs,
            # raw passthrough ---------------------------------------------------
            "raw_json": j,
        }

        cat_counter[j.get("category")] += 1
        members_counter["members" if j.get("members") else "f2p"] += 1
        if is_recurring:
            recurring_count += 1
        if rec["wilderness"]:
            wilderness_count += 1

        if rge:
            requires_ge_count += 1
            excluded.append({
                **rec,
                "reason": ("requires_ge: buy-process-sell / flipping (buy tradeable material on GE, "
                           "sell tradeable product on GE) -> income not realisable for ironman "
                           "(no GE access). Iron-realizable only via High Alch/value/store where applicable."),
            })
        else:
            records.append(rec)

    accessed = datetime.datetime.now(datetime.timezone.utc).isoformat()

    envelope = {
        "_provenance": {
            "domain": "money_making",
            "source_urls": [SOURCE_URL],
            "source_query": ("bucket('money_making_guide').select('page_name','value',"
                             "'recurring','json').limit(5000).run()"),
            "accessed": accessed,
            "license": "CC BY-NC-SA 3.0",
            "extraction_method": "script",
            "raw_files": [RAW_REL],
            "record_count": len(records),
            "completeness": {
                "bounded_by": "OSRS Wiki money_making_guide bucket (full universe)",
                "universe_count": len(rows),
                "records_count": len(records),
                "known_missing": [],   # full bucket fetched (627 of 627); no truncation
            },
            "domain_stats": {
                "universe_rows": len(rows),
                "records_kept": len(records),
                "excluded_count": len(excluded),
                "requires_ge_count": requires_ge_count,
                "recurring_count": recurring_count,
                "wilderness_count": wilderness_count,
                "by_category": dict(cat_counter),
                "members_split": dict(members_counter),
                "outputs_with_aggregate_count": aggregate_outputs,
                "outputs_with_coins_count": coins_outputs,
                "variant_methods": [r["name"] for r in (records + excluded) if r.get("variant")],
                "audience": "main (GE-priced dataset)",
                "value_note": ("gp_hr/value and all input/output prices are price-volatile GE snapshots "
                               "at accessed time"),
                "excluded_basis": ("ironman gate: requires_ge methods (buy-process-sell / flipping) "
                                   "moved to _excluded, not counted in record_count"),
            },
        },
        "records": records,
        "_excluded": excluded,
    }

    with open(OUT, "w") as f:
        json.dump(envelope, f, ensure_ascii=False, indent=2)

    print("universe rows:", len(rows))
    print("records:", len(records))
    print("excluded (requires_ge):", len(excluded))
    print("recurring:", recurring_count)
    print("aggregate-output methods:", aggregate_outputs)
    print("coins-output methods:", coins_outputs)
    print("variant methods:", envelope["_provenance"]["domain_stats"]["variant_methods"])


if __name__ == "__main__":
    build()
