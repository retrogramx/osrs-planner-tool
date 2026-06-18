#!/usr/bin/env python3
"""Fetch the OSRS Wiki equipment universe from the Bucket API.

Pulls two buckets in full (paginated by offset) and saves the raw responses:
  - infobox_bonuses : combat stats + equipment slot / weapon speed / combat style
  - infobox_item    : item metadata (members, high alch, value, quest, tradeable...)

Source: OSRS Wiki Bucket API (action=bucket). Content licensed CC BY-NC-SA 3.0.
No inference here: every field is taken verbatim from the API. Joining /
normalization happens in parse_items_equipment.py.
"""
import json
import os
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
UA = "GildedTome-research/1.0 (aalvarez0295@gmail.com)"
BASE = "https://oldschool.runescape.wiki/api.php"
PAGE = 5000  # server caps a single run() at 5000 rows; paginate by offset

BONUS_FIELDS = [
    "page_name",
    "stab_attack_bonus", "slash_attack_bonus", "crush_attack_bonus",
    "range_attack_bonus", "magic_attack_bonus",
    "stab_defence_bonus", "slash_defence_bonus", "crush_defence_bonus",
    "range_defence_bonus", "magic_defence_bonus",
    "strength_bonus", "ranged_strength_bonus", "prayer_bonus",
    "magic_damage_bonus",
    "equipment_slot", "weapon_attack_speed", "weapon_attack_range",
    "combat_style",
]
ITEM_FIELDS = [
    "page_name", "item_name", "version_anchor", "is_members_only",
    "high_alchemy_value", "value", "weight", "buy_limit",
    "default_version", "quest", "tradeable", "examine", "release_date",
]


def run_query(query):
    url = BASE + "?action=bucket&format=json&query=" + urllib.parse.quote(query)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def fetch_all(bucket, fields):
    sel = ",".join(f"'{f}'" for f in fields)
    rows = []
    offset = 0
    while True:
        query = (f"bucket('{bucket}').select({sel})"
                 f".offset({offset}).limit({PAGE}).run()")
        d = run_query(query)
        if d.get("error"):
            raise RuntimeError(f"{bucket} offset={offset}: {d['error']}")
        batch = d.get("bucket", [])
        rows.extend(batch)
        print(f"  {bucket}: offset={offset} got {len(batch)} (total {len(rows)})")
        if len(batch) < PAGE:
            break
        offset += PAGE
        time.sleep(0.5)
    return rows


def main():
    os.makedirs(RAW, exist_ok=True)
    print("Fetching infobox_bonuses ...")
    bonuses = fetch_all("infobox_bonuses", BONUS_FIELDS)
    with open(os.path.join(RAW, "infobox_bonuses_bucket.json"), "w") as f:
        json.dump({"bucket": bonuses}, f, ensure_ascii=False, indent=2)

    print("Fetching infobox_item ...")
    items = fetch_all("infobox_item", ITEM_FIELDS)
    with open(os.path.join(RAW, "infobox_item_bucket.json"), "w") as f:
        json.dump({"bucket": items}, f, ensure_ascii=False, indent=2)

    print(f"DONE: {len(bonuses)} bonuses rows, {len(items)} item rows")


if __name__ == "__main__":
    main()
