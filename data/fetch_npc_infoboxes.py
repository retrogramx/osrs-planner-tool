#!/usr/bin/env python3
"""Fetch each shop-operator NPC's {{Infobox NPC}} location (verbatim) for the operator layer.
Roster = the distinct owner NPCs the shop brick captured. Deterministic + sorted. Verbatim — no
inference. Source: OSRS Wiki (CC BY-NC-SA). Run: ./venv/bin/python data/fetch_npc_infoboxes.py
"""
import importlib.util, json, os, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RAW = os.path.join(HERE, "raw")
UA = "GildedTome-research/1.0 (aalvarez0295@gmail.com)"
API = "https://oldschool.runescape.wiki/api.php"
WIKI = "https://oldschool.runescape.wiki/w/"

# Reuse the shop brick's pure parsers (split + location list); load it by path (no package import).
_spec = importlib.util.spec_from_file_location("fetch_shop_infoboxes", os.path.join(HERE, "fetch_shop_infoboxes.py"))
_fsi = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_fsi)
extract_infobox_block = _fsi.extract_infobox_block
split_top_level_params = _fsi.split_top_level_params
shop_locations = _fsi.shop_locations            # generic: |location= + |location1..N=

import sys
sys.path.insert(0, ROOT)                          # for kg_ingest + the committed snapshots
from kg_ingest.builders.npcs import operator_roster   # noqa: E402


def _api(params):
    url = API + "?" + urllib.parse.urlencode({**params, "format": "json"})
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
        return json.load(r)


def main():
    os.makedirs(RAW, exist_ok=True)
    storeline = json.load(open(os.path.join(RAW, "storeline_bucket.json"), encoding="utf-8"))["bucket"]
    shop_ib = json.load(open(os.path.join(RAW, "wiki_shop_infoboxes.json"), encoding="utf-8"))["infoboxes"]
    varrock = {s["name"] for s in json.load(open(os.path.join(HERE, "map", "varrock.json"), encoding="utf-8"))["shops"]}
    titles = operator_roster(storeline, shop_ib, varrock)

    infoboxes = {}
    for i in range(0, len(titles), 20):
        batch = titles[i:i + 20]
        d = _api({"action": "query", "titles": "|".join(batch), "prop": "revisions",
                  "rvprop": "content", "rvslots": "main", "redirects": 1})
        pages = d.get("query", {}).get("pages", {})
        for pg in pages.values():
            title = pg["title"]
            revs = pg.get("revisions", [])
            wt = revs[0]["slots"]["main"]["*"] if revs else ""
            block = extract_infobox_block(wt, "Infobox NPC")
            params = split_top_level_params(block) if block else {}
            infoboxes[title] = {"locations": shop_locations(params), "is_npc": bool(block),
                                "source_url": WIKI + title.replace(" ", "_")}
        time.sleep(0.1)
    with open(os.path.join(RAW, "wiki_npc_infoboxes.json"), "w", encoding="utf-8") as f:
        json.dump({"_provenance": {"domain": "wiki_npc_infoboxes", "source": "OSRS Wiki revisions API",
                                   "license": "CC BY-NC-SA 3.0", "param": "Infobox NPC|location"},
                   "infoboxes": dict(sorted(infoboxes.items()))}, f, ensure_ascii=False, indent=1)
    print(f"DONE: {len(titles)} operators, {sum(1 for v in infoboxes.values() if v['is_npc'])} with an NPC infobox, "
          f"{sum(1 for v in infoboxes.values() if v['locations'])} with a location")


if __name__ == "__main__":
    main()
