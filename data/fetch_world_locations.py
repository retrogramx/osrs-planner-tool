#!/usr/bin/env python3
"""Fetch the IN location type-categories + F2P/Members membership + each page's
categories (for parentage) from the MediaWiki category API. Deterministic + sorted.
Source: OSRS Wiki (CC BY-NC-SA). Verbatim — no inference. Run: ./venv/bin/python data/fetch_world_locations.py
"""
import json, os, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
UA = "GildedTome-research/1.0 (aalvarez0295@gmail.com)"
API = "https://oldschool.runescape.wiki/api.php"
# IN type-categories (the granularity filter; banks/scenery/NPCs/granular-mines are OUT)
IN_CATS = ["Dungeons", "Slayer dungeons", "Caves", "Raids", "Minigames", "Guilds",
           "Agility courses", "Hunter areas", "Castles", "Settlements", "Islands", "Mines"]
ACCESS = ["Free-to-play locations", "Members' locations"]


def _api(params):
    url = API + "?" + urllib.parse.urlencode({**params, "format": "json"})
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
        return json.load(r)


def members(cat):
    out, cont = [], None
    while True:
        p = {"action": "query", "list": "categorymembers", "cmtitle": f"Category:{cat}", "cmlimit": "500", "cmtype": "page"}
        if cont:
            p["cmcontinue"] = cont
        d = _api(p)
        out += [m["title"] for m in d.get("query", {}).get("categorymembers", []) if m["ns"] == 0]
        cont = d.get("continue", {}).get("cmcontinue")
        if not cont:
            break
        time.sleep(0.1)
    return sorted(out)


def main():
    os.makedirs(RAW, exist_ok=True)
    cats = {c: members(c) for c in IN_CATS}
    access = {c: members(c) for c in ACCESS}
    titles = sorted({t for lst in cats.values() for t in lst})
    # each page's categories (batched 50) for region parentage
    page_cats = {}
    for i in range(0, len(titles), 50):
        d = _api({"action": "query", "titles": "|".join(titles[i:i + 50]), "prop": "categories", "cllimit": "500"})
        for pg in d.get("query", {}).get("pages", {}).values():
            page_cats[pg["title"]] = sorted(c["title"].replace("Category:", "") for c in pg.get("categories", []))
        time.sleep(0.08)
    out = {"_provenance": {"domain": "wiki_location_categories", "source": "OSRS Wiki category API",
                           "license": "CC BY-NC-SA 3.0", "in_categories": IN_CATS, "counts": {c: len(v) for c, v in cats.items()}},
           "categories": cats, "free_to_play": access["Free-to-play locations"],
           "members": access["Members' locations"], "page_categories": dict(sorted(page_cats.items()))}
    with open(os.path.join(RAW, "wiki_location_categories.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("DONE:", {c: len(v) for c, v in cats.items()}, "| pages:", len(titles))


if __name__ == "__main__":
    main()
